"""The AI assistant: stored conversations and the loop that lets the model use the app's tools.

One user message runs a loop of at most MAX_STEPS model calls. Each time the model answers
with text (the loop ends) or with tool calls. A read tool runs at once and its result goes
back to the model. A write tool doesn't run: it becomes a pending ChatAction (one per call, so
"move both to interview" makes two), the loop ends,
and the change happens only when the user confirms it (confirm_action).
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.base import AIProvider, ChatMessage, ToolCall, ToolMessage, ToolResult, ToolTurn
from app.ai.prompts import assistant_system_message
from app.models import ChatAction, Conversation, ConversationMessage, User
from app.models.chat import ActionStatus, ChatRole
from app.schemas.search import SearchResult
from app.search_sources.base import SearchSource
from app.search_sources.page_reader import PageReader
from app.services.chat_tools import ToolContext, ToolError, as_json, get_tool, tool_specs

MAX_STEPS = 6  # model calls per user message
MAX_HISTORY = 30  # stored rows sent back to the model (tool rows count too)
MAX_RESULT_CHARS = 6_000  # one tool result, as the model reads it
TITLE_CHARS = 80

STEP_LIMIT_TEXT = (
    'I used too many steps on this one and stopped. Try asking in a simpler way, '
    'or one thing at a time.'
)
CONFIRM_TEXT = 'Please confirm or cancel the change below.'
MAX_PENDING = 10  # changes waiting for the user after one message
TOO_MANY_CHANGES = f'At most {MAX_PENDING} changes can wait for the user at once.'
ALREADY_ASKED = 'This change is already waiting for the user.'


class ConversationNotFoundError(Exception):
    """No such conversation, or it belongs to someone else."""


class ActionNotFoundError(Exception):
    """No such action in this conversation."""


class ActionClosedError(Exception):
    """The action was already confirmed, cancelled or failed."""


def now() -> datetime:
    return datetime.now(UTC)


# ---- conversations -------------------------------------------------------------------------


def list_conversations(db: Session, user_id: int) -> list[Conversation]:
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        )
    )


def create_conversation(db: Session, user_id: int) -> Conversation:
    conversation = Conversation(user_id=user_id)
    db.add(conversation)
    db.commit()
    return conversation


def get_conversation(db: Session, user_id: int, conversation_id: int) -> Conversation:
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user_id
        )
    )
    if conversation is None:
        raise ConversationNotFoundError
    return conversation


def rename_conversation(
    db: Session, user_id: int, conversation_id: int, title: str
) -> Conversation:
    """A new name; updated_at stays, so renaming doesn't move the chat to the top."""
    conversation = get_conversation(db, user_id, conversation_id)
    conversation.title = title
    db.commit()
    return conversation


def delete_conversation(db: Session, user_id: int, conversation_id: int) -> None:
    db.delete(get_conversation(db, user_id, conversation_id))
    db.commit()


def add_row(
    conversation: Conversation,
    role: ChatRole,
    content: str,
    tool_name: str | None = None,
    data: dict[str, Any] | None = None,
) -> ConversationMessage:
    row = ConversationMessage(role=role, content=content, tool_name=tool_name, data=data)
    conversation.messages.append(row)
    return row


# ---- what the model sees -------------------------------------------------------------------


def window(rows: list[ConversationMessage]) -> list[ConversationMessage]:
    """The newest MAX_HISTORY rows, starting at a user message (models expect that)."""
    recent = rows[-MAX_HISTORY:]
    for index, row in enumerate(recent):
        if row.role == ChatRole.USER:
            return recent[index:]
    return []


def replay(rows: list[ConversationMessage]) -> list[ToolMessage]:
    """Stored rows as the model's history. Tool rows that follow each other become one
    tool turn (the calls) and its results, as if the model had called them together."""
    history: list[ToolMessage] = []
    calls: list[ToolCall] = []
    results: list[ToolResult] = []
    for row in [*rows, None]:
        if row is not None and row.role == ChatRole.TOOL and row.data is not None:
            call_id = str(row.data['call_id'])
            calls.append(
                ToolCall(
                    call_id,
                    row.tool_name or '',
                    row.data.get('arguments', {}),
                    row.data.get('extra'),  # e.g. Gemini's thought signature
                )
            )
            results.append(
                ToolResult(
                    call_id, str(row.data.get('result', '')), row.data.get('is_error', False)
                )
            )
            continue
        if calls:
            history.append(ToolTurn(tool_calls=calls))
            history.extend(results)
            calls, results = [], []
        if row is not None and row.role in (ChatRole.USER, ChatRole.ASSISTANT):
            history.append(ChatMessage(role=row.role, content=row.content))  # type: ignore[arg-type]
    return history


def last_search(conversation: Conversation) -> list[SearchResult]:
    """The results of the newest search in the conversation, for 'save result 3'."""
    for row in reversed(conversation.messages):
        if row.tool_name == 'search_jobs' and row.data and 'results' in row.data:
            return [SearchResult.model_validate(r) for r in row.data['results']]
    return []


def tool_context(
    db: Session,
    user: User,
    provider: AIProvider,
    sources: list[SearchSource],
    pages: PageReader | None,
    conversation: Conversation,
) -> ToolContext:
    analyses = {
        str(row.data['search_url']): row.data
        for row in conversation.messages
        if row.tool_name == 'analyse_offer' and row.data and 'search_url' in row.data
    }
    return ToolContext(db, user, provider, sources, pages, last_search(conversation), analyses)


