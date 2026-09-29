import os
import re
from datetime import date, datetime
from functools import wraps

import click
from flask import Flask, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

from translations import (
    ALLOWED_LANGUAGES,
    DEFAULT_LANGUAGE,
    LANGUAGE_NAMES,
    translate,
)

app = Flask(__name__)
# Dev-only key so Flask can sign the session cookie; replace with a real secret before deploying.
app.config["SECRET_KEY"] = "dev-secret-key-change-before-production"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///sheconnect.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

AFRICAN_COUNTRIES = [
    "Algeria", "Angola", "Benin", "Botswana", "Burkina Faso", "Burundi",
    "Cabo Verde", "Cameroon", "Central African Republic", "Chad", "Comoros",
    "Democratic Republic of the Congo", "Djibouti", "Egypt",
    "Equatorial Guinea", "Eritrea", "Eswatini", "Ethiopia", "Gabon",
    "Gambia", "Ghana", "Guinea", "Guinea-Bissau", "Ivory Coast", "Kenya",
    "Lesotho", "Liberia", "Libya", "Madagascar", "Malawi", "Mali",
    "Mauritania", "Mauritius", "Morocco", "Mozambique", "Namibia", "Niger",
    "Nigeria", "Republic of the Congo", "Rwanda", "Sao Tome and Principe",
    "Senegal", "Seychelles", "Sierra Leone", "Somalia", "South Africa",
    "South Sudan", "Sudan", "Tanzania", "Togo", "Tunisia", "Uganda",
    "Zambia", "Zimbabwe",
]

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Dashboard "Quick Actions" — a single source of truth so the card grid and
# the "Available Resources" count on the dashboard can never drift apart.
# Titles/descriptions are translation keys, resolved per-request in dashboard().
QUICK_ACTIONS = [
    {"icon": "fa-heart-pulse", "title_key": "qa1_title", "desc_key": "qa1_desc",
     "endpoint": "features", "label_key": "explore_btn"},
    {"icon": "fa-droplet", "title_key": "qa2_title", "desc_key": "qa2_desc",
     "endpoint": "features", "label_key": "explore_btn"},
    {"icon": "fa-shield-heart", "title_key": "qa3_title", "desc_key": "qa3_desc",
     "endpoint": "features", "label_key": "explore_btn"},
    {"icon": "fa-triangle-exclamation", "title_key": "qa4_title", "desc_key": "qa4_desc",
     "endpoint": "emergency", "label_key": "get_help_btn"},
    {"icon": "fa-people-group", "title_key": "qa5_title", "desc_key": "qa5_desc",
     "endpoint": "features", "label_key": "explore_btn"},
    {"icon": "fa-graduation-cap", "title_key": "qa6_title", "desc_key": "qa6_desc",
     "endpoint": "features", "label_key": "explore_btn"},
    {"icon": "fa-laptop-code", "title_key": "qa7_title", "desc_key": "qa7_desc",
     "endpoint": "features", "label_key": "explore_btn"},
    {"icon": "fa-crown", "title_key": "qa8_title", "desc_key": "qa8_desc",
     "endpoint": "subscription", "label_key": "view_plans_btn"},
]

# Features page cards. "live" cards render a real link; everything else
# renders a disabled "Coming Soon" button so nothing points at a broken page.
FEATURE_CARDS = [
    {"icon": "fa-heart-pulse", "title_key": "f1_title", "desc_key": "f1_desc", "status": "coming_soon"},
    {"icon": "fa-droplet", "title_key": "f2_title", "desc_key": "f2_desc", "status": "coming_soon"},
    {"icon": "fa-shield-heart", "title_key": "f3_title", "desc_key": "f3_desc", "status": "coming_soon"},
    {"icon": "fa-phone", "title_key": "f4_title", "desc_key": "f4_desc",
     "status": "live", "endpoint": "emergency", "label_key": "get_help_btn"},
    {"icon": "fa-people-group", "title_key": "f5_title", "desc_key": "f5_desc", "status": "coming_soon"},
    {"icon": "fa-hand-sparkles", "title_key": "f6_title", "desc_key": "f6_desc", "status": "coming_soon"},
    {"icon": "fa-laptop-code", "title_key": "f7_title", "desc_key": "f7_desc", "status": "coming_soon"},
    {"icon": "fa-bell", "title_key": "f8_title", "desc_key": "f8_desc", "status": "coming_soon"},
]


