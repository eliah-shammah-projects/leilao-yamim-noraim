"""Flask application for the aliyot auction."""

import os
from datetime import datetime, timedelta
from functools import wraps
from itertools import groupby

from flask import (
    Flask,
    abort,
    flash,
    get_flashed_messages,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import func, select

import mailer
from bidding import BidRejected, place_bid
from config import Config
from models import (
    STATUS_CLOSED,
    STATUS_LOCKED,
    STATUS_OPEN,
    Aliyah,
    Bid,
    Occasion,
    db,
    from_display,
    highest_bids_for_occasion,
    leading_bids_for_occasion,
    to_display,
    utcnow,
)

# Panel access levels. Both reach the same data; only one of them can change
# anything.
ROLE_ADMIN = "admin"
ROLE_VIEWER = "viewer"


def func_count():
    return func.count(Bid.id)

IMAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "images")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

# Plain Portuguese under each moment heading. Not everyone in the kehila reads
# "Arvit" and "Shacharit" as night and morning at a glance.
MOMENT_CAPTIONS = {
    "Arvit": "Noite",
    "Shacharit": "Manhã",
}

# Inside one moment the items are split into tiers so that the opening, the
# aliyot and hagbaa/glila each sit on their own row instead of running together
# in one flat grid. A tier is a break in the layout only: no heading and no
# rule. The blue rule stays where it belongs, between night and morning.
TIER_BY_IMAGE_KEY = {
    "pticha": "pticha",
    "aliyah": "aliyah",
    "hagbaa": "hagbaa-glila",
    "glila": "hagbaa-glila",
}


def tier_of(aliyah):
    return TIER_BY_IMAGE_KEY.get(aliyah.image_key, aliyah.image_key)


def format_nis(amount):
    """Format an amount as shekels, thousands separated by a dot.

    NIS, not ILS. ILS is the bank code; NIS is what the currency is called.
    """
    if amount is None:
        return ""
    return "{:,.0f}".format(amount).replace(",", ".") + " NIS"


def find_image(key):
    """URL of static/images/<key>.<ext>, or None when the file is not there.

    Missing images are not an error. The page falls back to a styled
    placeholder, so the design can be built and reviewed before the real
    photographs exist.
    """
    for extension in IMAGE_EXTENSIONS:
        if os.path.exists(os.path.join(IMAGE_DIR, key + extension)):
            return url_for("static", filename="images/" + key + extension)
    return None


