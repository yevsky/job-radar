"""The tools the AI assistant may call: each one wraps a service the routers already use.

A tool never takes a user id: it always works for the user in ToolContext (the logged-in
user), so the assistant can do exactly what that user can do in the app, and nothing more.

Read tools run at once. Write tools (`writes=True`) only describe what they would do; the chat
service stores that as a pending action, and they run after the user confirms it.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Any

from pydantic import BaseModel, Field, HttpUrl, UrlConstraints, ValidationError
from pydantic.json_schema import SkipJsonSchema
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.base import AIProvider, AIProviderError, ToolSpec
from app.ai.prompts import MAX_POSTING_CHARS, untrusted
from app.ai.structured import AIOutputError
from app.core.config import settings
from app.core.validation import format_errors
from app.models import JobOffer, User
from app.models.enums import ApplicationStatus, SourceKind
from app.schemas.ai import MAX_POSTING_TEXT
from app.schemas.analysis import AnalysisResult
from app.schemas.application import ApplicationUpdate, StatsRange
from app.schemas.job_offer import JobOfferFilters, JobOfferImport
from app.schemas.search import MAX_LOCATIONS, PostedWithin, SearchQuery, SearchResult
from app.search_sources.base import SearchSource
from app.search_sources.page_reader import PageReader
from app.services import application as applications
from app.services import job_offer as job_offers
from app.services.ai_analysis import (
    EmptyProfileError,
    analyse_offer,
    analyse_search_result,
    latest_analysis,
    store_analysis,
)
from app.services.job_offer_import import add_private_offer, normalize_url
from app.services.offer_parsing import enrich_saved_offer, find_link, parse_offer
from app.services.profile import to_profile_read
from app.services.resume import ResumeNotFoundError, list_resumes
from app.services.search import EmptyQueryError, NoSourcesError, SearchLimitError, run_search

MAX_ROWS = 20  # rows in one list result: enough to answer, small enough for an 8k context
MAX_DESCRIPTION_CHARS = 3_000
MAX_CALENDAR_DAYS = 92
# A shorter user message is a question or a link, not a pasted job posting
POSTING_MIN_CHARS = 200


class ToolError(Exception):
    """The tool can't do this (not found, bad arguments, limit reached). The message goes
    back to the model as the tool's result, so it can tell the user or try again."""


@dataclass
class ToolContext:
    """Everything a tool may use: the database, the logged-in user, and the outside services."""

    db: Session
    user: User
    provider: AIProvider
    sources: list[SearchSource]
    pages: PageReader | None
    # the results of the newest search in this conversation, so "save result 3" works
    last_search: list[SearchResult] = field(default_factory=list)
    # analyses of search results in this conversation, by url: kept when the result is saved
    search_analyses: dict[str, dict[str, Any]] = field(default_factory=dict)
    # the newest user message long enough to be a pasted posting, for add_offer_from_text
    pasted_text: str | None = None


@dataclass(frozen=True)
class ToolOutput:
    content: str  # what the model reads (JSON)
    note: str  # one line the user sees, e.g. 'Searched jobs: 8 results'
    data: dict[str, Any] | None = None  # stored with the message, e.g. the search results


@dataclass(frozen=True)
class Tool[A: BaseModel]:
    name: str
    description: str
    args: type[A]
    run: Callable[[ToolContext, A], ToolOutput]
    writes: bool = False
    # write tools only: one sentence for the confirm card; raises ToolError if it can't be done
    describe: Callable[[ToolContext, A], str] | None = None
    # write tools only, optional: fills in the arguments before they are stored with the
    # pending action (add_offer_from_text reads the posting once, here, not again on confirm)
    prepare: Callable[[ToolContext, A], A] | None = None

    def parse(self, arguments: dict[str, Any]) -> A:
        """The model's arguments as the tool's args model, or ToolError saying what's wrong."""
        try:
            return self.args.model_validate(arguments)
        except ValidationError as err:
            raise ToolError(f'Wrong arguments: {format_errors(err, root="arguments")}') from err