def get_current_language():
    lang = session.get("lang", DEFAULT_LANGUAGE)
    return lang if lang in ALLOWED_LANGUAGES else DEFAULT_LANGUAGE


def localize_cards(cards, lang):
    localized = []
    for card in cards:
        item = dict(card)
        item["title"] = translate(item.pop("title_key"), lang)
        item["description"] = translate(item.pop("desc_key"), lang)
        label_key = item.pop("label_key", None)
        if label_key:
            item["label"] = translate(label_key, lang)
        localized.append(item)
    return localized


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    country = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)


def get_password_errors(password, lang=DEFAULT_LANGUAGE):
    errors = []
    if len(password) < 8:
        errors.append(translate("pw_frag_length", lang))
    if not password[:1].isupper():
        errors.append(translate("pw_frag_upper", lang))
    if not re.search(r"[a-z]", password):
        errors.append(translate("pw_frag_lower", lang))
    if not re.search(r"\d", password):
        errors.append(translate("pw_frag_number", lang))
    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append(translate("pw_frag_symbol", lang))
    return errors


def asset_version(filename):
    # Query-string busts the browser cache whenever the file's contents change,
    # so edited CSS/JS is never served stale from a previous visit.
    path = os.path.join(app.static_folder, filename)
    try:
        return str(int(os.path.getmtime(path)))
    except OSError:
        return "0"


@app.context_processor
def inject_current_user():
    first_name = None
    full_name = None
    user_id = session.get("user_id")
    if user_id is not None:
        user = db.session.get(User, user_id)
        if user:
            full_name = user.full_name
            first_name = user.full_name.split(" ")[0]
        else:
            session.pop("user_id", None)

    lang = get_current_language()

    def t(key, **kwargs):
        return translate(key, lang, **kwargs)

    return {
        "current_first_name": first_name,
        "current_full_name": full_name,
        "css_version": asset_version("css/style.css"),
        "js_version": asset_version("js/script.js"),
        "current_year": date.today().year,
        "t": t,
        "current_lang": lang,
        "current_lang_code": lang.upper(),
        "language_names": LANGUAGE_NAMES,
    }


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


@app.route("/")
def home():
    # Popping this flag means it is only ever True for the single request that
    # follows a successful registration — a refresh or any later visit reads False.
    celebrate = session.pop("just_registered", False)
    return render_template("index.html", celebrate=celebrate)


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("home"))


@app.route("/set-language/<lang_code>")
def set_language(lang_code):
    if lang_code not in ALLOWED_LANGUAGES:
        lang_code = DEFAULT_LANGUAGE
    session["lang"] = lang_code

    next_path = request.args.get("next", "/")
    if not next_path.startswith("/") or next_path.startswith("//"):
        next_path = "/"
    return redirect(next_path)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/features")
def features():
    lang = get_current_language()
    return render_template("features.html", feature_cards=localize_cards(FEATURE_CARDS, lang))


@app.route("/emergency")
def emergency():
    return render_template("emergency.html")


@app.route("/subscription")
def subscription():
    return render_template("subscription.html")


@app.route("/dashboard")
@login_required
def dashboard():
    lang = get_current_language()
    return render_template(
        "dashboard.html",
        quick_actions=localize_cards(QUICK_ACTIONS, lang),
        resource_count=len(QUICK_ACTIONS),
    )


