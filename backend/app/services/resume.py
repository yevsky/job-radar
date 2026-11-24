"""CVs: read the PDF's text, let the AI list skills and wishes, copy what the user picks."""

import logging
from datetime import UTC, datetime
from io import BytesIO

from pydantic import ValidationError
from pypdf import PdfReader
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.base import AIProvider, AIProviderError
from app.ai.prompts import resume_extract_messages, resume_insights_messages
from app.ai.structured import AIOutputError, generate
from app.core.validation import format_errors
from app.models import Resume, User, UserPreferredEmploymentType, UserPreferredLocation
from app.models.user_profile import UserProfile
from app.schemas.ai import ResumeExtracted, ResumeInsights
from app.schemas.profile import (
    EmploymentTypesUpdate,
    LocationsUpdate,
    ProfileRead,
    SkillsUpdate,
)
from app.schemas.resume import ResumeApply
from app.services.offer_parsing import provider_label
from app.services.profile import to_profile_read
from app.services.technology import get_or_create_technologies

logger = logging.getLogger(__name__)

MAX_RESUME_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_RESUMES_PER_USER = 10
MAX_PDF_PAGES = 20  # a CV is 1-3 pages; this stops a huge PDF from keeping the server busy


class ResumeFileError(Exception):
    """The upload is not a PDF we can read text from. The message is shown to the user."""


class ResumeLabelTakenError(Exception):
    """The user already has a CV with this label."""


class ResumeLimitError(Exception):
    """The user already keeps MAX_RESUMES_PER_USER CVs."""


class ResumeNotFoundError(Exception):
    """No CV with this id, or it belongs to someone else."""


class ProfileLimitError(Exception):
    """Copying the CV data would go over a profile limit (50 skills, 10 locations)."""


# LaTeX fonts (Computer Modern) draw "ł" as two glyphs: a stroke called "suppress" and an "l".
# pypdf has no Unicode letter for "suppress", so it writes the glyph's name: 'Wroc/suppresslaw'.
TEX_LETTERS = {'/suppressl': 'ł', '/suppressL': 'Ł'}


def fix_tex_letters(text: str) -> str:
    """'Wroc/suppresslaw' -> 'Wrocław'; a stray '/suppress' left over is removed."""
    for glyphs, letter in TEX_LETTERS.items():
        text = text.replace(glyphs, letter)
    return text.replace('/suppress', '')


def pdf_text(content: bytes) -> str:
    """All text of a PDF, page by page. Raises ResumeFileError if there is none to read."""
    if not content.startswith(b'%PDF'):
        raise ResumeFileError('The file is not a PDF.')
    try:
        reader = PdfReader(BytesIO(content))
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ResumeFileError(f'The PDF has more than {MAX_PDF_PAGES} pages.')
        pages = [page.extract_text() or '' for page in reader.pages]
    except ResumeFileError:
        raise
    # A broken or password-protected file can fail anywhere inside pypdf, with many kinds of
    # errors. It's an uploaded file, so any of them means "we can't read it", never a 500.
    except Exception as err:
        raise ResumeFileError(
            'The PDF could not be read. Is it damaged or password-protected?'
        ) from err

    # Postgres text can't hold NUL characters, and some PDFs contain them
    text = '\n\n'.join(page.strip() for page in pages if page.strip()).replace('\x00', '')
    text = fix_tex_letters(text)
    if not text:
        raise ResumeFileError(
            'The PDF has no text to read. A scanned CV is only an image: '
            'export it as PDF from the editor you wrote it in.'
        )
    return text


def list_resumes(db: Session, user_id: int) -> list[Resume]:
    return list(
        db.scalars(
            select(Resume)
            .where(Resume.user_id == user_id)
            .order_by(Resume.created_at.desc(), Resume.id.desc())
        )
    )


def get_resume(db: Session, user_id: int, resume_id: int) -> Resume:
    """The user's own CV; another user's CV is "not found", so ids reveal nothing."""
    resume = db.get(Resume, resume_id)
    if resume is None or resume.user_id != user_id:
        raise ResumeNotFoundError
    return resume


def extract(db: Session, provider: AIProvider, resume: Resume) -> Resume:
    """Ask the AI what the CV says and store it. Raises AIProviderError or AIOutputError."""
    extracted = generate(provider, resume_extract_messages(resume.text), ResumeExtracted)
    resume.extracted = extracted.model_dump(mode='json')  # enums and dates as plain JSON
    resume.extracted_with = provider_label(provider)
    db.commit()
    return resume