def as_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def inline_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """The args model's JSON schema with every $ref replaced by its definition.

    Small local models read a flat schema much better than one with $defs.
    """
    definitions = schema.get('$defs', {})

    def resolve(node: object) -> object:
        if isinstance(node, dict):
            if '$ref' in node:
                return resolve(definitions[node['$ref'].split('/')[-1]])
            return {k: resolve(v) for k, v in node.items() if k not in ('$defs', 'title')}
        if isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    result = resolve(schema)
    assert isinstance(result, dict)
    return result


# ---- arguments -----------------------------------------------------------------------------


class NoArgs(BaseModel):
    pass


class ApplicationsArgs(BaseModel):
    status: ApplicationStatus | None = Field(default=None, description='Only this status')


class StatsArgs(BaseModel):
    range: StatsRange = Field(
        default='all', description='Applications sent in the last 30 or 90 days, or all'
    )


class CalendarArgs(BaseModel):
    start: date | None = Field(default=None, description='First day, YYYY-MM-DD; default today')
    end: date | None = Field(
        default=None, description='Last day, YYYY-MM-DD; default start + 14 days'
    )


class OffersArgs(BaseModel):
    location: str | None = Field(default=None, max_length=100, description='City, e.g. Wrocław')
    technologies: list[str] = Field(default=[], max_length=5, description='e.g. ["Python"]')


class SearchArgs(BaseModel):
    position: str = Field(
        min_length=1,
        max_length=120,
        description='Job title with level, e.g. Junior Python developer',
    )
    locations: list[str] = Field(default=[], max_length=MAX_LOCATIONS, description='Cities')
    posted_within: PostedWithin | None = None


class TargetArgs(BaseModel):
    """An offer in the database, or a result of the newest search in this chat."""

    offer_id: int | None = Field(
        default=None,
        description='Id of an offer stored in the app (from list_job_offers or '
        'list_applications). Never a search result number.',
    )
    search_result: int | None = Field(
        default=None,
        ge=1,
        description='The search_result number of a result of the last search_jobs call',
    )


class AnalyseArgs(TargetArgs):
    resume_id: int | None = Field(default=None, description='A CV id to compare with, optional')


class StatusArgs(BaseModel):
    application_id: int
    status: ApplicationStatus


class PastedOfferArgs(BaseModel):
    """The posting itself is never an argument: the app reads it from the user's message."""

    url: Annotated[HttpUrl, UrlConstraints(max_length=2048)] | None = Field(
        default=None,
        description="The offer's link, only if the user gave it apart from the posting",
    )
    company_name: str | None = Field(
        default=None,
        max_length=200,
        description='Only if the user named the company and the posting does not',
    )
    # filled by the app (prepare_pasted_offer), hidden from the model
    draft: SkipJsonSchema[JobOfferImport | None] = None


# ---- read tools ----------------------------------------------------------------------------


def get_profile(ctx: ToolContext, _args: NoArgs) -> ToolOutput:
    # only the job-related part: the name and the bio never go to the AI provider
    profile = to_profile_read(ctx.user)
    data = profile.model_dump(mode='json', exclude={'first_name', 'last_name', 'bio'})
    return ToolOutput(as_json(data), 'Read your profile')


def get_resumes(ctx: ToolContext, _args: NoArgs) -> ToolOutput:
    rows = [
        {
            'id': resume.id,
            'label': resume.label,
            'file_name': resume.file_name,
            'uploaded': resume.created_at.date(),
            'extracted': resume.extracted,  # skills, level, ... read by the AI at upload
        }
        for resume in list_resumes(ctx.db, ctx.user.id)
    ]
    return ToolOutput(as_json(rows), f'Read your CVs: {len(rows)}')


