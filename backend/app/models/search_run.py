from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SearchRun(Base):
    """One search a user ran: when, and how many results it returned. Never the results."""

    __tablename__ = 'search_runs'
    __table_args__ = (Index('ix_search_runs_user_id_created_at', 'user_id', 'created_at'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    result_count: Mapped[int]
