# CLAUDE.md — Aliyot Auction (Yamim Noraim)

## Project Overview

Public auction website for synagogue honors (aliyot) for Rosh Hashanah and Yom Kippur, built for the Kehila community. Visitors place bids on aliyot; the site shows only the current highest bid (no names). The admin (Eliahu) receives an email on every bid and has a password-protected dashboard. No payment on the site — payment is handled offline after the auction closes.

This is a completely separate project from the seat-reservation app. Different repo, different design, no shared code or data.

## Working Rules (important)

- Make ONLY the changes explicitly requested. No unrequested additions, refactors, or "improvements".
- One task at a time. Finish, update this file, then /clear.
- Spec-driven: plan before executing. Confirm the plan before writing code.
- No emojis anywhere: not in code comments, not in UI copy, not in commit messages.

## Stack

- Backend: Flask (Python)
- Database: MySQL (Railway managed)
- Frontend: server-rendered HTML + CSS + vanilla JavaScript (no framework)
- Deploy: Railway, auto-deploy from GitHub main branch
- No Docker. No AWS.
- Email: SMTP via environment variables (e.g. Gmail app password). All secrets in env vars, never in code.

## Business Rules

1. Anyone can view the site and place bids. No login for the public.
2. A bid is valid ONLY if it clears the current highest bid for that aliyah by at
   least the STEP of 100 NIS. AMENDED 2026-09-09, see the decision below: strictly
   greater is no longer enough, so an aliyah sitting at 350 is next taken at 450.
   Anything from the current amount up to one shekel below the step is rejected with
   a message naming the current highest AND the amount that would be accepted.
3. Bid validation must be atomic at the database level (transaction / SELECT ... FOR UPDATE), not against what the user saw on screen. Concurrent bids must never both succeed at the same value.
4. Every bid requires: full name, email, phone. Required fields, basic validation.
5. Names of bidders NEVER appear on the public site. Only the current highest amount per aliyah.
6. A person may bid on multiple aliyot, and may raise their own winning bid.
7. All bids are stored (full history), not just the highest.
8. Admin receives an email on every new valid bid (aliyah, amount, name, email, phone).
9. The auction has an opening datetime AND a closing datetime (both configurable in admin). Before opening: site visible, bidding disabled, shows "opens at [date]". After closing: bidding closed, site shows final results (amounts only).
9b. AMENDED 2026-09-14, see the decision of that date: the countdown now shows WHOLE DAYS
    ONLY and the closing hour never appears on the public page. The text below is the
    original rule, kept for the history.
    Countdown timer: while the auction is open, the hero shows a prominent countdown (days, hours, minutes, seconds) to the closing datetime, styled in gold to match the design. Server time is the source of truth: the on-screen countdown syncs with server time on page load, and bid acceptance/rejection near the deadline is decided by the backend against server/database time, never the visitor's clock. After closing, the countdown disappears.
10. On closing, the system sends the admin a final report email: every aliyah with winning amount + winner name, email, phone.
11. Minimum bid per aliyah: ACTIVE since 2026-09-01 (this replaces the earlier
    "field exists but disabled" rule). Every aliyah has a starting minimum in ILS,
    stored on its own row so the admin can override a single item, but seeded by
    image group:
      - pticha (Abertura de parnassa, Abertura do Aron): 400
      - aliyah (Aliat Cohen through Aliat Maftir): 400
      - hagbaa_glila (Hagbaa 1/2, Glila 1/2): 200
    The first bid on an aliyah must be GREATER THAN OR EQUAL TO its minimum.
    Once any bid exists, rule 2 takes over and every further bid must be strictly
    greater than the current highest. The minimum never blocks a later bid.
    Maximum bid: field exists in DB and admin UI, empty and without effect. No ceiling.
12. Two tabs/occasions: Rosh Hashanah (active) and Yom Kippur (locked/blocked until after Rosh Hashanah — admin can unlock).

## Occasions and Items

### Rosh Hashanah — FIRST DAY ONLY (13 items, in this order; 12 on sale)

Grouped by moment, and inside Shacharit by tier. RENAMED 2026-09-01, see the
naming decision below. The card shows the name, and the subtitle under it in
smaller type where there is one.

**Arvit (night of Rosh Hashanah)**
1. Ptichat Heichal (Parnassa) / Abertura do Aron

**Shacharit — tier 1, the opening**
2. Ptichat Heichal / Abertura do Aron

**Shacharit — tier 2, the aliyot**
3. Cohen
4. Levi
5. Shlishi
6. Revii
7. Hamishi
8. Shishi - WITHDRAWN 2026-09-06, see below. Still listed here and still row 8.
9. Maftir

**Shacharit — tier 3, hagbaa and glila**
10. Hagbaa 1
11. Glila 1
12. Hagbaa 2
13. Glila 2

### Withdrawing an item

Added 2026-09-06, when Eliahu said the kehila would not sell the Shishi after all, with the
auction already open.

AN ITEM IS NEVER DELETED. `aliyot.is_active` goes False and that is the whole mechanism:
the card disappears from the public page, place_bid() refuses a bid on it even from a page
opened before the change, and the panel keeps the row dimmed with a "Fora do leilao" tag.
Bids already placed on it stay in the database, because a bid has a person behind it who
may have to be answered, and business rule 7 keeps the full history.

The list lives in `WITHDRAWN` in seed.py, keyed by (occasion slug, aliyah name). The row
stays in ROSH_HASHANA_ALIYOT so its display_order stays taken. Putting an item back in the
auction is deleting one line from WITHDRAWN and deploying. The seed enforces the flag on
every boot, the same way it enforces names, so a redeploy never resurrects a withdrawn item.

Eliahu said nobody had bid on the Shishi when it was pulled. It was still done this way,
because that fact was not knowable from here: the live data is on Railway.

SCHEMA MIGRATIONS, first time this was needed. db.create_all() creates missing TABLES and
never alters an existing one, so a new column on a model that is already deployed does not
appear on Railway by itself. `ensure_columns()` in seed.py checks the live table and runs the
ALTER when the column is missing. It runs on every boot from the Procfile, checks before it
acts, and was tested against the real pre-change database. ANY FUTURE COLUMN NEEDS THE SAME
TREATMENT, or it will work locally on a fresh SQLite file and break on the deploy.

### Yom Kippur (13 items, in this order)

SUPPLIED 2026-09-14 by Eliahu, with the minimums. Unlike Rosh Hashana the minimum is set PER
ITEM in YOM_KIPUR_ALIYOT (a sixth tuple element), not by image group, because Parnassa and
Maftir Yona share photographs with items that start much lower.

**Arvit (Kol Nidrei)**
1. Kol Nidrei / Sefer 1 - 500
2. Kol Nidrei / Sefer 2 - 500
3. Ptichat Heichal (Parnassa) / Abertura do Aron - 1000