def get_applications(ctx: ToolContext, args: ApplicationsArgs) -> ToolOutput:
    found = applications.list_applications(ctx.db, ctx.user.id)
    if args.status is not None:
        found = [a for a in found if a.status == args.status]
    rows = [
        {
            'application_id': a.id,
            'status': a.status,
            'title': a.job_offer.title,
            'company': a.job_offer.company_name,
            'offer_id': a.job_offer_id,
            'applied_at': a.applied_at,
            'interview_at': a.interview_at,
        }
        for a in found[:MAX_ROWS]
    ]
    result = {'total': len(found), 'applications': rows}
    return ToolOutput(as_json(result), f'Read your applications: {len(found)}')


def get_stats(ctx: ToolContext, args: StatsArgs) -> ToolOutput:
    stats = applications.stats(ctx.db, ctx.user.id, args.range)
    data = stats.model_dump(mode='json', exclude={'weekly'})
    return ToolOutput(as_json(data), 'Read your application stats')


def get_calendar(ctx: ToolContext, args: CalendarArgs) -> ToolOutput:
    start = args.start or datetime.now(UTC).date()
    end = args.end or start + timedelta(days=14)
    if end < start:
        raise ToolError('end is before start')
    if (end - start).days > MAX_CALENDAR_DAYS:
        raise ToolError(f'Ask for at most {MAX_CALENDAR_DAYS} days at once')
    events = applications.calendar(ctx.db, ctx.user.id, start, end)
    rows = [event.model_dump(mode='json') for event in events[: MAX_ROWS * 2]]
    result = {'start': start, 'end': end, 'events': rows}
    return ToolOutput(as_json(result), f'Read your calendar: {len(events)} events')


def get_offers(ctx: ToolContext, args: OffersArgs) -> ToolOutput:
    filters = JobOfferFilters(location=args.location, technologies=args.technologies)
    page = job_offers.list_job_offers(ctx.db, ctx.user.id, MAX_ROWS, 0, filters)
    rows = [item.model_dump(mode='json', exclude={'deadline'}) for item in page.items]
    result = {'total': page.total, 'offers': rows}
    return ToolOutput(as_json(result), f'Read job offers: {page.total}')


def get_offer(ctx: ToolContext, args: TargetArgs) -> ToolOutput:
    one_target(args)
    if args.search_result is not None:
        found = search_result(ctx, args.search_result)
        data = found.model_dump(mode='json', exclude={'description'})
        title, description = found.title, found.description or ''
    else:
        offer = job_offers.get_job_offer(ctx.db, args.offer_id or 0, ctx.user.id)
        if offer is None:
            raise ToolError(f'No job offer with id {args.offer_id}')
        exclude = {'description', 'is_private', 'last_seen_at'}
        data = offer.model_dump(mode='json', exclude=exclude)
        title, description = offer.title, offer.description or ''
    description = description[:MAX_DESCRIPTION_CHARS]
    data['next_steps'] = 'Do not repeat these details later. Ask whether to analyse the match '
    data['next_steps'] += '(analyse_offer) or save the offer (save_offer).'
    content = as_json(data) + '\n' + untrusted('job_posting', description, MAX_POSTING_CHARS)
    return ToolOutput(content, f'Read offer: {title}')


def search_jobs(ctx: ToolContext, args: SearchArgs) -> ToolOutput:
    query = SearchQuery(
        position=args.position, locations=args.locations, posted_within=args.posted_within
    )
    try:
        response = run_search(
            ctx.db, ctx.user, query, ctx.sources, settings.search_results_per_source
        )
    except EmptyQueryError as err:
        raise ToolError('Give a position to search for') from err
    except SearchLimitError as err:
        raise ToolError('The daily search limit is reached, try again tomorrow') from err
    except NoSourcesError as err:
        raise ToolError('Search is switched off by an admin right now') from err

    ctx.last_search = list(response.results)
    rows = [
        {
            'search_result': number,
            'title': r.title,
            'company': r.company_name,
            'location': r.location,
            'level': r.experience_level,
            'employment_type': r.employment_type,
            'technologies': r.technologies,
            'url': r.url,
        }
        for number, r in enumerate(response.results, start=1)
    ]
    result = {
        'query': response.query,
        'results': rows,
        'searches_left_today': response.searches_left_today,
        'failed_sources': [e.source for e in response.errors],
        'how_to_use': 'To read, analyse or save one of these, pass its number as search_result '
        '(not offer_id) to get_job_offer, analyse_offer or save_offer.',
    }
    data = {'results': [r.model_dump(mode='json') for r in response.results]}
    note = f'Searched "{response.query}": {len(rows)} results'
    return ToolOutput(as_json(result), note, data)


