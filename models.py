"""Database models for the aliyot auction.

Written against SQLAlchemy so the same code runs on SQLite locally and on
MySQL in production. Nothing here is dialect specific.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    select,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


# Occasion lifecycle. The public site reads these to decide what to show.
STATUS_UPCOMING = "upcoming"  # visible, bidding not open yet
STATUS_OPEN = "open"          # bidding accepted
STATUS_LOCKED = "locked"      # tab visible but blocked, used by Yom Kipur
STATUS_CLOSED = "closed"      # auction over, final amounts shown

# Moment groups used to break the item list into visual sections.
MOMENT_ARVIT = "Arvit"
MOMENT_SHACHARIT = "Shacharit"

# Storage is naive UTC everywhere and stays that way. This is only for the
# dates a visitor reads: the kehila is in Israel, so a time on the page is an
# Israeli one. Israel is UTC+3 in summer and UTC+2 in winter, and the auction
# sits either side of nothing in September, but the offset must never be
# written as a fixed number: it changes at the end of October.
DISPLAY_TZ = ZoneInfo("Asia/Jerusalem")


def to_display(moment):
    """A naive UTC datetime as it reads on a clock in Israel."""
    return moment.replace(tzinfo=timezone.utc).astimezone(DISPLAY_TZ)


def from_display(moment):
    """A naive Israel-local datetime as the naive UTC value we store.

    The admin types Israel time, because that is the only time the kehila
    thinks in. This is the one place that conversion happens on the way in.
    """
    return (
        moment.replace(tzinfo=DISPLAY_TZ)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )


def utcnow():
    """Server time, as naive UTC.

    All datetimes in this database are naive UTC. Mixing aware and naive values
    in a plain DATETIME column behaves differently on SQLite and on MySQL, and
    the auction deadline has to mean the same thing in both.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Occasion(db.Model):
    __tablename__ = "occasions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=STATUS_UPCOMING
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    opening_datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closing_datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    aliyot: Mapped[list["Aliyah"]] = relationship(
        back_populates="occasion",
        cascade="all, delete-orphan",
        order_by="Aliyah.display_order",
    )

    def is_bidding_open(self, now):
        """Whether a bid may be accepted right now, by server time.

        The window is decided here and nowhere else. The countdown on the page
        is decoration; this is the rule.
        """
        if self.status != STATUS_OPEN:
            return False
        if self.opening_datetime is not None and now < self.opening_datetime:
            return False
        if self.closing_datetime is not None and now >= self.closing_datetime:
            return False
        return True

    def closed_reason(self, now):
        """Why bidding is not accepted, phrased for the visitor.

        Every date here goes through to_display first. The stored value is UTC,
        and printing that raw told an Israeli visitor a time three hours behind
        the real one.
        """
        if self.status == STATUS_LOCKED:
            return "Esta ocasião ainda não foi liberada."
        if self.status == STATUS_CLOSED:
            return "O leilão está encerrado."
        if self.closing_datetime is not None and now >= self.closing_datetime:
            return "O leilão encerrou em {:%d/%m/%Y às %H:%M} (horário de Israel).".format(
                to_display(self.closing_datetime)
            )
        if self.opening_datetime is not None and now < self.opening_datetime:
            return "O leilão abre em {:%d/%m/%Y às %H:%M} (horário de Israel).".format(
                to_display(self.opening_datetime)
            )
        return "O leilão ainda não está aberto."

    def __repr__(self):
        return f"<Occasion {self.slug} {self.status}>"


class Aliyah(db.Model):
    __tablename__ = "aliyot"
    __table_args__ = (
        UniqueConstraint("occasion_id", "display_order", name="uq_aliyah_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    occasion_id: Mapped[int] = mapped_column(
        ForeignKey("occasions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Smaller line under the name on the card. Carries the Portuguese reading of
    # a Hebrew title, so "Pticha" can be the name without losing "Abertura do Aron".
    subtitle: Mapped[str | None] = mapped_column(String(120), nullable=True)
    moment_group: Mapped[str] = mapped_column(String(40), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    image_key: Mapped[str] = mapped_column(String(40), nullable=False)

    # An item withdrawn from the auction. The row is never deleted: bids on it
    # are history and a withdrawal can be undone. False hides the card, refuses
    # new bids, and marks the row in the panel.
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1")
    )

    # Present in the schema and in the admin UI, intentionally unused for now.
    min_bid: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    max_bid: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    occasion: Mapped["Occasion"] = relationship(back_populates="aliyot")
    bids: Mapped[list["Bid"]] = relationship(
        back_populates="aliyah",
        cascade="all, delete-orphan",
        order_by="Bid.amount.desc()",
    )

    @property
    def label(self):
        """Name as it reads away from the card.

        On the card the image and the position in the page say which opening is
        which. In an email or a confirmation message there is neither, so the
        subtitle is spelled out.
        """
        if self.subtitle:
            return f"{self.name} - {self.subtitle}"
        return self.name

    def __repr__(self):
        return f"<Aliyah {self.display_order} {self.name}>"


class Bid(db.Model):
    __tablename__ = "bids"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    aliyah_id: Mapped[int] = mapped_column(
        ForeignKey("aliyot.id", ondelete="CASCADE"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(40), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    # A cancelled bid is never deleted. It stops counting towards the aliyah's
    # highest and stays in the history, because the record is what settles an
    # argument later about what was offered and what was taken back.
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    aliyah: Mapped["Aliyah"] = relationship(back_populates="bids")

    @property
    def is_cancelled(self):
        return self.cancelled_at is not None

    def __repr__(self):
        state = " cancelled" if self.is_cancelled else ""
        return f"<Bid {self.aliyah_id} {self.amount}{state}>"


def highest_bids_for_occasion(occasion_id):
    """Return {aliyah_id: highest amount} for one occasion, in a single query.

    Aliyot with no bids are absent from the mapping. The highest bid is always
    derived from the bids table, never cached on the aliyah row, so it cannot
    drift out of sync with the stored history. Cancelled bids are excluded, so
    cancelling one hands the aliyah back to the bid below it.
    """
    rows = db.session.execute(
        select(Bid.aliyah_id, func.max(Bid.amount))
        .join(Aliyah, Aliyah.id == Bid.aliyah_id)
        .where(Aliyah.occasion_id == occasion_id, Bid.cancelled_at.is_(None))
        .group_by(Bid.aliyah_id)
    ).all()
    return {aliyah_id: amount for aliyah_id, amount in rows}


def leading_bids_for_occasion(occasion_id):
    """Return {aliyah_id: Bid} for the bid currently winning each aliyah.

    The admin needs the person, not just the figure. Ties cannot happen: a bid
    has to be strictly greater than the one before it, so the maximum amount
    belongs to exactly one row.
    """
    bids = db.session.scalars(
        select(Bid)
        .join(Aliyah, Aliyah.id == Bid.aliyah_id)
        .where(Aliyah.occasion_id == occasion_id, Bid.cancelled_at.is_(None))
        .order_by(Bid.aliyah_id, Bid.amount)
    ).all()
    # Ordered ascending, so the last one written for each aliyah is the highest.
    return {bid.aliyah_id: bid for bid in bids}
