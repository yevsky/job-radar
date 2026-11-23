from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SearchSourceSwitch(Base):
    """An admin's on/off switch for one search source, for every user at once.

    SEARCH_SOURCES in .env says which sources the server *can* use (they have API keys);
    this table says which of them are switched on right now. A source with no row is on,
    so a new source works without anyone touching the table.
    """

    __tablename__ = 'search_source_switches'

    name: Mapped[str] = mapped_column(String(50), primary_key=True)  # 'tavily', 'jsearch'
    is_enabled: Mapped[bool] = mapped_column(nullable=False)
    # The admin who flipped it last; kept as NULL if that account is deleted
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