def search_result(ctx: ToolContext, number: int) -> SearchResult:
    if not ctx.last_search:
        raise ToolError('There is no search in this chat yet: call search_jobs first')
    if number > len(ctx.last_search):
        raise ToolError(f'The last search has only {len(ctx.last_search)} results')
    return ctx.last_search[number - 1]


def one_target(args: TargetArgs) -> None:
    if (args.offer_id is None) == (args.search_result is None):
        raise ToolError('Give either offer_id or search_result')


def analyse(ctx: ToolContext, args: AnalyseArgs) -> ToolOutput:
    one_target(args)
    data: dict[str, Any] = {'resume_id': args.resume_id}
    try:
        if args.offer_id is not None:
            row = analyse_offer(ctx.db, ctx.provider, ctx.user, args.offer_id, args.resume_id)
            result = AnalysisResult.model_validate(row, from_attributes=True)
        else:
            found = search_result(ctx, args.search_result or 0)
            result = analyse_search_result(ctx.db, ctx.provider, ctx.user, found, args.resume_id)
            data['search_url'] = str(found.url)
    except job_offers.OfferNotFoundError as err:
        raise ToolError(f'No job offer with id {args.offer_id}') from err
    except ResumeNotFoundError as err:
        raise ToolError(f'No CV with id {args.resume_id}') from err
    except EmptyProfileError as err:
        raise ToolError('The profile is empty: the user should add a position or skills') from err
    except (AIProviderError, AIOutputError) as err:
        raise ToolError('The match analysis failed, try again later') from err
    data['analysis'] = result.model_dump(mode='json')  # the chat shows it as the match card
    if 'search_url' in data:
        ctx.search_analyses[data['search_url']] = data
    # Only the score and the summary: given the reasons and red flags too, qwen2.5:3b
    # wrote the whole card out again under it.
    next_step = (
        'whether to save this offer (save_offer)'
        if args.search_result is not None
        else 'whether to save this offer or change its application status'
    )
    content = as_json(
        {
            'score': result.score,
            'summary': result.summary,
            'shown_to_user': 'The app already shows the full match card (score, reasons, red '
            'flags, skills) right above your answer.',
            'reply_with': f'Only one short question: {next_step}. Do not repeat the score, '
            'reasons, red flags or skills.',
        }
    )
    return ToolOutput(content, f'Analysed the match: {result.score}/100', data)


def keep_search_analysis(ctx: ToolContext, url: str, offer_id: int) -> None:
    """A search result analysed earlier in the chat was saved: keep that analysis with
    the offer, so its page shows the same card (unless it already has an analysis)."""
    found = ctx.search_analyses.get(url)
    if found is None or latest_analysis(ctx.db, ctx.user.id, offer_id) is not None:
        return
    result = AnalysisResult.model_validate(found['analysis'])
    store_analysis(ctx.db, ctx.user.id, offer_id, found.get('resume_id'), result)


# ---- write tools ---------------------------------------------------------------------------


def describe_save(ctx: ToolContext, args: TargetArgs) -> str:
    one_target(args)
    if args.search_result is not None:
        found = search_result(ctx, args.search_result)
        return f'Save "{found.title}" at {found.company_name} to your saved offers'
    offer = job_offers.get_job_offer(ctx.db, args.offer_id or 0, ctx.user.id)
    if offer is None:
        raise ToolError(f'No job offer with id {args.offer_id}')
    return f'Save "{offer.title}" at {offer.company_name} to your saved offers'