# ---- the loop ------------------------------------------------------------------------------


def run_call(
    ctx: ToolContext,
    conversation: Conversation,
    call: ToolCall,
    pending: list[ChatAction],
) -> tuple[ConversationMessage, ToolResult, ChatAction | None]:
    """Run one tool call (or turn a write call into a pending action) and store it as a row."""
    action = None
    data: dict[str, Any] | None = None
    try:
        tool = get_tool(call.name)
        args = tool.parse(call.arguments)
        if tool.writes:
            if len(pending) >= MAX_PENDING:
                raise ToolError(TOO_MANY_CHANGES)
            arguments = args.model_dump(mode='json')
            if any(a.tool == tool.name and a.arguments == arguments for a in pending):
                raise ToolError(ALREADY_ASKED)
            assert tool.describe is not None
            summary = tool.describe(ctx, args)
            action = ChatAction(tool=tool.name, arguments=arguments, summary=summary)
            conversation.actions.append(action)
            content = as_json({'waiting_for_user': summary})
            note = 'Prepared a change for you to confirm'
        else:
            output = tool.run(ctx, args)
            content, note, data = output.content, output.note, output.data
        is_error = False
    except ToolError as err:
        content, note, is_error = str(err), f'{call.name}: {err}', True

    content = content[:MAX_RESULT_CHARS]
    row_data = {
        'call_id': call.id,
        'arguments': call.arguments,
        'result': content,
        'is_error': is_error,
        **(data or {}),
    }
    if call.extra:
        row_data['extra'] = call.extra
    row = add_row(conversation, ChatRole.TOOL, note, tool_name=call.name, data=row_data)
    return row, ToolResult(call.id, content, is_error), action


def close_pending(conversation: Conversation, why: str) -> None:
    for action in conversation.actions:
        if action.status == ActionStatus.PENDING:
            action.status = ActionStatus.CANCELLED
            action.result = why
            action.resolved_at = now()


def send_message(
    db: Session,
    provider: AIProvider,
    user: User,
    sources: list[SearchSource],
    pages: PageReader | None,
    conversation_id: int,
    content: str,
) -> tuple[list[ConversationMessage], list[ChatAction]]:
    """Add the user's message and let the model answer, using tools.

    Returns the new rows (the user's message first) and the actions waiting for confirmation.
    Rows are saved even if the provider fails half way (AIProviderError goes to the caller).
    """
    conversation = get_conversation(db, user.id, conversation_id)
    close_pending(conversation, 'The user wrote a new message instead')
    if conversation.title is None:
        conversation.title = content[:TITLE_CHARS]
    added = [add_row(conversation, ChatRole.USER, content)]
    db.commit()

    ctx = tool_context(db, user, provider, sources, pages, conversation)
    history: list[ToolMessage] = [
        assistant_system_message(now().date()),
        *replay(window(conversation.messages)),
    ]
    specs = tool_specs()
    pending: list[ChatAction] = []
    try:
        for _ in range(MAX_STEPS):
            turn = provider.chat_tools(history, specs)
            if not turn.tool_calls:
                added.append(add_row(conversation, ChatRole.ASSISTANT, turn.text))
                break
            history.append(turn)
            for call in turn.tool_calls:
                row, result, action = run_call(ctx, conversation, call, pending)
                added.append(row)
                history.append(result)
                if action is not None:
                    pending.append(action)
            if pending:
                added.append(add_row(conversation, ChatRole.ASSISTANT, CONFIRM_TEXT))
                break
        else:
            added.append(add_row(conversation, ChatRole.ASSISTANT, STEP_LIMIT_TEXT))
    finally:
        conversation.updated_at = now()
        db.commit()
    return added, pending


# ---- confirm or cancel ---------------------------------------------------------------------


def get_action(conversation: Conversation, action_id: int) -> ChatAction:
    for action in conversation.actions:
        if action.id == action_id:
            if action.status != ActionStatus.PENDING:
                raise ActionClosedError
            return action
    raise ActionNotFoundError


def confirm_action(
    db: Session,
    provider: AIProvider,
    user: User,
    sources: list[SearchSource],
    pages: PageReader | None,
    conversation_id: int,
    action_id: int,
) -> tuple[ChatAction, ConversationMessage]:
    """Run the change the user confirmed. The answer is written by code, not by the model."""
    conversation = get_conversation(db, user.id, conversation_id)
    action = get_action(conversation, action_id)
    ctx = tool_context(db, user, provider, sources, pages, conversation)
    tool = get_tool(action.tool)
    try:
        output = tool.run(ctx, tool.parse(action.arguments))  # checks everything again
        action.status, action.result = ActionStatus.CONFIRMED, output.note
        text = f'Done: {output.note}.'
    except ToolError as err:
        action.status, action.result = ActionStatus.FAILED, str(err)
        text = f"That didn't work: {err}"
    action.resolved_at = now()
    row = add_row(conversation, ChatRole.ASSISTANT, text)
    conversation.updated_at = now()
    db.commit()
    return action, row


def cancel_action(
    db: Session, user_id: int, conversation_id: int, action_id: int
) -> tuple[ChatAction, ConversationMessage]:
    conversation = get_conversation(db, user_id, conversation_id)
    action = get_action(conversation, action_id)
    action.status, action.result, action.resolved_at = ActionStatus.CANCELLED, None, now()
    row = add_row(conversation, ChatRole.ASSISTANT, f'Cancelled: {action.summary}.')
    conversation.updated_at = now()
    db.commit()
    return action, row
