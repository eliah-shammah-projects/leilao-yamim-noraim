"""Create the database tables and load the initial occasions and aliyot.

Safe to run more than once: existing rows are left untouched.

    python seed.py
"""

from decimal import Decimal

from sqlalchemy import select

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

            if exists.min_bid is None:
                # Only fill an empty minimum. An admin who changed a value must
                # not have it reset by the next deploy.
                exists.min_bid = MIN_BID_BY_IMAGE_KEY[image_key]
                filled_minimums += 1

    db.session.commit()
    return created_occasions, created_aliyot, renamed_aliyot, filled_minimums


def main():
    app = create_app()
    with app.app_context():
        db.create_all()
        occasions, aliyot, renamed, minimums = seed()
        print("Tables ready.")
        print(f"Occasions created: {occasions}")
        print(f"Aliyot created: {aliyot}")
        print(f"Aliyot renamed: {renamed}")
        print(f"Minimum bids filled: {minimums}")


if __name__ == "__main__":
    main()