def save_offer(ctx: ToolContext, args: TargetArgs) -> ToolOutput:
    describe_save(ctx, args)  # the same checks again: the offer may be gone since
    offer_id = args.offer_id
    if args.search_result is not None:
        found = search_result(ctx, args.search_result)
        offer, created = add_private_offer(
            ctx.db, found, ctx.user.id, source=SourceKind.SEARCH, found_via=found.found_via
        )
        if created and settings.ai_enrich_saved_results:
            enrich_saved_offer(ctx.db, offer, ctx.provider, ctx.pages)
        offer_id = offer.id
        keep_search_analysis(ctx, str(found.url), offer.id)
    try:
        saved, created = applications.save_offer(ctx.db, ctx.user.id, offer_id or 0)
    except applications.OfferNotFoundError as err:
        raise ToolError(f'No job offer with id {offer_id}') from err
    title = f'"{saved.job_offer.title}" at {saved.job_offer.company_name}'
    note = f'Saved {title}' if created else f'{title} was already in your list'
    result = {'saved': created, 'offer_id': saved.job_offer.id, 'application_id': saved.id}
    return ToolOutput(as_json(result), note)


def describe_status(ctx: ToolContext, args: StatusArgs) -> str:
    try:
        found = applications.get_application(ctx.db, ctx.user.id, args.application_id)
    except applications.ApplicationNotFoundError as err:
        raise ToolError(f'No application with id {args.application_id}') from err
    if found.status == args.status:
        raise ToolError(f'The application already has status {args.status}')
    offer = found.job_offer
    return f'Move "{offer.title}" at {offer.company_name} from {found.status} to {args.status}'


def set_status(ctx: ToolContext, args: StatusArgs) -> ToolOutput:
    sentence = describe_status(ctx, args)
    applications.update_application(
        ctx.db, ctx.user.id, args.application_id, ApplicationUpdate(status=args.status)
    )
    note = sentence.replace('Move', 'Moved', 1)
    return ToolOutput(as_json({'application_id': args.application_id, 'status': args.status}), note)


def prepare_pasted_offer(ctx: ToolContext, args: PastedOfferArgs) -> PastedOfferArgs:
    """Read the pasted posting with the AI, like the Add an offer page, into a draft offer.

    Whatever the model put in `draft` is replaced: the fields come from the posting only.
    """
    text = ctx.pasted_text
    if text is None:
        raise ToolError('There is no pasted job posting. Ask the user to paste the whole posting.')
    text = text[:MAX_POSTING_TEXT]
    try:
        parsed = parse_offer(ctx.provider, text)
    except (AIProviderError, AIOutputError) as err:
        raise ToolError(f"Couldn't read the posting: {err}") from err
    url = str(args.url) if args.url else find_link(text)
    if url is None:
        raise ToolError(
            "The posting has no link. Ask the user for the offer's link, then call "
            'add_offer_from_text again with url.'
        )
    company = args.company_name or parsed.company_name
    if not company:
        raise ToolError(
            "The posting doesn't name the company. Ask the user for it, then call "
            'add_offer_from_text again with company_name.'
        )
    deadline = datetime.combine(parsed.deadline, time(), tzinfo=UTC) if parsed.deadline else None
    try:
        draft = JobOfferImport(
            title=parsed.title,
            company_name=company,
            url=url,  # type: ignore[arg-type]  # validated here
            location=parsed.location,
            experience_level=parsed.experience_level,
            employment_type=parsed.employment_type,
            deadline=deadline,
            technologies=parsed.technologies,
            description=text,
        )
    except ValidationError as err:
        raise ToolError(f'Wrong offer fields: {format_errors(err, root="offer")}') from err
    return args.model_copy(update={'draft': draft})