@app.route("/profile")
@login_required
def profile():
    user = db.session.get(User, session["user_id"])
    return render_template(
        "profile.html",
        member_email=user.email,
        member_country=user.country,
        member_date_of_birth=user.date_of_birth.strftime("%d %B %Y"),
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    lang = get_current_language()

    if request.method != "POST":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    errors = {}

    if not email:
        errors["email"] = translate("err_email_required", lang)
    if not password:
        errors["password"] = translate("err_password_required", lang)

    user = None
    if not errors:
        user = User.query.filter_by(email=email).first()
        if not user:
            errors["email"] = translate("err_no_account", lang)
        elif not check_password_hash(user.password_hash, password):
            errors["password"] = translate("err_incorrect_password", lang)

    if errors:
        return render_template("login.html", errors=errors, form_data={"email": email})

    session["user_id"] = user.id
    return redirect(url_for("dashboard"))


@app.route("/register", methods=["GET", "POST"])
def register():
    today = date.today().isoformat()
    lang = get_current_language()
    strength_labels = {
        "veryWeak": translate("strength_very_weak", lang),
        "weak": translate("strength_weak", lang),
        "medium": translate("strength_medium", lang),
        "strong": translate("strength_strong", lang),
        "veryStrong": translate("strength_very_strong", lang),
    }

    if request.method != "POST":
        return render_template(
            "register.html",
            countries=AFRICAN_COUNTRIES,
            today=today,
            strength_labels=strength_labels,
        )

    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    dob_raw = request.form.get("date_of_birth", "").strip()
    country = request.form.get("country", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    errors = {}

    if not full_name:
        errors["full_name"] = translate("err_full_name_required", lang)

    if not email:
        errors["email"] = translate("err_email_required", lang)
    elif not EMAIL_PATTERN.match(email):
        errors["email"] = translate("err_email_invalid", lang)

    dob = None
    if not dob_raw:
        errors["date_of_birth"] = translate("err_dob_required", lang)
    else:
        try:
            dob = datetime.strptime(dob_raw, "%Y-%m-%d").date()
            if dob > date.today():
                errors["date_of_birth"] = translate("err_dob_future", lang)
        except ValueError:
            errors["date_of_birth"] = translate("err_dob_invalid", lang)

    if country not in AFRICAN_COUNTRIES:
        errors["country"] = translate("err_country_required", lang)

    if not password:
        errors["password"] = translate("err_password_required", lang)
    else:
        password_errors = get_password_errors(password, lang)
        if password_errors:
            errors["password"] = translate("pw_must_prefix", lang) + ", ".join(password_errors) + "."

    if not confirm_password:
        errors["confirm_password"] = translate("err_confirm_required", lang)
    elif password and confirm_password != password:
        errors["confirm_password"] = translate("err_passwords_mismatch", lang)

    if "email" not in errors and User.query.filter_by(email=email).first():
        errors["email"] = translate("err_email_exists", lang)

    if errors:
        form_data = {
            "full_name": full_name,
            "email": email,
            "date_of_birth": dob_raw,
            "country": country,
        }
        return render_template(
            "register.html",
            countries=AFRICAN_COUNTRIES,
            today=today,
            errors=errors,
            form_data=form_data,
            strength_labels=strength_labels,
        )

    new_user = User(
        full_name=full_name,
        email=email,
        date_of_birth=dob,
        country=country,
        password_hash=generate_password_hash(password),
    )
    db.session.add(new_user)
    db.session.commit()

    session["user_id"] = new_user.id
    session["just_registered"] = True
    return redirect(url_for("home"))


@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404


@app.cli.command("reset-password")
@click.argument("email")
@click.argument("new_password")
def reset_password_command(email, new_password):
    """Dev-only local utility to set a new password for an existing account.

    Not a web route — only runnable from a terminal with access to this
    project, so it never changes anything unless you explicitly run it.
    Use this if you're locked out of an account and cannot recover the
    original password (which SheConnect never stores and cannot look up).

    Usage:
        flask --app app.py reset-password someone@example.com NewPass@1
    """
    email = email.strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user:
        click.echo(f"No account found for {email}. Nothing was changed.")
        return

    password_errors = get_password_errors(new_password)
    if password_errors:
        click.echo("New password must " + ", ".join(password_errors) + ". Nothing was changed.")
        return

    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    click.echo(f"Password updated for {email}.")


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)