**Shacharit** - no Ptichat Heichal in the morning, confirmed
4. Cohen - 500
5. Shlishi - 500
6. Revii - 500
7. Hagbaa 1 - 300
8. Glila 1 - 300
   (Hagbaa 2 and Glila 2 were in the first list and REMOVED by Eliahu. The "1" stays in the
   name, his choice.)

**Mincha (Tarde)** - a new moment, with the same blue rule above it, confirmed
9. Levi - 500
10. Maftir Yona - 2000
11. Hagbaa - 300
12. Glila - 300

**Neila (Fim do dia)** - a new moment, added later the same day
13. Ptichat Heichal (em honra ao Rav) / Abertura do Aron - 1000
    Named after the Parnassa pattern, Eliahu's choice. It IS sold and takes bids like any
    other item; "em honra ao Rav" means the Rav is the one who opens the Aron. pticha photo.

`kol_nidrei` is a new image_key, used by both Kol Nidrei cards. It gets its own tier row in
Arvit. Photograph supplied the same day, see Images.

The step of 100 NIS applies unchanged; Eliahu confirmed it is a minimum, so +150 is fine.

The tab is still LOCKED. Whether it is unlocked from the panel or opened by the deploy is
"falamos depois". Do not unlock it without asking.

## Database Schema (guideline)

- `occasions` — id, name, status (upcoming / open / locked / closed), opening_datetime, closing_datetime
- `aliyot` — id, occasion_id, name, subtitle (nullable), moment_group (e.g. "Arvit", "Shacharit"), display_order, image_key, min_bid (nullable, unused for now), max_bid (nullable, unused for now)
- `bids` — id, aliyah_id, full_name, email, phone, amount, created_at

Current highest bid = MAX(amount) per aliyah, or a denormalized column if justified — decide during build, keep it simple.

## Pages

### Public site
- Tabs: Rosh Hashanah | Yom Kippur (locked tab shows a tasteful "opens after Rosh Hashanah" state)
- Hero section with background video (see Design), title, and countdown timer to closing (while open)
- Items grouped by moment (Arvit / Shacharit) with group headings
- Each aliyah = a card: image, aliyah name, current highest bid (or "no bids yet" state), bid button/form
- Bid flow: enter amount + full name + email + phone, confirm, get success or "current bid is X, offer more" rejection
- After closing datetime: bidding disabled, cards show final amounts

### Admin (password-protected, single admin password via env var)
- Live overview: every aliyah, current highest bid, winner name/email/phone, full bid history per aliyah
- Configure: opening datetime, closing datetime, min/max bid per aliyah (fields present, default empty), lock/unlock Yom Kippur tab
- Manual "close auction" button (in addition to automatic closing datetime)
- Trigger/send final report email

## Design Direction

Solemn dark + gold ("Yamim Noraim" direction):

REDIRECTED ON 2026-09-01 by Eliahu, after seeing the first version. The three bullets that
used to sit here (near-black blue background, gold used sparingly, thin serif typography)
are SUPERSEDED. The direction is now warm, gold dominant and modern:

- Warm dark BRONZE background, never black and never blue. Base #17110a, surfaces #241c13 to
  #2e2418. Every neutral leans to amber, so the whole screen reads gold without the page ever
  turning light.
- Gold is DOMINANT, not an accent: gold headings, gold section rules, gold card borders, gold
  filled buttons, gold gradient on the hero title. Gold #d4af55, bright #eccd82, deep #a8842c.
- Modern, clean and airy: rounded corners (20px cards and panels, 999px pill buttons and tabs),
  generous spacing, soft shadows, sticky translucent header with a blur.
- Typography is SANS, not serif: Manrope, weight 200-300 for large display text and 500-700 for
  small uppercase labels. The thin serif direction was dropped.
- Gold gradients are wanted here (hero title, active tab, buttons). The old ban was on
  purple-blue gradients, which still stands. No linear easing: one shared bezier curve.
- The occasion tabs are a pill segmented control, the active one filled with gold.
- The countdown sits in rounded translucent bronze tiles.
- Cards: image + name + current bid. On hover: smooth scale-up (subtle, with proper easing) and slight inner image zoom.
- Hero: static background image (hero.jpg), NO video. Decision of 2026-09-01: the video was dropped from scope entirely, on desktop and on mobile, to keep the page light for older visitors on phones. Dark overlay 70-80 percent, object-position center so the Aron stays the focal point at every crop.
- Hero animation: slow Ken Burns zoom on the image, scale 1.00 to 1.08 over about 28 seconds, ease-in-out, alternating back and forth, CSS only, no JavaScript. It must never read as movement, only keep the page from looking frozen. Honor prefers-reduced-motion: no zoom when the visitor asks for reduced motion.
- NO music, no audio of any kind.
- Fully responsive; the site will be used by older community members on phones — readability and simple flows matter.

## Images (referenced by `image_key`; files live in static/images/)

Updated 2026-09-01, when Eliahu supplied the files.

- `pticha` - used by: Abertura de parnassa, Abertura do Aron - PROVIDED: `pticha.jpg`
  (open golden Aron Hakodesh with the sifrei Torah, "da lifnei mi ata omed" above)
- `aliyah` - used by: all 7 aliyot (Cohen through Maftir) - PROVIDED: `aliyah.png`
  (silver yad pointing at Torah text; the yad sits in the left third, so
  object-position keeps it in frame at every card size)
- `hagbaa` - used by: Hagbaa 1 and Hagbaa 2 - PROVIDED: `hagbaa.jpg` (open Torah scroll
  on the bimah with a yad)
- `glila` - used by: Glila 1 and Glila 2 - PROVIDED: `glila.jpg` REPLACED TWICE on
  2026-09-01 and 2026-09-02. A sefer in a burgundy velvet mantle with the crown, the two
  lions and the crest, standing on a wooden table. The first replacement came on a
  near-white studio background, which was the one light block on an otherwise dark page;
  Eliahu was told and supplied a second version of the same shot on a WARM BEIGE DAMASK
  background, which is the file in use. It still reads lighter than the other cards, but it
  leans amber and sits inside the palette instead of fighting it. Keep any future
  replacement warm and dark, and prefer a frame where the sefer is not a narrow strip.
