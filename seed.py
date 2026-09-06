"""Create the database tables and load the initial occasions and aliyot.

Safe to run more than once: existing rows are left untouched.

    python seed.py
"""

from decimal import Decimal

from sqlalchemy import inspect, select, text

from app import create_app
from models import (
    MOMENT_ARVIT,
    MOMENT_SHACHARIT,
    STATUS_LOCKED,
    STATUS_UPCOMING,
    Aliyah,
    Occasion,
    db,
)

# Starting minimum bid in NIS, by image group. See rule 11 in CLAUDE.md.
# The value is stored on each aliyah row, so the admin can later raise or lower
# a single item without touching the others.
MIN_BID_BY_IMAGE_KEY = {
    "pticha": Decimal("400"),
    "aliyah": Decimal("400"),
    "hagbaa": Decimal("200"),
    "glila": Decimal("200"),
}

# Rosh Hashana, first day only. Order comes straight from CLAUDE.md.
#
# The card shows the Hebrew title and, where there is one, the Portuguese
# reading under it in smaller type. The seven aliyot drop the word "Aliat":
# the tier they sit in already says they are aliyot.
#
#   (display_order, moment, name, subtitle, image_key)
ROSH_HASHANA_ALIYOT = [
    (1, MOMENT_ARVIT, "Ptichat Heichal (Parnassa)", "Abertura do Aron", "pticha"),
    (2, MOMENT_SHACHARIT, "Ptichat Heichal", "Abertura do Aron", "pticha"),
    (3, MOMENT_SHACHARIT, "Cohen", None, "aliyah"),
    (4, MOMENT_SHACHARIT, "Levi", None, "aliyah"),
    (5, MOMENT_SHACHARIT, "Shlishi", None, "aliyah"),
    (6, MOMENT_SHACHARIT, "Revii", None, "aliyah"),
    (7, MOMENT_SHACHARIT, "Hamishi", None, "aliyah"),
    (8, MOMENT_SHACHARIT, "Shishi", None, "aliyah"),
    (9, MOMENT_SHACHARIT, "Maftir", None, "aliyah"),
    (10, MOMENT_SHACHARIT, "Hagbaa 1", None, "hagbaa"),
    (11, MOMENT_SHACHARIT, "Glila 1", None, "glila"),
    (12, MOMENT_SHACHARIT, "Hagbaa 2", None, "hagbaa"),
    (13, MOMENT_SHACHARIT, "Glila 2", None, "glila"),
]

# Items withdrawn from the auction, keyed by (occasion slug, aliyah name).
# The row stays in the list above so its display_order stays taken and putting
# it back is one line. Withdrawing does NOT delete anything: bids already
# placed on it are kept, and the panel still shows them.
#
# Shishi was withdrawn on 2026-09-06, with the auction already open, because
# the kehila decided not to sell it.
WITHDRAWN = {
    ("rosh-hashana", "Shishi"),
}


# Yom Kipur exists as a locked tab. Its item list has not been defined yet,
# so no aliyot are created for it.
OCCASIONS = [
    {
        "slug": "rosh-hashana",
        "name": "Rosh Hashana",
        "status": STATUS_UPCOMING,
        "display_order": 1,
        "aliyot": ROSH_HASHANA_ALIYOT,
    },
    {
        "slug": "yom-kipur",
        "name": "Yom Kipur",
        "status": STATUS_LOCKED,
        "display_order": 2,
        "aliyot": [],
    },
]


def seed():
    created_occasions = 0
    created_aliyot = 0
    renamed_aliyot = 0
    filled_minimums = 0
    withdrawn_changed = 0

    for spec in OCCASIONS:
        occasion = db.session.scalar(
            select(Occasion).where(Occasion.slug == spec["slug"])
        )
        if occasion is None:
            occasion = Occasion(
                slug=spec["slug"],
                name=spec["name"],
                status=spec["status"],
                display_order=spec["display_order"],
            )
            db.session.add(occasion)
            db.session.flush()
            created_occasions += 1

        for order, moment, name, subtitle, image_key in spec["aliyot"]:
            active = (spec["slug"], name) not in WITHDRAWN
            exists = db.session.scalar(
                select(Aliyah).where(
                    Aliyah.occasion_id == occasion.id,
                    Aliyah.display_order == order,
                )
            )
            if exists is None:
                db.session.add(
                    Aliyah(
                        occasion_id=occasion.id,
                        display_order=order,
                        moment_group=moment,
                        name=name,
                        subtitle=subtitle,
                        image_key=image_key,
                        is_active=active,
                        min_bid=MIN_BID_BY_IMAGE_KEY[image_key],
                    )
                )
                created_aliyot += 1
                continue

            # Wording is decided in CLAUDE.md, not in the admin, so a renamed
            # item is carried over to rows that already exist.
            if exists.name != name or exists.subtitle != subtitle:
                exists.name = name
                exists.subtitle = subtitle
                renamed_aliyot += 1

            # Withdrawal is decided here, not in the admin, so a redeploy
            # carries it to a row that already exists, and putting a name back
            # in the auction is done by removing it from WITHDRAWN.
            if exists.is_active != active:
                exists.is_active = active
                withdrawn_changed += 1

            if exists.min_bid is None:
                # Only fill an empty minimum. An admin who changed a value must
                # not have it reset by the next deploy.
                exists.min_bid = MIN_BID_BY_IMAGE_KEY[image_key]
                filled_minimums += 1

    db.session.commit()
    return (
        created_occasions,
        created_aliyot,
        renamed_aliyot,
        filled_minimums,
        withdrawn_changed,
    )


def ensure_columns():
    """Add columns that a database created by an older deploy does not have.

    db.create_all() creates missing TABLES and never alters an existing one, so
    a column added to a model after the first deploy has to be added by hand.
    This runs on every boot, checks before it acts, and is therefore safe to
    repeat. The one statement below is accepted by both SQLite and MySQL.
    """
    columns = {c["name"] for c in inspect(db.engine).get_columns("aliyot")}
    if "is_active" not in columns:
        with db.engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE aliyot ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1")
            )
        print("Added column aliyot.is_active.")


def main():
    app = create_app()
    with app.app_context():
        db.create_all()
        ensure_columns()
        occasions, aliyot, renamed, minimums, withdrawn = seed()
        print("Tables ready.")
        print(f"Occasions created: {occasions}")
        print(f"Aliyot created: {aliyot}")
        print(f"Aliyot renamed: {renamed}")
        print(f"Minimum bids filled: {minimums}")
        print(f"Withdrawal flags changed: {withdrawn}")


if __name__ == "__main__":
    main()
