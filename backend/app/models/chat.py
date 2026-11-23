"""The AI assistant's conversations: messages, and the changes waiting for the user's OK."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChatRole(StrEnum):
    USER = 'user'
    ASSISTANT = 'assistant'
    TOOL = 'tool'  # one tool call: `content` is the line the user sees, `data` the rest


class ActionStatus(StrEnum):
    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    CANCELLED = 'cancelled'
    FAILED = 'failed'


def now() -> datetime:
    return datetime.now(UTC)


class Conversation(Base):
    __tablename__ = 'chat_conversations'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), index=True, nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(80))  # the first message, cut
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    messages: Mapped[list['ConversationMessage']] = relationship(
        cascade='all, delete-orphan', order_by='ConversationMessage.id'
    )
    actions: Mapped[list['ChatAction']] = relationship(
        cascade='all, delete-orphan', order_by='ChatAction.id'
    )


class ConversationMessage(Base):
    __tablename__ = 'chat_messages'

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey('chat_conversations.id', ondelete='CASCADE'), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # ChatRole
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(50))
    # tool rows: call id, arguments, the result the model read, search results
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    @property
    def analysis(self) -> dict[str, Any] | None:
        """The match card of an analyse_offer row, for the chat to show."""
        if self.tool_name != 'analyse_offer' or not self.data:
            return None
        found = self.data.get('analysis')
        return found if isinstance(found, dict) else None


class ChatAction(Base):
    """A change the assistant asked for. It runs only when the user confirms it."""

    __tablename__ = 'chat_actions'

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey('chat_conversations.id', ondelete='CASCADE'), index=True, nullable=False
    )
    tool: Mapped[str] = mapped_column(String(50), nullable=False)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)  # 'Move ... from applied to ...'
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ActionStatus.PENDING
    )  # ActionStatus
    result: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