def parse_israel_datetime(text):
    """Read a datetime-local field, typed in Israel time, as naive UTC."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        typed = datetime.strptime(text, "%Y-%m-%dT%H:%M")
    except ValueError:
        raise ValueError("Data invalida.")
    return from_display(typed)


def own_cancellable_bids(now, window_minutes):
    """Return {aliyah_id: Bid} for bids this browser placed and may still undo.

    Identity on the public site is the session and nothing else: there is no
    login, so "your bid" means a bid placed from this browser. Anyone who
    changes device or clears their cookies loses the ability, which is
    understood and accepted.
    """
    ids = session.get("my_bids") or []
    if not ids:
        return {}

    cutoff = now - timedelta(minutes=window_minutes)
    bids = db.session.scalars(
        select(Bid)
        .where(
            Bid.id.in_(ids),
            Bid.cancelled_at.is_(None),
            Bid.created_at >= cutoff,
        )
        .order_by(Bid.created_at)
    ).all()
    # Rule 6 lets somebody raise their own winning bid, so one aliyah can hold
    # two of their bids at once. Ordered oldest first, the last one written
    # into the map is the newest, which is the one that counts and the only one
    # worth offering to undo. Cancelling it hands the aliyah back to whatever
    # sits below, their own earlier bid included.
    return {bid.aliyah_id: bid for bid in bids}


def remember_own_bid(bid_id):
    """Keep the last few bid ids, so the cookie cannot grow without bound."""
    ids = session.get("my_bids") or []
    ids.append(bid_id)
    session["my_bids"] = ids[-30:]


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    app.jinja_env.filters["nis"] = format_nis
    app.jinja_env.filters["israel"] = lambda moment: (
        "" if moment is None else "{:%d/%m/%Y %H:%M}".format(to_display(moment))
    )
    # The value a datetime-local input wants, in Israel time.
    app.jinja_env.filters["israel_input"] = lambda moment: (
        "" if moment is None else "{:%Y-%m-%dT%H:%M}".format(to_display(moment))
    )
    register_routes(app)

    return app


def register_routes(app):
    @app.route("/")
    def index():
        now = utcnow()
        occasions = db.session.scalars(
            select(Occasion).order_by(Occasion.display_order, Occasion.id)
        ).all()

        wanted = request.args.get("ocasiao")
        occasion = next((o for o in occasions if o.slug == wanted), None)
        if occasion is None:
            occasion = occasions[0] if occasions else None

        groups = []
        highest = {}
        bidding_open = False

        if occasion is not None:
            bidding_open = occasion.is_bidding_open(now)
            aliyot = db.session.scalars(
                select(Aliyah)
                .where(Aliyah.occasion_id == occasion.id)
                .order_by(Aliyah.display_order)
            ).all()
            # Items arrive in display order, so items of the same moment already
            # sit together, and inside a moment the tiers do too. groupby keeps
            # that order in both passes.
            for moment, items in groupby(aliyot, key=lambda a: a.moment_group):
                items = list(items)
                tiers = [
                    (tier, list(row)) for tier, row in groupby(items, key=tier_of)
                ]
                groups.append((moment, len(items), tiers))
            highest = highest_bids_for_occasion(occasion.id)

        # A rejected bid comes back with its values so nobody has to retype a
        # name, an email and a phone number on a phone.
        prefill = session.get("bidder", {})
        rejected_id = request.args.get("erro", type=int)

        window = app.config["SELF_CANCEL_MINUTES"]
        own_bids = own_cancellable_bids(now, window) if bidding_open else {}

        # A rejection belongs inside the bid dialog, next to the field the
        # visitor got wrong, not as a banner stranded in the middle of the page
        # where it also sits behind the dialog's own backdrop.
        flashed = get_flashed_messages(with_categories=True)
        errors = [text for category, text in flashed if category == "error"]
        notices = [text for category, text in flashed if category != "error"]

        return render_template(
            "index.html",
            occasions=occasions,
            occasion=occasion,
            groups=groups,
            highest=highest,
            bidding_open=bidding_open,
            closed_reason=None if occasion is None or bidding_open
            else occasion.closed_reason(now),
            is_locked=occasion is not None and occasion.status == STATUS_LOCKED,
            is_closed=occasion is not None and occasion.status == STATUS_CLOSED,
            hero_image=find_image("hero"),
            # Blue, deliberately. A gold Star of David on a dark ground reads as the
            # Judenstern. See the Logo section of CLAUDE.md.
            logo_image=find_image("logo_blue") or find_image("logo"),
            image_url_for=find_image,
            server_now=now,
            moment_captions=MOMENT_CAPTIONS,
            prefill=prefill,
            rejected_id=rejected_id,
            errors=errors,
            notices=notices,
            own_bids=own_bids,
            cancel_window=window,
        )

    @app.route("/aliyah/<int:aliyah_id>/lance", methods=["POST"])
    def submit_bid(aliyah_id):
        occasion_slug = request.form.get("ocasiao") or None

        session["bidder"] = {
            "full_name": (request.form.get("full_name") or "").strip(),
            "email": (request.form.get("email") or "").strip(),
            "phone": (request.form.get("phone") or "").strip(),
        }

        try:
            bid = place_bid(
                aliyah_id=aliyah_id,
                full_name=request.form.get("full_name"),
                email=request.form.get("email"),
                phone=request.form.get("phone"),
                amount_raw=request.form.get("amount"),
                now=utcnow(),
                format_amount=format_nis,
            )
        except BidRejected as rejection:
            flash(str(rejection), "error")
            return redirect(
                url_for(
                    "index",
                    ocasiao=occasion_slug,
                    erro=aliyah_id,
                    _anchor=f"aliyah-{aliyah_id}",
                )
            )

        remember_own_bid(bid.id)

        # The bid is committed. Email failures from here on are logged and do
        # not affect the visitor or the bid.
        aliyah = db.session.get(Aliyah, aliyah_id)
        occasion = db.session.get(Occasion, aliyah.occasion_id)
        mailer.send_bid_notification(
            app.config, occasion, aliyah, bid, format_nis(bid.amount)
        )

        flash(
            f"Lance de {format_nis(bid.amount)} registrado para {aliyah.label}.",
            "success",
        )
        return redirect(
            url_for("index", ocasiao=occasion_slug, _anchor=f"aliyah-{aliyah_id}")
        )

    @app.route("/lance/<int:bid_id>/anular", methods=["POST"])
    def cancel_own_bid(bid_id):
        """A bidder taking back their own bid, from the browser that placed it.

        Three things have to hold: the session remembers this bid, it is not
        cancelled already, and it is still inside the window. All three are
        checked here against the database, never against the page.
        """
        now = utcnow()
        window = app.config["SELF_CANCEL_MINUTES"]
        occasion_slug = request.form.get("ocasiao") or None

        bid = own_cancellable_bids(now, window).get(
            request.form.get("aliyah_id", type=int)
        )
        if bid is None or bid.id != bid_id:
            flash(
                "Este lance nao pode mais ser anulado por aqui. "
                "Fale com a Kehila.",
                "error",
            )
            return redirect(url_for("index", ocasiao=occasion_slug))

        bid.cancelled_at = now
        db.session.commit()

        flash(f"Seu lance de {format_nis(bid.amount)} foi anulado.", "success")
        return redirect(
            url_for("index", ocasiao=occasion_slug, _anchor=f"aliyah-{bid.aliyah_id}")
        )

    # ---------- Panel ----------

    def current_role():
        return session.get("panel_role")

    def require_panel(view):
        """Either level. Everything in the panel is behind this."""
        @wraps(view)
        def wrapped(*args, **kwargs):
            if current_role() not in (ROLE_ADMIN, ROLE_VIEWER):
                return redirect(url_for("panel_login"))
            return view(*args, **kwargs)
        return wrapped

    def require_admin(view):
        """Anything that changes something."""
        @wraps(view)
        def wrapped(*args, **kwargs):
            if current_role() != ROLE_ADMIN:
                if current_role() == ROLE_VIEWER:
                    abort(403)
                return redirect(url_for("panel_login"))
            return view(*args, **kwargs)
        return wrapped

    @app.context_processor
    def panel_context():
        return {"panel_role": current_role(), "ROLE_ADMIN": ROLE_ADMIN}

    @app.route("/admin/entrar", methods=["GET", "POST"])
    def panel_login():
        if request.method == "POST":
            typed = request.form.get("senha") or ""
            admin_password = app.config["ADMIN_PASSWORD"]
            viewer_password = app.config["VIEWER_PASSWORD"]

            # An empty configured password must never let anyone in, which is
            # what a plain equality check against "" would do.
            if admin_password and typed == admin_password:
                session["panel_role"] = ROLE_ADMIN
                return redirect(url_for("panel"))
            if viewer_password and typed == viewer_password:
                session["panel_role"] = ROLE_VIEWER
                return redirect(url_for("panel"))

            flash("Senha incorreta.", "error")
            return redirect(url_for("panel_login"))

        if current_role():
            return redirect(url_for("panel"))
        return render_template("panel_login.html")

    @app.route("/admin/sair", methods=["POST"])
    def panel_logout():
        session.pop("panel_role", None)
        return redirect(url_for("index"))

    @app.route("/admin")
    @require_panel
    def panel():
        now = utcnow()
        occasions = db.session.scalars(
            select(Occasion).order_by(Occasion.display_order, Occasion.id)
        ).all()

        wanted = request.args.get("ocasiao")
        occasion = next((o for o in occasions if o.slug == wanted), None)
        if occasion is None:
            occasion = occasions[0] if occasions else None

        rows = []
        total = 0
        with_bids = 0

        if occasion is not None:
            aliyot = db.session.scalars(
                select(Aliyah)
                .where(Aliyah.occasion_id == occasion.id)
                .order_by(Aliyah.display_order)
            ).all()
            leading = leading_bids_for_occasion(occasion.id)
            counts = dict(
                db.session.execute(
                    select(Bid.aliyah_id, func_count())
                    .join(Aliyah, Aliyah.id == Bid.aliyah_id)
                    .where(
                        Aliyah.occasion_id == occasion.id,
                        Bid.cancelled_at.is_(None),
                    )
                    .group_by(Bid.aliyah_id)
                ).all()
            )
            for aliyah in aliyot:
                bid = leading.get(aliyah.id)
                rows.append((aliyah, bid, counts.get(aliyah.id, 0)))
                if bid is not None:
                    total += bid.amount
                    with_bids += 1

        return render_template(
            "panel.html",
            occasions=occasions,
            occasion=occasion,
            rows=rows,
            total=total,
            with_bids=with_bids,
            now=now,
            is_open=occasion is not None and occasion.is_bidding_open(now),
        )

    @app.route("/admin/aliyah/<int:aliyah_id>")
    @require_panel
    def panel_aliyah(aliyah_id):
        aliyah = db.session.get(Aliyah, aliyah_id)
        if aliyah is None:
            abort(404)

        bids = db.session.scalars(
            select(Bid)
            .where(Bid.aliyah_id == aliyah.id)
            .order_by(Bid.amount.desc(), Bid.created_at.desc())
        ).all()
        occasion = db.session.get(Occasion, aliyah.occasion_id)

        return render_template(
            "panel_aliyah.html", aliyah=aliyah, occasion=occasion, bids=bids
        )

    @app.route("/admin/lance/<int:bid_id>/anular", methods=["POST"])
    @require_admin
    def panel_cancel_bid(bid_id):
        bid = db.session.get(Bid, bid_id)
        if bid is None:
            abort(404)
        if bid.cancelled_at is None:
            bid.cancelled_at = utcnow()
            db.session.commit()
            flash(
                f"Lance de {format_nis(bid.amount)} de {bid.full_name} anulado.",
                "success",
            )
        return redirect(url_for("panel_aliyah", aliyah_id=bid.aliyah_id))

    @app.route("/admin/ocasiao/<int:occasion_id>", methods=["POST"])
    @require_admin
    def panel_save_occasion(occasion_id):
        occasion = db.session.get(Occasion, occasion_id)
        if occasion is None:
            abort(404)

        action = request.form.get("acao")

        if action == "encerrar":
            occasion.status = STATUS_CLOSED
            db.session.commit()
            flash(f"{occasion.name} encerrado.", "success")
            return redirect(url_for("panel", ocasiao=occasion.slug))

        if action == "estado":
            wanted = request.form.get("status")
            if wanted in (STATUS_OPEN, STATUS_LOCKED, STATUS_CLOSED):
                occasion.status = wanted
                db.session.commit()
                flash(f"{occasion.name}: estado alterado.", "success")
            return redirect(url_for("panel", ocasiao=occasion.slug))

        try:
            opening = parse_israel_datetime(request.form.get("abertura"))
            closing = parse_israel_datetime(request.form.get("encerramento"))
        except ValueError:
            flash("Data invalida.", "error")
            return redirect(url_for("panel", ocasiao=occasion.slug))

        if opening is not None and closing is not None and closing <= opening:
            flash("O encerramento tem que ser depois da abertura.", "error")
            return redirect(url_for("panel", ocasiao=occasion.slug))

        occasion.opening_datetime = opening
        occasion.closing_datetime = closing
        db.session.commit()
        flash(f"Datas de {occasion.name} salvas.", "success")
        return redirect(url_for("panel", ocasiao=occasion.slug))

    @app.route("/health")
    def health():
        db.session.execute(select(1))
        return {"status": "ok"}


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
