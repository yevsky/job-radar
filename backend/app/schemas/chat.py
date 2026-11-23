from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.analysis import AnalysisResult

MAX_MESSAGE_CHARS = 12_000  # room for a pasted job posting (MAX_POSTING_CHARS)
TITLE_CHARS = 80  # chat_conversations.title is String(80)

MessageText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_CHARS)
]


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    created_at: datetime
    updated_at: datetime


class ChatMessageRead(BaseModel):
    """One line of the chat. Tool rows (role 'tool') are the grey 'Searched jobs: 8' lines."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    tool_name: str | None
    created_at: datetime
    analysis: AnalysisResult | None = None  # analyse_offer rows: shown as the match card


class ChatActionRead(BaseModel):
    """A change the assistant asked for; the frontend shows it with Confirm / Cancel."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tool: str
    summary: str
    status: str
    result: str | None
    created_at: datetime
    resolved_at: datetime | None


class ConversationDetail(ConversationRead):
    messages: list[ChatMessageRead]
    actions: list[ChatActionRead]


class MessageCreate(BaseModel):
    content: MessageText


class ConversationRename(BaseModel):
    """Body of PATCH /chat/{id}: the chat's new name."""

    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TITLE_CHARS)
    ]


class ChatReply(BaseModel):
    """The rows a message added (the user's own first), and the changes waiting for an OK."""

    messages: list[ChatMessageRead]
    pending_actions: list[ChatActionRead]


class ActionReply(BaseModel):
    action: ChatActionRead
    message: ChatMessageRead  # 'Saved ...' / 'Cancelled: ...', written by code