def describe_pasted_offer(ctx: ToolContext, args: PastedOfferArgs) -> str:
    draft = args.draft
    if draft is None:
        raise ToolError('The posting was not read yet')
    existing = ctx.db.scalar(
        select(JobOffer).where(
            JobOffer.url == normalize_url(str(draft.url)), job_offers.visible_to(ctx.user.id)
        )
    )
    if existing is not None:
        raise ToolError(
            f'This offer is already in the app: offer_id {existing.id}, '
            f'"{existing.title}" at {existing.company_name}'
        )
    details = [
        part for part in (draft.location, draft.experience_level, draft.employment_type) if part
    ]
    if draft.technologies:
        details.append(', '.join(draft.technologies[:8]))
    extra = f' ({"; ".join(details)})' if details else ''
    return f'Add "{draft.title}" at {draft.company_name}{extra} to your job offers'


def add_pasted_offer(ctx: ToolContext, args: PastedOfferArgs) -> ToolOutput:
    describe_pasted_offer(ctx, args)  # again: the same link may have been added since
    assert args.draft is not None
    offer, _ = add_private_offer(ctx.db, args.draft, ctx.user.id)
    note = f'Added "{offer.title}" at {offer.company_name} to your job offers'
    return ToolOutput(as_json({'offer_id': offer.id}), note, {'offer_id': offer.id})


# ---- the registry --------------------------------------------------------------------------

ALL_TOOLS: list[Tool[Any]] = [
    Tool(
        'get_profile',
        "The user's job profile: position, level, skills, cities.",
        NoArgs,
        get_profile,
    ),
    Tool('list_resumes', "The user's CVs with what was read from them.", NoArgs, get_resumes),
    Tool(
        'list_applications',
        "The user's applications and saved offers (status saved), newest first.",
        ApplicationsArgs,
        get_applications,
    ),
    Tool('get_stats', 'Application funnel and outcomes.', StatsArgs, get_stats),
    Tool(
        'get_calendar',
        'Interviews, applied dates, status changes and deadlines between two days.',
        CalendarArgs,
        get_calendar,
    ),
    Tool(
        'list_job_offers',
        'Job offers stored in the app (not a web search), newest first.',
        OffersArgs,
        get_offers,
    ),
    Tool(
        'get_job_offer',
        'One offer with its description: a stored offer (offer_id) or a result of the last '
        'search (search_result).',
        TargetArgs,
        get_offer,
    ),
    Tool(
        'search_jobs',
        'Search job boards on the web. Counts toward the daily search limit. '
        'Results are numbered; pass the number as search_result to get_job_offer, '
        'analyse_offer or save_offer.',
        SearchArgs,
        search_jobs,
    ),
    Tool(
        'analyse_offer',
        'Score how well the user matches an offer (0-100), with matched and missing skills.',
        AnalyseArgs,
        analyse,
    ),
    Tool(
        'save_offer',
        "Save an offer to the user's saved offers. The user must confirm it.",
        TargetArgs,
        save_offer,
        writes=True,
        describe=describe_save,
    ),
    Tool(
        'set_application_status',
        "Change an application's status. The user must confirm it.",
        StatusArgs,
        set_status,
        writes=True,
        describe=describe_status,
    ),
    Tool(
        'add_offer_from_text',
        'Add a job posting the user pasted in the chat to their job offers. The app reads '
        'the posting from their message: never copy it into the arguments. The user must '
        'confirm it.',
        PastedOfferArgs,
        add_pasted_offer,
        writes=True,
        describe=describe_pasted_offer,
        prepare=prepare_pasted_offer,
    ),
]
TOOLS = {tool.name: tool for tool in ALL_TOOLS}


def tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(tool.name, tool.description, inline_schema(tool.args.model_json_schema()))
        for tool in TOOLS.values()
    ]


def get_tool(name: str) -> Tool[Any]:
    if name not in TOOLS:
        raise ToolError(f'There is no tool called {name}')
    return TOOLS[name]
