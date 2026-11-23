from fastapi import APIRouter, HTTPException, status

from app.ai.base import AIProviderError
from app.db.dependencies import DbSession
from app.dependencies import AI, CurrentUser, EnabledSearchSources, Pages
from app.schemas.chat import (
    ActionReply,
    ChatActionRead,
    ChatMessageRead,
    ChatReply,
    ConversationDetail,
    ConversationRead,
    ConversationRename,
    MessageCreate,
)
from app.services import chat
from app.services.chat import (
    ActionClosedError,
    ActionNotFoundError,
    ConversationNotFoundError,
)

router = APIRouter(prefix='/chat', tags=['chat'])

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Conversation not found')


@router.get('', response_model=list[ConversationRead])
def read_conversations(db: DbSession, user: CurrentUser) -> list[ConversationRead]:
    """Your conversations with the assistant, the newest first."""
    rows = chat.list_conversations(db, user.id)
    return [ConversationRead.model_validate(row) for row in rows]


@router.post('', response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def start_conversation(db: DbSession, user: CurrentUser) -> ConversationRead:
    return ConversationRead.model_validate(chat.create_conversation(db, user.id))


@router.get('/{conversation_id}', response_model=ConversationDetail)
def read_conversation(conversation_id: int, db: DbSession, user: CurrentUser) -> ConversationDetail:
    """The messages (tool lines included) and every change the assistant asked for."""
    try:
        conversation = chat.get_conversation(db, user.id, conversation_id)
    except ConversationNotFoundError as err:
        raise NOT_FOUND from err
    return ConversationDetail.model_validate(conversation, from_attributes=True)


@router.patch('/{conversation_id}', response_model=ConversationRead)
def rename_conversation(
    conversation_id: int, data: ConversationRename, db: DbSession, user: CurrentUser
) -> ConversationRead:
    try:
        conversation = chat.rename_conversation(db, user.id, conversation_id, data.title)
    except ConversationNotFoundError as err:
        raise NOT_FOUND from err
    return ConversationRead.model_validate(conversation)


@router.delete('/{conversation_id}', status_code=status.HTTP_204_NO_CONTENT)
def remove_conversation(conversation_id: int, db: DbSession, user: CurrentUser) -> None:
    try:
        chat.delete_conversation(db, user.id, conversation_id)
    except ConversationNotFoundError as err:
        raise NOT_FOUND from err


@router.post('/{conversation_id}/messages', response_model=ChatReply)
def post_message(
    conversation_id: int,
    data: MessageCreate,
    db: DbSession,
    user: CurrentUser,
    ai: AI,
    sources: EnabledSearchSources,
    pages: Pages,
) -> ChatReply:
    """Send a message. The assistant may use tools; changes it asks for come back in
    `pending_actions` and happen only after POST .../actions/{id}/confirm."""
    try:
        rows, actions = chat.send_message(
            db, ai, user, sources, pages, conversation_id, data.content
        )
    except ConversationNotFoundError as err:
        raise NOT_FOUND from err
    except AIProviderError as err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            # The reason has no secrets ("gemini answered with HTTP 404") and says what to fix
            detail=f"The AI provider didn't answer: {err}",
        ) from err
    return ChatReply(
        messages=[ChatMessageRead.model_validate(row) for row in rows],
        pending_actions=[ChatActionRead.model_validate(action) for action in actions],
    )


def action_errors(err: Exception) -> HTTPException:
    if isinstance(err, ConversationNotFoundError):
        return NOT_FOUND
    if isinstance(err, ActionNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Action not found')
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT, detail='This action was already closed'
    )


@router.post('/{conversation_id}/actions/{action_id}/confirm', response_model=ActionReply)
def confirm(
    conversation_id: int,
    action_id: int,
    db: DbSession,
    user: CurrentUser,
    ai: AI,
    sources: EnabledSearchSources,
    pages: Pages,
) -> ActionReply:
    """Do the change. If it can't be done any more, the action becomes `failed`."""
    try:
        action, row = chat.confirm_action(db, ai, user, sources, pages, conversation_id, action_id)
    except (ConversationNotFoundError, ActionNotFoundError, ActionClosedError) as err:
        raise action_errors(err) from err
    return ActionReply(
        action=ChatActionRead.model_validate(action), message=ChatMessageRead.model_validate(row)
    )


@router.post('/{conversation_id}/actions/{action_id}/cancel', response_model=ActionReply)
def cancel(conversation_id: int, action_id: int, db: DbSession, user: CurrentUser) -> ActionReply:
    try:
        action, row = chat.cancel_action(db, user.id, conversation_id, action_id)
    except (ConversationNotFoundError, ActionNotFoundError, ActionClosedError) as err:
        raise action_errors(err) from err
    return ActionReply(
        action=ChatActionRead.model_validate(action), message=ChatMessageRead.model_validate(row)
    )
