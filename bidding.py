"""Bid validation and recording.

Every rule here runs on the server, against the database, inside one
transaction. Nothing is trusted from the page the visitor was looking at: by
the time a form arrives, the highest bid may already have moved.
"""

import re
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select

from models import Aliyah, Bid, Occasion, db

# Numeric(10, 2) tops out below one hundred million. Refuse anything near it
# rather than let the database raise on overflow.
MAX_AMOUNT = Decimal("9999999")

# Raising a bid moves it by at least this much. Asked for 2026-09-09: an
# aliyah at 350 is next taken at 450, not at 351. It only applies once there
# is a bid to beat; the first bid on an aliyah still answers to min_bid alone.
MIN_INCREMENT = Decimal("100")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]+$")

# "1.200" and "1.200,50": dots only count as thousands separators when every
# group has exactly three digits, so "400.50" is never read as 40050.
THOUSANDS_RE = re.compile(r"^\d{1,3}(\.\d{3})+(,\d{1,2})?$")


class BidRejected(Exception):
    """A bid that failed a rule. The message is shown to the visitor."""


def parse_amount(raw):
    text = (raw or "").strip().replace(" ", "").replace("NIS", "").replace("₪", "")
    if not text:
        raise BidRejected("Informe o valor do lance.")

    if THOUSANDS_RE.match(text):
        text = text.replace(".", "")
    text = text.replace(",", ".")

    try:
        amount = Decimal(text)
    except InvalidOperation:
        raise BidRejected("Valor inválido. Digite apenas números, por exemplo 1200.")

    if not amount.is_finite():
        raise BidRejected("Valor inválido. Digite apenas números, por exemplo 1200.")
    if amount <= 0:
        raise BidRejected("O valor precisa ser maior que zero.")
    if amount > MAX_AMOUNT:
        raise BidRejected("Valor alto demais. Confira o número digitado.")

    return amount.quantize(Decimal("0.01"))


def clean_contact(full_name, email, phone):
    full_name = (full_name or "").strip()
    email = (email or "").strip().lower()
    phone = (phone or "").strip()

    if len(full_name) < 2:
        raise BidRejected("Informe seu nome completo.")
    if not EMAIL_RE.match(email):
        raise BidRejected("Informe um e-mail válido.")
    if len(re.sub(r"\D", "", phone)) < 8:
        raise BidRejected("Informe um telefone válido, com DDD.")

    return full_name, email, phone


def place_bid(aliyah_id, full_name, email, phone, amount_raw, now, format_amount):
    """Validate and record one bid. Returns the saved Bid.

    Raises BidRejected with a message meant for the visitor.

    The row lock is what makes concurrent bids safe: two people offering the
    same amount at the same instant are serialized by the database, so the
    second one reads the first one's bid and is rejected. SQLite ignores the
    lock, so this guarantee is real only on MySQL.
    """
    amount = parse_amount(amount_raw)
    full_name, email, phone = clean_contact(full_name, email, phone)

    try:
        aliyah = db.session.execute(
            select(Aliyah).where(Aliyah.id == aliyah_id).with_for_update()
        ).scalar_one_or_none()
        if aliyah is None:
            raise BidRejected("Aliyah não encontrada.")

        # A page opened before the item was withdrawn can still post to it.
        if not aliyah.is_active:
            raise BidRejected(
                f"{aliyah.label} não faz mais parte do leilão."
            )

        occasion = db.session.get(Occasion, aliyah.occasion_id)
        if not occasion.is_bidding_open(now):
            raise BidRejected(occasion.closed_reason(now))

        # A cancelled bid is not a bid. It neither wins the aliyah nor sets
        # the floor the next person has to clear.
        current_highest = db.session.execute(
            select(func.max(Bid.amount)).where(
                Bid.aliyah_id == aliyah.id, Bid.cancelled_at.is_(None)
            )
        ).scalar()

        if current_highest is None:
            minimum = aliyah.min_bid
            if minimum is not None and amount < minimum:
                raise BidRejected(
                    f"O lance mínimo para {aliyah.label} é "
                    f"{format_amount(minimum)}."
                )
        elif amount < current_highest + MIN_INCREMENT:
            raise BidRejected(
                f"O maior lance para {aliyah.label} já é "
                f"{format_amount(current_highest)}. Apenas lances de "
                f"{format_amount(MIN_INCREMENT)} a mais que o anterior estão "
                f"sendo aceitos: ofereça "
                f"{format_amount(current_highest + MIN_INCREMENT)} ou mais."
            )

        bid = Bid(
            aliyah_id=aliyah.id,
            full_name=full_name,
            email=email,
            phone=phone,
            amount=amount,
            created_at=now,
        )
        db.session.add(bid)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return bid