- `kol_nidrei` - used by: Kol Nidrei Sefer 1 and Sefer 2 (Yom Kipur) - PROVIDED 2026-09-14:
  `kol_nidrei.jpg` (a sefer in a cream mantle embroidered in gold, "ספר תורה / יום כיפור /
  כל נדרי", held against a tallit with blue stripes). Generated image, 1408x768 like the
  others. Exported at 700 wide, 58 KB. No --zoom and no CSS rule: the embroidered text sits
  at the centre, and both the 3:2 desktop crop and the upright phone strip were checked and
  keep it in frame. The mantle is cream, so this card reads lighter than the rest of the page.
- `hero` - PROVIDED: `hero.jpg` (congregation from behind in white tallitot facing the
  illuminated golden Aron, candlelight). Dark warm veil over it, object-position center so
  the Aron stays the focal point. Animated with the slow Ken Burns zoom.

CHANGED 2026-09-01: the single `hagbaa_glila` key was SPLIT into `hagbaa` and `glila`,
because two different photographs were supplied. Both still carry a 200 ILS minimum.

For missing images, the card falls back to a thin gold Magen David outline on the dark
surface. find_image() tries .jpg, .jpeg, .png and .webp for the key, so installing a real
image is just dropping the file in with the right name.

ALL SIX IMAGES ARE NOW INSTALLED. No card falls back to the placeholder any more.

FRAMING PER PHOTO, asked for by Eliahu on 2026-09-01. Each card carries a `media-<image_key>`
class and the image has a `--zoom` custom property, so every photograph gets its own crop. The
hover zoom multiplies `--zoom` instead of replacing it, so both survive together.

- `glila` - crop IN on the sefer. The scroll is tall and narrow in a wide frame, so without
  this the card is a field of background with a small scroll in the middle. Currently
  --zoom 2.0 (pulled back from 2.4 on Eliahu's ask), object-position 50% center, which
  favours the mantle, the crown and the lions. The top and bottom of the scroll are
  deliberately cropped. The studio background still fills most of the card: the scroll is
  about a seventh of the frame width, and cropping in far enough to fill the card with
  velvet would mean scaling a 170 pixel wide strip up to card size.
- `pticha` - RETUNED 2026-09-01, asked for by Eliahu: focus on the Aron and cut the walls of
  the room that were showing on both sides. Now --zoom 1.6, object-position 50% center, at
  which the frame holds nothing but the gold carving and the sifrei Torah. The inscription
  over the arch and the step below are cut, which is the cost of losing the walls: the Aron
  is nearly square and the card is 3:2, so both cannot fit.
- `aliyah` - object-position 32% center. The yad sits in the left third and must never be
  cropped out, at any card size.

THE PHONE IS A DIFFERENT CROP, found on 2026-09-02 and easy to forget. On a desktop the
media box is 3:2 and lying down. On a phone the card turns into a row and the box becomes a
narrow upright strip, 98px wide by the card height, about 0.70. The photographs are 1.83, so
the browser is already cropping the sides away hard before --zoom does anything, and a high
zoom then crops a second time. On `pticha` at zoom 1.6 the phone was left with the shelf of
sifrei Torah and no Aron at all: the arch, the crown and the inscription were all outside
the frame, which is the opposite of what the zoom was raised for.

`.media-pticha img` is therefore overridden to `--zoom: 1` inside the 700px breakpoint. The
walls stay out of frame there regardless, because the upright strip has already cut them.
The other three are checked and fine on a phone: glila fills the card better than it does on
a desktop, aliyah puts the yad in the centre, hagbaa reads.

ALWAYS check both crops after touching a --zoom. Most visitors are on a phone.

NOTE on tuning: with object-fit cover, these photographs (1408x768, ratio 1.83) overflow the
3:2 card horizontally only, so the VERTICAL half of object-position does nothing. Vertical
framing is always centred and can only be changed with --zoom. The old "50% 36%" and
"47% 44%" values were inert in their second number.

These zoom values are a first pass. Tune them by eye rather than treating them as settled.

CLOSED 2026-09-02. The images used to total 4.6 MB and every visitor downloaded all of it
on the first load, on a phone, on mobile data. They now total 501 KB:

  pticha 1817 -> 95 KB (940 wide), glila 602 -> 79 KB (1150), hagbaa 753 -> 49 KB (660),
  hero 873 -> 210 KB (1376, unchanged size, re-encoded), aliyah 624 -> 48 KB (520),
  logo_blue 19 KB untouched.

All JPEG at quality 82, progressive, optimize on. `aliyah` was a photograph stored as a PNG
and is now `aliyah.jpg`; the PNG was deleted, and find_image() prefers .jpg anyway.

Each target width was worked back from the largest region the layout ever shows OF THAT
FILE, not from one blanket size, because --zoom means only part of a file reaches the card.
The card is 223 CSS px wide on a desktop and 98 on a phone, so roughly 2x of the visible
region is the target.

THE FULL SIZE ORIGINALS ARE IN `images_source/`, which is outside static/ and is never
served. Reframing (a new --zoom, a new object-position) must be done FROM THERE and then
re-exported, otherwise it is a crop of a crop. Do not delete that folder.
Re-run the export by hand if a photograph is replaced; there is no build step.

## Logo

REWRITTEN 2026-09-01. This REVERSES the original instruction, which said to make a
monochrome gold or ivory version of the mark for the dark site and never use the blue
original directly. Do not restore that instruction.

- Community: Kehilat Or Israel. In use: `logo_blue.png` (Star of David in two blues with a
  Torah scroll at the centre, Hebrew and English name underneath).
- THE MARK MUST NOT BE GOLD OR YELLOW. A gold Star of David on a dark ground reads as the
  Judenstern, the star Jews were forced to wear in Nazi Germany. Eliahu saw the gold version
  on the site and asked for it to go. The gold file was deleted from static/images.
  This applies to the drawn Magen David fallback too, which is now blue (--blue-mark).
- The light plate behind the mark was TRIED AND REJECTED by Eliahu on 2026-09-01: he wants
  the mark loose on the background, no box and no border. It sits directly on the bronze.
- To make that possible the white background baked into the supplied file was stripped from
  `static/images/logo_blue.png` itself (near-white pixels cleared, rim feathered so there is
  no white halo). THE FILE IN THE PROJECT IS NOT THE SAME AS THE ONE ELIAHU SUPPLIED. If it
  is ever replaced with a fresh copy of the original, the white square comes back and the
  background has to be stripped again.
- The bottom fifth of the logo file (its own wordmark) is cropped away in the header, because
  the community name is already set in clean type beside it.
- In emails (light background) the original full-colour logo is used directly, no plate.

## Blue in the palette

Added 2026-09-01, asked for by Eliahu: a deep navy used lightly, at a few strategic points,
so the page is not wall to wall bronze.

- `--blue: #16233d`, `--blue-soft: #1e3055`, `--blue-line`, `--blue-mark: #4f7cb8`
- THE JOB OF BLUE IS DIVISION, the job of gold is money. Keeping the two apart is the whole
  point. Eliahu's own words: blue belongs "em alguma linha que divide noite manha".
- Used in: the rules that divide one moment from the next (2px --blue-rule on top of each
  moment header, a hairline under it), the footer band, the modal backdrop, the card image
  base, and the Magen David fallback.
- The locked Yom Kipur panel WAS blue and was REVERTED on 2026-09-01: a whole panel in blue
  was too loud ("muito na cara"). It is bronze again with a gold title. Blue as a large filled
  block does not work in this design; blue as a line does.
- NOT used in the hero, the cards or the type. Bronze and gold still carry the page.
- Never blend navy into bronze as a gradient. The two mixed go purple, which the design
  direction has banned from the start.

## Pending Requests (asked by Eliahu 2026-09-01, NOT built yet)

Recorded from a short note, so each one carries the original wording and the reading of it.
Confirm the reading before building.

1. DONE 2026-09-01. "dividir alia de abertura e outras coisa em andares diferentes"
   Built as three tiers inside Shacharit, plus the renaming below.

2. DONE 2026-09-05. "arrumar foots", settled when Eliahu said what was missing: the footer
   had to carry the notices. Built as "Como funciona", a gold-bulleted list under the
   community name:
     - todas as aliyot serao vendidas em leilao
     - vence o maior lance no momento do encerramento
     - nenhum nome aparece no site, so o valor
     - a data do encerramento
     - o pagamento e combinado com a Kehila depois
   THE CLOSING LINE IS DERIVED, never typed: it reads occasion.closing_datetime through the
   `israel_long` filter, so changing the date in the panel changes the footer, and the tab
   the visitor is on decides which occasion is named. It says "encerra" before the date and
   "encerrou" after, compared against server_now. No closing date on the occasion (Yom Kipur
   before it is configured) and the line is simply absent.
   The list is LEFT ALIGNED inside a centred 620px block. Centred sentences are harder to
   read on a phone, and most visitors are on one.

3. DONE 2026-09-01. "quando o valor ser sugerido por alguem ele tera q estar palpitando
   dentro de uma borda ouro" - an amount that someone has actually bid now sits in a gold
   pill and pulses. See the decision below. This is a SEPARATE request from item 4 and does
   not settle it.

4. DONE 2026-09-02. The explanation at the top of the site. Wording is Eliahu's own, see
   the decision below. Built as the `.intro` block between the hero and the tabs.

5. "qdo doa ele tenq mostrar q eh o valir maximo"
   READING NOT ESTABLISHED. A first reading was proposed (a label above the amount saying
   "lance minimo" or "maior lance") and Eliahu said it was WRONG. He will explain what he
   actually meant. Do NOT build anything for this item until he does, and do not reuse the
   rejected reading as a starting point.
   All that is certain is his own wording, kept verbatim above.

## The Schedule

SET 2026-09-02 from the datetimes Eliahu gave. HIS TIMES ARE ISRAEL TIME, and he said so
twice. What is in the database is the UTC equivalent:

  | ocasiao      | abertura (Israel) | encerramento (Israel) | guardado em UTC             |
  | rosh-hashana | 05/09/2026 20:00  | 10/09/2026 22:00      | 05/09 17:00 / 10/09 19:00   |
  | yom-kipur    | 13/09/2026 20:00  | 17/09/2026 22:00      | 13/09 17:00 / 17/09 19:00   |

Israel is UTC+3 in September (IDT), so three hours come off. The conversion was done with
zoneinfo, cross checked against the Windows timezone database, and BOTH SOURCES AGREED
before anything was written. Never type a UTC value by hand and never add a fixed offset:
Israel drops to UTC+2 at the end of October and any hardcoded +3 silently becomes wrong.

Rosh Hashana keeps status `open` and Yom Kipur keeps `locked`. The window is what decides
bidding now, so the site is currently in its BEFORE OPENING state: no bid buttons, no
countdown, and the line "O leilao abre em 05/09/2026 as 20:00 (horario de Israel)".

TO TEST THE BID FLOW BEFORE 05/09 the opening_datetime has to be cleared or moved back by
hand. There is no admin yet. Put the real value back afterwards.

THE DEVELOPMENT MACHINE IS IN BRASILIA, UTC-3, six hours behind Israel. It does not affect
the app, which takes its time from datetime.now(timezone.utc) and is therefore the same
instant everywhere including Railway. It does affect anyone eyeballing a date on this
machine: local time here is neither the stored value nor what the site shows.

## Admin And Cancelling A Bid - decided 2026-09-02, phase 4

### Who sees the data

TWO LEVELS, both reached from the same password screen at /admin.

- ADMIN (Eliahu). Sees everything and changes everything: the datetimes, lock/unlock Yom
  Kipur, close the auction by hand, cancel anybody's bid.
- CONSULTA (about three other people). Sees exactly the same data and changes NOTHING.

ONE shared password for the consulta level, Eliahu's choice: "pode ser uma senha p todos".
Individual passwords were offered and declined. A separate password from the admin one, so
the viewers can be cut off without changing his. Both live in environment variables.

Eliahu was told the panel exposes the name, email and phone of every member who bids, and
that a shared password means a leak is a leak of the whole list. His answer, recorded so it
is not re-litigated: "nao tenho medo de vazar nao somos tao grandes."

### Cancelling a bid

A bidder may cancel THEIR OWN bid within a SHORT WINDOW after placing it, and only from the
same browser. After the window only the admin can cancel, and the admin can cancel anything
at any time. Agreed with Eliahu, who approved the short window over free cancellation.

The reason for the window, worth keeping because it is not obvious: free cancellation turns
the auction into a different game. Bid 5000 to scare the room off, cancel the night before,
take the aliyah for 400. Or bid 1000, go uncontested, cancel and re-bid 450, which makes the
minimum and the strictly-greater rule decorative. A short window covers the real case, which
is a typo, and closes the door on the rest.

IDENTITY IS THE SESSION AND NOTHING ELSE. There is no login on the public site, and email
confirmation links are off the table (see below). So "your own bid" means a bid placed in
this browser. Change device, clear the cookies, or bid on the phone and try to cancel on the
laptop, and it will not work. That limit is understood and accepted.

A CANCELLED BID IS NEVER DELETED. It is marked cancelled with the time, business rule 7
keeps the full history, and the record matters if anyone ever disputes what happened. What
changes is that it stops counting towards the aliyah's highest.

### Email

BUSINESS RULES 8 AND 10 ARE SUSPENDED, not deleted. Eliahu: "em relacao a m mandar email nao
precisa... eu copio os dados na mao", and then "eu estou cancelando por ora... talvez no fim
vou aumentar". So no bid notification and no final report for now, and the panel is how he
reads the auction.

mailer.py and the call in submit_bid STAY IN PLACE, dormant. They are already written, they
cost nothing while SMTP is unconfigured, and he may want them back. Do not delete them and
do not delete rules 8 and 10 from this file: they are suspended, with a date.

## The Panel, as built 2026-09-02

WAY IN: a "Painel do leilao" button at the bottom of the public page, plus the address
/admin directly. Eliahu asked for the button rather than a typed address. That does mean the
panel is no longer a secret address and the password is the only thing guarding it, which
is fine by his own decision above.

  /admin/entrar   the password screen, both levels
  /admin          the overview table
  /admin/aliyah/<id>  one aliyah's full history
  /admin/sair     logout

TWO PASSWORDS, both environment variables, both empty by default. An empty one CANNOT be
logged into: the check is `if configured_password and typed == configured_password`, because
a plain equality would let an empty form in on a fresh deploy.

  ADMIN_PASSWORD   full control
  VIEWER_PASSWORD  reads everything, changes nothing

The viewer level is enforced on the server, not by hiding buttons: the admin-only routes
return 403 to a viewer. Tested.

The overview carries the aliyah, the current amount, and the name, email and phone of
whoever is winning it, which is what Eliahu copies out by hand. Email and phone are mailto:
and tel: links so a phone can call straight from the table. Three tiles on top: total of the
winning bids, how many aliyot have a bid, and whether the occasion is open.

Datetimes in the panel are typed and shown in ISRAEL TIME and converted at the edge, by
from_display() on the way in and to_display() on the way out. The page says so in a line of
its own so nobody wonders.

The panel is deliberately plainer than the public site: a working tool read on a phone, in a
hurry, across a wide table. Same palette, none of the ceremony. The table scrolls sideways
inside its own box so the page never scrolls horizontally.

### Cancelling, as built

- `Bid.cancelled_at`, nullable. NEVER deleted. Both highest_bids_for_occasion() and the
  check inside place_bid() ignore cancelled rows, so cancelling hands the aliyah back to the
  bid below it and lowers the floor the next bidder has to clear.
- The visitor's own cancel: `POST /lance/<id>/anular`, and the button only renders on a card
  when this browser placed that bid and it is inside the window. session["my_bids"] holds the
  last 30 bid ids. Verified that a second browser posting the same bid id changes nothing.
- SELF_CANCEL_MINUTES, default 10, an environment variable.
- Rule 6 lets somebody raise their own bid, so one aliyah can hold two live bids from the
  same person. own_cancellable_bids() orders by created_at so the map keeps the NEWEST, which
  is the one that counts. This was a real bug found in testing, not a hypothetical.
- The admin cancels anything at any time from the history page, with a confirmation.
- NARROWED 2026-09-03, raised by Eliahu from the live site. The button used to render
  whenever this browser had a live bid on the aliyah, which meant it sat under somebody
  else's higher amount and read as an offer to cancel THAT. It now renders only while the
  browser's own bid is the one winning the aliyah: `mine.amount == current` in the card.
  The reasoning, so it is not undone: the window exists for a typo the bidder is held to,
  and once covered they are held to nothing, so cancelling would move no figure on screen.
  The narrow case given up is a covering bid that is itself cancelled later, which hands a
  mistyped amount back to a bidder whose own window has passed. The admin can cancel it.
- The label carries the amount, "Anular meu lance de 400 NIS", asked for by Eliahu the same
  day so the button can never be read as belonging to another person's bid.
- THE SERVER WAS NOT TOUCHED by either change. cancel_own_bid() still checks the session,
  the cancelled flag and the window against the database, and does not ask whether the bid
  is winning, so a stale page cancels its own covered bid harmlessly instead of erroring.

### The test data

The database was emptied of bids twice on 2026-09-02, at Eliahu's request, so the real
auction starts from zero. There is deliberately NO "clear everything" button: during a live
auction it can only destroy work, and cancelling one wrong bid is what is actually needed.
Wiping is done by hand if it is ever needed again.

## Still Open On The Schedule

1. THE CLOSED STATE HAS TO SEND PEOPLE TO YOM KIPUR. Eliahu: "depois de rosh hashana ou seja
   depois q acabar o horario vao ter q estar escrito q acabou o leilao e dizendo p ir na aba
   de yom kipur". Today the closed state is one dry line from closed_reason() above the
   cards, and it invites nobody anywhere. Agreed shape, wording still to be confirmed:

     O leilao de Rosh Hashana esta encerrado
     Os lances foram encerrados em <data> as <hora>.
     [ Ver o leilao de Yom Kipur ]        <- gold button, links to that tab

   OPEN: what if Yom Kipur is still LOCKED when Rosh Hashana closes? It is locked today and
   has no aliyot at all, because its item list has never been supplied. A button into a
   locked tab is a dead end. PROPOSED, awaiting Eliahu: the block reads the other occasion's
   state and changes by itself - button when Yom Kipur is open, and the plain line "O leilao
   de Yom Kipur abre em breve" with no button while it is still locked, so the admin does not
   have to race to unlock at the closing minute.

   Note the gap in the dates: Rosh Hashana closes 10/09 22:00 and Yom Kipur opens 13/09
   20:00. For nearly three days BOTH are shut, and whatever this block says has to still make
   sense in that window.

2. THE INTRO BLOCK READS WRONG ONCE THE AUCTION IS OVER. "Aqui voce registra apenas o seu
   lance" is an invitation and it keeps showing after closing. Asked, not answered.

3. NO COUNTDOWN BEFORE THE OPENING. The countdown only renders while bidding is open, so
   between now and 05/09 there is a sentence and nothing else. Rule 9 asks for exactly that,
   but a countdown to the opening was never discussed. Raise it with Eliahu.

4. Setting these datetimes belongs in the admin, phase 4, not built. For now the database is
   the only way in. Do not hardcode a date anywhere.

## Open Questions (do not decide alone — ask Eliahu)

- Yom Kippur item list. SUPPLIED 2026-09-14, see Occasions and Items. The tab is still
  locked, so the "go to Yom Kipur" call to action still points at a locked tab.
- Who unlocks Yom Kipur and when. Deferred by Eliahu on 2026-09-14.
- The footer, pending request 2. What is actually wrong with it has never been said.
- Whether the Arvit card should follow the Pticha naming pattern.

## Decisions Taken

- 2026-09-14 THE PUBLIC PAGE NEVER SHOWS THE CLOSING HOUR. Asked for by the kehila through
  Eliahu: "nao mostrar as horas q vai terminar p ngm ficar esperando e sim apenas mostrar
  qtos dias falta". The auction still closes at the exact datetime set in the panel; only
  the display changed.
  - Hero: one tile, "3 dias" / "1 dia", and on the closing day "Encerra hoje" (his choice
    over "Ultimo dia"), without the "Para o leilao fechar" note under it.
  - DAYS ARE CALENDAR DAYS IN ISRAEL, from closing_countdown() in app.py. A 24-hour count
    would turn over at 22:00, the closing hour itself, and give it away anyway. The figure
    turns over at midnight in Israel.
  - THE CLOSING DATETIME IS NOT IN THE HTML AT ALL. The old data-closing and data-now
    attributes are gone. The page only gets data-refresh-in, the seconds until the next
    Israel midnight, and site.js reloads then (postponed while a modal is open, so a bid
    being typed is never lost).
  - Consequence, accepted: the page no longer reloads by itself at the closing minute,
    because it does not know it. A bid sent after the close is refused by the server, as
    it always was, and the next load shows the closed state.
  - Footer: "encerra na quinta-feira, 17/09/2026." The israel_long filter lost the hour and
    the "(horario de Israel)" went with it.
  - UNCHANGED on purpose: after the close, closed_reason() still says "encerrou em ... as
    22:00", agreed with Eliahu, since it no longer matters. The opening line "abre em ... as
    20:00" is untouched. The panel still shows full datetimes.
  - A change of closing date in the panel reaches all of it on the next page load.

- 2026-09-09 EVERY MESSAGE THE VISITOR READS IS SPELLED WITH ACCENTS. The ten rejection
  messages in bidding.py and the self-cancel refusal in app.py were written without them
  ("Valor invalido", "ofereca", "nao encontrada"). Eliahu's reason for the old spelling, so
  nobody reads it as a style: "no meu teclado nao tem". This finishes what the 2026-09-02
  entry started on closed_reason(). Anything new that a visitor or the panel reads is
  written properly from here on; code, comments and this file stay in plain ASCII English.
  Still unaccented and left alone for now: three panel-only lines, "Senha incorreta", "Data
  invalida" and "{ocasiao}: estado alterado".

- 2026-09-09 BIDS RISE IN STEPS OF 100 NIS. `MIN_INCREMENT` in bidding.py, one branch
  inside place_bid(): a raise must reach current + 100, not current + 0.01. Asked for by
  Eliahu, so a contested aliyah is not walked up one shekel at a time.
  THE STEP IS A MINIMUM, NOT A GRID. Above the floor any amount passes, so 350 can be
  answered with 450, 500 or 720. Eliahu chose this over multiples of 100, which would
  refuse 480 as well.
  THE FIRST BID ON AN ALIYAH IS UNTOUCHED. With no bid to beat there is nothing to step
  up from, so min_bid alone decides it and 400 is still accepted on an aliyah, 200 on a
  hagbaa or glila. Only from the second bid on does the step apply.
  NOTHING WAS DELETED OR MIGRATED. No column, no table, no seed change, and every bid
  already in the database keeps its amount. Only bids arriving after the deploy are judged
  by the new rule, which means a live auction can adopt it mid-flight.
  Tested against a COPY of the local database, not the working one: 399 refused, 400 taken,
  401/450/499 refused over 400, 500 and 720 taken, 720 refused over 720, 820 taken.

- 2026-09-01 Site UI language: Portuguese. Aliyah names stay exactly as written in this file.
- 2026-09-01 Currency: ILS (shekel).
- 2026-09-01 Hero: static image with slow Ken Burns zoom. Video removed from scope, desktop and mobile.
- 2026-09-01 Database access: one SQLAlchemy codebase driven by a DATABASE_URL env var. SQLite locally during development, MySQL on Railway in production. No code change at the switch.
- 2026-09-01 Highest bid: computed as MAX(amount) per aliyah, no denormalized column.
- 2026-09-01 Build order: backend skeleton first (Phase 1), public design immediately after (Phase 2).
- 2026-09-01 Minimum bid activated, per image group, values in rule 11. Equal to the minimum is accepted.
- 2026-09-01 A card with no bids shows the minimum amount only, with no "a partir de" prefix and no "sem lances ainda" text. It is set apart from a real bid by styling, not by wording.
  REVERSED 2026-09-02. Eliahu watched the built page and said the bare numbers were being
  read as the price of the aliyah: "os 400 e 200 sao os minimos, confundem pq parecem os
  precos". A card with no bids now carries a small uppercase "A partir de" over the figure.
  Styling alone was not enough to carry the difference. A card WITH a bid is unchanged: the
  gold filled pill, beating, and no label.
- 2026-09-01 Maximum bid stays disabled, no ceiling on any aliyah.
- 2026-09-01 Seed fills min_bid only when it is empty, so a redeploy never overwrites an admin edit.
- 2026-09-01 Hero title: "Leilao de Aliyot", kicker "Yamim Noraim", occasion name below.
- 2026-09-01 Bidding happens in a modal opened from the card, not in a form inside the card.
- 2026-09-01 Missing images fall back to a thin gold Magen David outline on the dark surface.
  find_image() looks for static/images/<image_key>.<jpg|jpeg|png|webp>, so dropping the real
  files in with the right name is the whole swap-in. Names expected: hero, logo_gold (or logo),
  pticha, aliyah, hagbaa_glila.
- 2026-09-01 Typography split: Cormorant Garamond 300 for headings, hero and amounts; a system
  sans for body, labels and inputs. A thin serif at 13px is not readable for older visitors, and
  inputs are 16px so phones do not zoom on focus.
- 2026-09-01 The bidder's name, email and phone are kept in the session and prefilled, so a
  rejected bid or a bid on a second aliyah does not mean retyping everything on a phone.
- 2026-09-01 A rejected bid reopens the modal on the same aliyah with the values still there.
- 2026-09-01 The full width feature card for a single-item moment was TRIED AND REVERTED the
  same day: Eliahu did not like the wide Arvit card. A lone card in a normal grid row is the
  accepted look. Do not reintroduce it.
- 2026-09-01 Hero heights: 72vh desktop, 58vh mobile, so the first moment and the start of the
  next one are reachable in one scroll. Most visitors will be on a phone.
- 2026-09-01 The header was enlarged so the kehila symbol stands out: header padding 20px, the
  logo mark 60x48 (was 44x35), the name at 15px. Eliahu asked for the symbol to be prominent,
  so do not shrink the mark back for the sake of a slimmer bar.
- 2026-09-01 DESIGN REDIRECT: Eliahu asked for more modern and more gold than black. Bronze and
  gold, clean and airy, sans typography. See the Design Direction section, which was rewritten.
- 2026-09-01 BUG FIXED: the modal used display:flex, which beats the browser rule for [hidden],
  so it covered the whole page from load. Any element hidden with the hidden attribute needs an
  explicit [hidden] rule when its display is set in CSS.
- 2026-09-01 Phase order changed: phase 3 (bid flow) was built BEFORE phase 2 (design), so the
  design is drawn once with the bid form already in place instead of being reworked around it.
- 2026-09-01 Email is best effort. It is sent only after the bid is committed, and any SMTP
  failure is logged and swallowed. A bid is never lost or rolled back because email failed.
- 2026-09-01 All datetimes in the database are naive UTC. The bidding window is decided by
  Occasion.is_bidding_open() against server time, never against the visitor's clock.
- OPEN RISK: the row lock that makes concurrent bids safe (SELECT ... FOR UPDATE) is IGNORED by
  SQLite. It is written correctly but is only truly enforced on MySQL. Must be re-tested with
  real concurrent requests once the project is running on Railway.
- NOT BUILT, decide later: the public bid form has no CSRF token and no rate limiting. Both are
  worth revisiting before the site goes public, since the form is open and creates a real
  payment obligation.
- 2026-09-01 This file lives at the project root. The copy under AppData/Local/Temp is obsolete.
- 2026-09-01 TIERS inside a moment. Shacharit holds three tiers: the opening, the seven
  aliyot, hagbaa and glila. A tier is SPACE ONLY: no heading, no rule, no label. Eliahu was
  explicit: "soh em outro andar sem linha separando, a linha eh apenas entre de noite e de
  manha". The blue rule stays a division of night from morning, and drawing one between
  tiers would cost it that meaning. Rendered as one .grid per tier with .grid + .grid
  spacing, so each tier starts on a fresh row.
- 2026-09-01 The tier is derived from image_key (pticha, aliyah, hagbaa+glila together), not
  stored on the row. The image already tracks the kind of honour, so a second column would
  be the same fact written twice.
- 2026-09-01 NAMING. The card carries the Hebrew title, with the Portuguese reading under it
  in smaller type in a new nullable `subtitle` column. Abertura do Aron became "Pticha" with
  the subtitle "Abertura do Aron". The seven aliyot dropped the word "Aliat" and are just
  Cohen, Levi, Shlishi, Revii, Hamishi, Shishi, Maftir - the tier they sit in already says
  they are aliyot. Hagbaa and Glila keep their names, asked for by Eliahu.
- 2026-09-01 Aliyah.label (name plus subtitle) is used everywhere the card is not there to
  give context: admin emails, the confirmation message and the bid modal title. Two openings
  both titled "Pticha" would otherwise be indistinguishable in an email.
- 2026-09-01 Seed now UPDATES the name and subtitle of rows that already exist. Wording is
  decided in this file, not in the admin, so it is not an admin edit to protect. min_bid is
  still only filled when empty.
- 2026-09-01 The `subtitle` column was added to the local aliyot.db by hand with ALTER TABLE.
  There is no migration tool in the project: db.create_all() creates new tables but never
  adds a column to an existing one. Any further column change needs the same manual step
  locally, and on MySQL once Railway is live.
- 2026-09-01 An amount somebody has bid is shown in a pill FILLED with gold, the number
  reversed out in the page's bronze (--bg) at weight 600, beating on bid-pulse: 1.7s, a
  scale to 1.07 and a ring that expands to 13px and fades. Eliahu asked for it twice, the
  second time louder: "qero q palpita mais chamativo e q dentro das bordas esteja preenchido
  c ouro (e o numero entao em outra cor)". The outlined version that came first was not
  enough. An aliyah still showing only its minimum keeps the plain faint number, no border
  and no movement. The contrast between the two is what says which cards carry money,
  without a word of explanation. Reduced motion is honoured by the global rule at the end of
  the stylesheet, and the animation rests on the state it ends in.
- 2026-09-02 CURRENCY IS WRITTEN "NIS", not "ILS". ILS is the bank code, NIS is the name of
  the currency. format_nis() and the jinja filter `nis` replaced format_ils()/`ils`, and the
  parser in bidding.py strips "NIS" as well as the shekel sign from what a visitor types.
- 2026-09-02 The occasion tabs are TWO LOOSE PILLS. The capsule that boxed both of them
  together, an outer border with a surface behind it, was removed on Eliahu's ask. The
  active pill is still filled with gold. This narrows the earlier "pill segmented control"
  line in the design direction: segmented, but without the container.
- 2026-09-02 Switching occasion keeps your place on the page. The tab is a plain link, so
  the browser loads a fresh page at the top; site.js stores window.scrollY in sessionStorage
  on the click and restores it on load, clamped to the new page height because Yom Kipur is
  one short panel. An anchor from a placed bid wins over the stored position, and a browser
  that refuses sessionStorage simply loses the position instead of breaking the link.
- 2026-09-02 THE BID FORM NO LONGER SHOWS AN AMOUNT. The kicker and the figure above the
  form were removed, markup, CSS and the JS that filled them. Eliahu's reason is the good
  one: a minimum displayed over an empty field reads as the number you are supposed to type,
  so it anchors people at the minimum instead of inviting a real bid. A bid that is too low
  is refused by the server with a message naming the amount to beat, and the enlarged card
  carries the current figure, so nothing is lost.
- 2026-09-02 TAPPING A CARD OPENS THAT SAME CARD, BIG, in the middle of the page: photograph,
  name, amount and its bid button. It is the card element CLONED into #card-modal, not a
  second layout to keep in step with the first, so anything added to a card appears there for
  free. The clone drops its id and its .card-zoom cover, and its bid button is wired to the
  ORIGINAL card's button so focus has somewhere real to return to. The small "Dar lance"
  button on the card still opens the form directly, in one tap, as before: the enlarged card
  is an addition, not a step inserted in front of bidding.
- 2026-09-02 A transparent .card-zoom button covers the whole card, and .btn-bid is lifted
  above it with z-index. The whole card is the target, not just the photograph, because the
  visitors are older people on phones and a bigger target is a kinder one.
- 2026-09-02 On a phone the enlarged card overrides the row layout back to a column with a
  3:2 photograph, and with it the phone framing override: .card-big .media-pticha img goes
  back to --zoom 1.6, because inside the big card the box is 3:2 again, not the narrow strip
  the phone list uses.
- 2026-09-02 INTRO BLOCK between the hero and the tabs, wording Eliahu's own, kept verbatim:
  title "Dê o seu lance e aumente seus Zechuyot", then "Aqui você registra apenas o seu
  lance, o site não recebe pagamento. O vencedor será contatado pela Kehila para acertar o
  pagamento." ("Quem ganhar no final" was Eliahu's first wording and he replaced it with
  "O vencedor" the same day.) The second sentence is the one that matters and the reason the block
  exists: no money changes hands on this site. It shows in every state of the auction,
  including after closing, where the first sentence reads oddly. Revisit if that matters.
- 2026-09-02 CARD TYPOGRAPHY. The aliyah name on the card went from 14px weight 500 in cream
  to 17px weight 600 in --gold-bright (18px on a phone, 24px in the enlarged card), and the
  subtitle from 12px --faint to 13px --dim so it does not vanish under the bigger name.
  Eliahu asked for it: the name "nao chamativa". It read as a caption under a photograph
  rather than as the title of the honour being offered. Gold headings are the design
  direction anyway, and size is what older eyes on a phone need. If he asks for more there
  are two roads and he has to choose: 19-20px with names wrapping to two lines, or a second
  typeface used only for the aliyah names, which would break the one-font decision.
- 2026-09-02 DATES ARE SHOWN IN ISRAEL TIME, STORED IN UTC. models.py gained DISPLAY_TZ
  (Asia/Jerusalem) and to_display(), and closed_reason() passes every datetime through it.
  Before this the stored UTC value was printed straight to the visitor, so the page told a
  reader in Israel a time three hours behind the real one. Storage did not change and must
  not: naive UTC everywhere, translated only at the moment it is read.
- 2026-09-02 `tzdata` was added to requirements.txt. Python's zoneinfo has no timezone
  database of its own on Windows and ZoneInfo("Asia/Jerusalem") raised until it was
  installed. Linux usually carries one, so this is belt and braces for Railway and a
  requirement for any future work on this machine.
- 2026-09-02 The four accented strings in closed_reason() were spelled properly at the same
  time ("O leilão está encerrado" and so on). They are read by visitors and the rest of the
  site is accented; those lines were not.
- 2026-09-02 THE TWO OPENINGS, settled after several passes. Eliahu dictated the final form
  himself, so take it literally rather than reasoning it out again:

    Arvit      name "Ptichat Heichal (Parnassa)"   subtitle "Abertura do Aron"
    Shacharit  name "Ptichat Heichal"              subtitle "Abertura do Aron"

  BOTH carry the same subtitle. What tells them apart is "(Parnassa)" inside the name of the
  night one. An earlier pass put "Parnassa" in the subtitle of the Arvit card and that was
  WRONG; he corrected it. The names travelled "Abertura de parnassa" to "Pticha (Parnassa)"
  to this, the last move being "vamos fazer mais elegante".

  Aliyah.label spells the name and subtitle together wherever there is no card to give
  context, which is what stops the two reading as one item in the panel.

## Where We Stopped, 2026-09-02

Phases 1 to 4 and 6 are built and running LOCALLY ONLY, on SQLite, on the development
machine. THE SITE HAS NEVER BEEN DEPLOYED. That is the main thing left, and it is the whole
of phase 1's "Railway deploy pipeline working end to end", which was never finished.

### Deploying is a first time, not a repeat

- THE GIT REPOSITORY HAS NO COMMITS AT ALL. `git log` says so. Everything ever written on
  this project is uncommitted working tree. There is no remote either. So the first step is
  a first commit and a GitHub repository, not a push.
- Railway auto-deploys from the GitHub main branch, and the local branch is `master`.
- The database changes from SQLite to MySQL at that moment. One codebase, driven by
  DATABASE_URL, decided 2026-09-01, so no code changes. But nothing has ever run on MySQL,
  and two things only work properly there:
    - SELECT ... FOR UPDATE, the row lock that makes two simultaneous bids safe, is IGNORED
      by SQLite. It has never actually been exercised. Test it with real concurrent requests
      once it is on Railway.
    - The tables must be created and the aliyot seeded on the production database. SOLVED
      2026-09-02: the Procfile now runs `python seed.py && gunicorn ...`, so every boot
      creates missing tables, inserts missing aliyot and carries over renamed ones. seed.py
      is idempotent by design and min_bid is only filled when empty, so repeating it is
      harmless. If seeding fails the container fails to start, which is the right way round:
      better loud than a site serving an empty auction.
- The `subtitle` and `cancelled_at` columns were added to the local SQLite file BY HAND with
  ALTER TABLE. A fresh MySQL database gets them from the model automatically, so this is
  only a trap if a database already exists somewhere.
- Environment variables to set in Railway: SECRET_KEY (a real random one), ADMIN_PASSWORD,
  VIEWER_PASSWORD. DATABASE_URL is provided by Railway. SELF_CANCEL_MINUTES defaults to 10
  and can be left out.
- THE APP REFUSES TO START IN PRODUCTION WITHOUT SECRET_KEY, added 2026-09-02. The panel
  keeps its access level in the session cookie, so running on the published development
  default would let anyone forge an admin session. config._secret_key() raises when
  DATABASE_URL is set and SECRET_KEY is not. Locally, with no DATABASE_URL, the development
  default still applies and nothing changes.
- `images_source/` is 4.6 MB of full size originals. It is NOT gitignored on purpose, so the
  originals survive, and it is outside static/ so it is never served.

### Decide before the site is public

NOT BUILT and now overdue, having been noted on 2026-09-01: the public bid form has NO CSRF
TOKEN and NO RATE LIMITING. It was acceptable while the site was on one machine. It is a
different matter once the form is open to the world and each submission creates a real
payment obligation to the kehila. Raise it with Eliahu before launch rather than after.

### Still to build

- Phase 5, closing behaviour. The automatic close by datetime already works, and the manual
  one is in the panel. The final report email is SUSPENDED, see the Email section.
- The "auction is over, go to Yom Kipur" block. See Still Open On The Schedule.
- Phase 7, final QA. The images are swapped in and resized already.
- The footer, pending request 2, never specified.
- The Yom Kipur aliyot list. DONE 2026-09-14, with the kol_nidrei photograph.

## Build Phases

1. Project skeleton: Flask app, MySQL schema, Railway deploy pipeline working end to end with a hello page
2. Public site: occasions, grouped cards, current highest bid display (read-only)
3. Bid flow: form, atomic validation, storage, bid email to admin
4. Admin dashboard: auth, live overview, settings (closing datetime, lock/unlock, min/max fields)
5. Closing behavior: auto + manual close, final report email
6. Design polish: full dark-gold identity, hover animations, hero Ken Burns animation, responsive pass
7. Real images swap-in and final QA

## Status

- [x] Phase 1 - done 2026-09-01. Flask app factory, SQLAlchemy models,
      seed with the 13 Rosh Hashana aliyot, plain listing page, /health.
      Running locally on SQLite. Railway deploy not done yet.
- [x] Phase 2 - done 2026-09-01, after phase 3. Dark and gold identity, hero with Ken Burns,
      server-synced countdown, occasion tabs with the locked Yom Kipur state, cards grouped by
      moment, bid modal, responsive pass. Real images still missing, placeholders in use.
- [x] Phase 3 - done 2026-09-01, built before phase 2. Bid form, server side validation,
      minimum and strictly-greater rules, row-locked transaction, admin notification email
      (code complete, inactive until SMTP env vars are filled).
- [x] Phase 4 - done 2026-09-02. Panel at /admin behind a password, two levels, overview
      table with the winning bidder's contact details, full per-aliyah history including
      cancelled bids, and admin-only settings for the datetimes and the occasion state.
      Self-cancel of a bid built at the same time.
- [ ] Phase 5
- [x] Phase 6 - absorbed into phase 2 on 2026-09-01. The dark and gold identity, hover
      animations, hero Ken Burns and the responsive pass were all built there. A final
      polish pass still happens in phase 7, once the real images are in.
- [ ] Phase 7
