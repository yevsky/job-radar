from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Resume(Base):
    """One of a user's CVs: its text and what the AI read from it. The PDF itself is not kept."""

    __tablename__ = 'resumes'
    __table_args__ = (UniqueConstraint('user_id', 'label', name='uq_resumes_user_id_label'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), index=True, nullable=False
    )
    label: Mapped[str] = mapped_column(String(100), nullable=False)  # 'Backend CV'
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)  # the text read from the PDF
    # ResumeExtracted as JSON; None until the AI has read the CV (or if it failed)
    extracted: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    extracted_with: Mapped[str | None] = mapped_column(String(100))  # 'ollama/qwen2.5:3b'
    # ResumeInsights as JSON: the career snapshot shown on the profile page; None until made
    insights: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    insights_with: Mapped[str | None] = mapped_column(String(100))
    applied_to_profile_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
