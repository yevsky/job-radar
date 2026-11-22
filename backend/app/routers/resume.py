from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, UploadFile, status

from app.ai.base import AIProviderError
from app.ai.structured import AIOutputError
from app.db.dependencies import DbSession
from app.dependencies import AI, CurrentUser
from app.schemas.profile import ProfileRead
from app.schemas.resume import ResumeApply, ResumeDetail, ResumeRead
from app.services.resume import (
    MAX_RESUME_BYTES,
    MAX_RESUMES_PER_USER,
    ProfileLimitError,
    ResumeFileError,
    ResumeLabelTakenError,
    ResumeLimitError,
    ResumeNotFoundError,
    apply_resume,
    create_resume,
    delete_resume,
    extract,
    get_resume,
    list_resumes,
)

router = APIRouter(prefix='/resumes', tags=['resumes'])

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='CV not found')


def unprocessable(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=message)


@router.get('', response_model=list[ResumeRead])
def read_my_resumes(user: CurrentUser, db: DbSession) -> list[ResumeRead]:
    """Your CVs, newest first."""
    return [ResumeRead.model_validate(resume) for resume in list_resumes(db, user.id)]


@router.post('', response_model=ResumeRead, status_code=status.HTTP_201_CREATED)
def upload_resume(
    file: UploadFile,
    label: Annotated[str, Form(max_length=100)],
    user: CurrentUser,
    db: DbSession,
    ai: AI,
) -> ResumeRead:
    """Upload a CV as PDF (max 5 MB). Its text is stored and read by the AI; the PDF is not
    kept. Nothing goes into your profile until you apply it."""
    label = label.strip()
    if not label:
        raise unprocessable('Give the CV a label, e.g. "Backend CV".')
    if file.content_type != 'application/pdf':
        raise unprocessable('The file is not a PDF.')
    content = file.file.read(MAX_RESUME_BYTES + 1)  # one byte more is enough to see it's too big

    try:
        resume = create_resume(db, ai, user.id, label, file.filename or 'cv.pdf', content)
    except ResumeFileError as err:
        raise unprocessable(str(err)) from err
    except ResumeLabelTakenError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f'You already have a CV called "{label}".'
        ) from err
    except ResumeLimitError as err:
        raise unprocessable(
            f'You can keep at most {MAX_RESUMES_PER_USER} CVs. Delete one first.'
        ) from err
    return ResumeRead.model_validate(resume)


@router.get('/{resume_id}', response_model=ResumeDetail)
def read_my_resume(resume_id: int, user: CurrentUser, db: DbSession) -> ResumeDetail:
    """One of your CVs, with the text read from the PDF."""
    try:
        return ResumeDetail.model_validate(get_resume(db, user.id, resume_id))
    except ResumeNotFoundError as err:
        raise NOT_FOUND from err


@router.post('/{resume_id}/extract', response_model=ResumeRead)
def extract_resume_again(resume_id: int, user: CurrentUser, db: DbSession, ai: AI) -> ResumeRead:
    """Let the AI read the CV again, e.g. after it failed on upload."""
    try:
        resume = get_resume(db, user.id, resume_id)
    except ResumeNotFoundError as err:
        raise NOT_FOUND from err
    try:
        return ResumeRead.model_validate(extract(db, ai, resume))
    except (AIProviderError, AIOutputError) as err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI provider didn't answer, try again later",
        ) from err


@router.post('/{resume_id}/apply', response_model=ProfileRead)
def apply_resume_to_profile(
    resume_id: int, data: ResumeApply, user: CurrentUser, db: DbSession
) -> ProfileRead:
    """Copy the fields you picked into your profile. Position and level are replaced; skills,
    locations and employment types are added to the ones you have."""
    try:
        return apply_resume(db, user, resume_id, data)
    except ResumeNotFoundError as err:
        raise NOT_FOUND from err
    except ProfileLimitError as err:
        raise unprocessable(f'Your profile would go over a limit: {err}') from err


@router.delete('/{resume_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_my_resume(resume_id: int, user: CurrentUser, db: DbSession) -> None:
    try:
        delete_resume(db, user.id, resume_id)
    except ResumeNotFoundError as err:
        raise NOT_FOUND from err