def make_insights(db: Session, provider: AIProvider, resume: Resume) -> Resume:
    """Ask the AI for the CV's career snapshot and store it. Raises the AI errors.

    A second, separate call instead of more fields in the extraction: a longer answer made
    the small local model worse at the dates and the level, which code depends on. The level
    and years code counted go in as facts, so the suggested roles fit them.
    """
    extracted = resume.extracted or {}
    messages = resume_insights_messages(
        resume.text, extracted.get('experience_level'), extracted.get('experience_years')
    )
    insights = generate(provider, messages, ResumeInsights)
    resume.insights = insights.model_dump(mode='json')
    resume.insights_with = provider_label(provider)
    db.commit()
    return resume


def create_resume(
    db: Session, provider: AIProvider, user_id: int, label: str, file_name: str, content: bytes
) -> Resume:
    """Store a CV's text and what the AI read from it. The PDF bytes are not kept.

    Checks the cheap things first (label, count, the file), so a refused upload costs no AI
    call. Then two AI calls: the extraction and the career snapshot. If one fails, the CV is
    still stored with that field None; POST /resumes/{id}/extract or /insights tries again.
    """
    taken = db.scalar(select(Resume.id).where(Resume.user_id == user_id, Resume.label == label))
    if taken is not None:
        raise ResumeLabelTakenError
    count = db.scalar(select(func.count()).select_from(Resume).where(Resume.user_id == user_id))
    if (count or 0) >= MAX_RESUMES_PER_USER:
        raise ResumeLimitError
    if len(content) > MAX_RESUME_BYTES:
        raise ResumeFileError('The file is larger than 5 MB.')

    resume = Resume(user_id=user_id, label=label, file_name=file_name[:255], text=pdf_text(content))
    db.add(resume)
    db.commit()

    try:
        extract(db, provider, resume)
    except (AIProviderError, AIOutputError) as err:
        logger.warning('Could not read CV %s with AI: %s', resume.id, err)
    try:
        make_insights(db, provider, resume)
    except (AIProviderError, AIOutputError) as err:
        logger.warning('Could not make the snapshot of CV %s: %s', resume.id, err)
    return resume


def delete_resume(db: Session, user_id: int, resume_id: int) -> None:
    db.delete(get_resume(db, user_id, resume_id))
    db.commit()


def merged[T: str](current: list[T], added: list[T]) -> list[T]:
    """current + the added items it doesn't have yet, compared ignoring case."""
    seen = {item.lower() for item in current}
    result = list(current)
    for item in added:
        if item.lower() not in seen:
            seen.add(item.lower())
            result.append(item)
    return result


def apply_resume(db: Session, user: User, resume_id: int, data: ResumeApply) -> ProfileRead:
    """Copy the fields the user sent into their profile.

    Position and level are replaced. Locations and employment types are added to what the
    profile has, so nothing typed by hand is lost. Skills are added too, or replace the
    profile's when skills_mode is 'replace'. Every limit is checked before anything
    changes, and everything is committed once: either all of it is applied, or none.
    """
    resume = get_resume(db, user.id, resume_id)
    sent = data.model_dump(exclude_unset=True)

    try:
        kept = [] if data.skills_mode == 'replace' else [t.name for t in user.technologies]
        skills = (
            SkillsUpdate(skills=merged(kept, data.skills)).skills
            if data.skills is not None
            else None
        )
        locations = (
            LocationsUpdate(
                locations=merged([p.location for p in user.preferred_locations], data.locations)
            ).locations
            if data.locations is not None
            else None
        )
        employment_types = (
            EmploymentTypesUpdate(
                employment_types=merged(
                    [e.employment_type for e in user.preferred_employment_types],
                    data.employment_types,
                )
            ).employment_types
            if data.employment_types is not None
            else None
        )
    except ValidationError as err:
        raise ProfileLimitError(format_errors(err, root='profile')) from err

    if 'desired_position' in sent or 'experience_level' in sent:
        if user.profile is None:
            user.profile = UserProfile()
        if 'desired_position' in sent:
            user.profile.desired_position = data.desired_position
        if 'experience_level' in sent:
            user.profile.experience_level = data.experience_level
    if skills is not None:
        user.technologies = get_or_create_technologies(db, skills)
    if locations is not None:
        user.preferred_locations = [UserPreferredLocation(location=loc) for loc in locations]
    if employment_types is not None:
        user.preferred_employment_types = [
            UserPreferredEmploymentType(employment_type=t) for t in employment_types
        ]

    resume.applied_to_profile_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)
    return to_profile_read(user)
