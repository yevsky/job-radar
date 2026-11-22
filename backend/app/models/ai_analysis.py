from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AiAnalysis(Base):
    """One match analysis of an offer for a user. Every run adds a row; the newest is shown."""

    __tablename__ = 'ai_analyses'
    __table_args__ = (
        CheckConstraint('score BETWEEN 0 AND 100', name='ck_ai_analyses_score_0_100'),
        Index(
            'ix_ai_analyses_user_id_job_offer_id_created_at',
            'user_id',
            'job_offer_id',
            'created_at',
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    job_offer_id: Mapped[int] = mapped_column(
        ForeignKey('job_offers.id', ondelete='CASCADE'), index=True, nullable=False
    )
    # The CV the model saw; deleting the CV keeps the analysis (it just forgets which CV)
    resume_id: Mapped[int | None] = mapped_column(ForeignKey('resumes.id', ondelete='SET NULL'))
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    breakdown: Mapped[dict[str, int]] = mapped_column(JSONB, nullable=False)  # ScoreBreakdown
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    red_flags: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    matched_skills: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    missing_skills: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # 'ollama'
    model: Mapped[str] = mapped_column(String(100), nullable=False)  # 'qwen2.5:3b'
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
