import os
import re
import uuid
from datetime import date, datetime, timedelta
from functools import wraps

import click
from flask import Flask, abort, redirect, render_template, request, send_from_directory, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from translations import (
    ALLOWED_LANGUAGES,
    DEFAULT_LANGUAGE,
    LANGUAGE_NAMES,
    translate,
)

app = Flask(__name__)
# In production, set the SECRET_KEY environment variable to a real, random
# secret (Flask uses it to sign the session cookie). The hardcoded fallback
# below is only ever used for local development and is not safe to deploy.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-before-production")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///sheconnect.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# Modest cap so a single upload can't exhaust disk space; well above any
# reasonable photo/PDF of evidence.
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

db = SQLAlchemy(app)

# Evidence files are private — stored outside static/ so Flask never serves
# them at a public URL. Only /report-abuse/evidence/<id> can hand one back,
# and only to the user who owns the report it belongs to.
EVIDENCE_UPLOAD_DIR = os.path.join(app.instance_path, "evidence_uploads")
ALLOWED_EVIDENCE_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}

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
    {"icon": "fa-calendar-plus", "title_key": "qa9_title", "desc_key": "qa9_desc",
     "endpoint": "tracker", "label_key": "open_tracker_btn"},
    {"icon": "fa-user-shield", "title_key": "qa10_title", "desc_key": "qa10_desc",
     "endpoint": "report_abuse", "label_key": "report_abuse_btn"},
    {"icon": "fa-book-medical", "title_key": "qa11_title", "desc_key": "qa11_desc",
     "endpoint": "health_resources", "label_key": "read_article_btn"},
    {"icon": "fa-book-open-reader", "title_key": "qa12_title", "desc_key": "qa12_desc",
     "endpoint": "education", "label_key": "explore_btn"},
    {"icon": "fa-comments", "title_key": "qa13_title", "desc_key": "qa13_desc",
     "endpoint": "community", "label_key": "explore_btn"},
    {"icon": "fa-bell", "title_key": "qa14_title", "desc_key": "qa14_desc",
     "endpoint": "notifications", "label_key": "view_notifications_btn"},
]

# Every existing page the Dashboard's site search can navigate to. This is a
# website navigation search over this fixed list, never an external/internet
# search, so it stays a plain endpoint + label lookup with no query building.
SITE_SEARCH_PAGES = [
    ("search_page_home", "home"),
    ("search_page_dashboard", "dashboard"),
    ("search_page_profile", "profile"),
    ("search_page_tracker", "tracker"),
    ("search_page_report_abuse", "report_abuse"),
    ("search_page_health_resources", "health_resources"),
    ("search_page_education", "education"),
    ("search_page_community", "community"),
    ("search_page_notifications", "notifications"),
    ("search_page_emergency", "emergency"),
    ("search_page_subscription", "subscription"),
    ("search_page_about", "about"),
    ("search_page_features", "features"),
]


def localize_site_search_pages(lang):
    return [
        {"name": translate(label_key, lang), "url": url_for(endpoint)}
        for label_key, endpoint in SITE_SEARCH_PAGES
    ]


# The main protected feature pages, in the fixed order the Previous/Next page
# arrows step through. Reuses the same search_page_* labels as the Dashboard
# search above, so a page's name is identical in both places.
PAGE_NAV_ORDER = [
    "home", "dashboard", "about", "features", "emergency", "subscription", "profile",
]

PAGE_NAV_LABEL_KEYS = {endpoint: label_key for label_key, endpoint in SITE_SEARCH_PAGES}


# Health Articles & Resources. Card titles/summaries/categories are
# translated (short strings, resolved per-request like the quick actions
# above); the full article body stays in English for this increment,
# matching the same scope decision already made for the Cycle Tracker and
# Report Abuse pages, and is disclosed as such.
HEALTH_ARTICLES = [
    {
        "slug": "menstrual-health",
        "icon": "fa-droplet",
        "category_key": "menstrual",
        "title_key": "ha1_title",
        "summary_key": "ha1_summary",
        "category_label_key": "ha1_category",
        "body": [
            "A menstrual cycle is the natural, monthly process your body goes through to "
            "prepare for a possible pregnancy. Most cycles last somewhere between 21 and 35 "
            "days, counted from the first day of one period to the first day of the next. "
            "There is no single 'normal' because every body is a little different, and your "
            "own cycle can even vary slightly from month to month.",

            "During your period, it is common to experience cramping, tiredness, mood "
            "changes, or bloating. These happen because of natural hormone changes and "
            "usually pass on their own within a few days. Gentle exercise, a warm compress "
            "on your lower abdomen, staying hydrated and getting enough rest can all help "
            "make these days more comfortable.",

            "Keeping track of your cycle can help you understand your own pattern, notice "
            "changes early, and feel more prepared each month. You can use the Cycle "
            "Tracker on SheConnect to record it.",

            "You should speak to a healthcare provider if you experience very heavy "
            "bleeding that soaks through a pad or tampon every hour, pain that stops you "
            "from doing normal daily activities, periods that suddenly become very "
            "irregular, or if your period has not started by age 16. These can usually be "
            "managed once a professional understands what is happening in your specific "
            "situation.",

            "This article is general educational information and is not a substitute for "
            "advice from a qualified healthcare provider.",
        ],
    },
    {
        "slug": "personal-hygiene",
        "icon": "fa-hand-sparkles",
        "category_key": "hygiene",
        "title_key": "ha2_title",
        "summary_key": "ha2_summary",
        "category_label_key": "ha2_category",
        "body": [
            "Good hygiene habits protect your health and can help you feel more "
            "comfortable and confident every day. Simple daily habits go a long way, for "
            "example washing your body and face, brushing your teeth twice a day, wearing "
            "clean clothes, and washing your hands before eating and after using the "
            "toilet.",

            "During your period, changing your pad, tampon or cloth regularly (roughly "
            "every 4 to 6 hours) helps prevent irritation and odour, and supports better "
            "health. If you use reusable cloths, wash them with soap and clean water and "
            "dry them fully in sunlight where possible before reusing them.",

            "If access to water, soap or menstrual products is limited where you live, you "
            "are not alone, and it does not mean you are doing anything wrong. Clean, "
            "folded cloth can be a safe option when washed and dried properly. Community "
            "groups, schools or local clinics can sometimes point you toward free or "
            "low-cost products, so it is always worth asking.",

            "Hygiene is about health and comfort, not shame. Every person deserves to feel "
            "clean, cared for and dignified, regardless of their circumstances.",
        ],
    },
    {
        "slug": "mental-health",
        "icon": "fa-brain",
        "category_key": "mental",
        "title_key": "ha3_title",
        "summary_key": "ha3_summary",
        "category_label_key": "ha3_category",
        "body": [
            "Mental health is just as important as physical health. It is normal to have "
            "good days and hard days. Feeling stressed, worried, sad or overwhelmed from "
            "time to time does not mean something is wrong with you.",

            "Common challenges many women and girls face include stress from school, work "
            "or family responsibilities, anxiety about the future, and feelings of sadness "
            "or loneliness. These feelings are valid, and there are things that can help.",

            "Simple daily habits can support your emotional wellbeing: talking to someone "
            "you trust, keeping a consistent sleep routine, taking short breaks during a "
            "busy day, gentle movement or a walk outside, and slow, deep breathing when you "
            "feel overwhelmed.",

            "It may be time to reach out for extra support if sadness, worry or "
            "hopelessness lasts for more than two weeks, if you lose interest in things you "
            "used to enjoy, or if you ever have thoughts of harming yourself. If this "
            "happens, please talk to a trusted adult, a counsellor, or a healthcare "
            "provider as soon as you can. If you are in immediate danger, visit the "
            "Emergency Help page right away.",

            "Asking for help is a sign of strength, not weakness. You deserve support.",
        ],
    },
    {
        "slug": "sexual-reproductive-health",
        "icon": "fa-venus",
        "category_key": "reproductive",
        "title_key": "ha4_title",
        "summary_key": "ha4_summary",
        "category_label_key": "ha4_category",
        "body": [
            "Sexual and reproductive health covers how your body grows and changes, how "
            "relationships and consent work, and how to access accurate, trustworthy "
            "information so you can make informed choices about your own body.",

            "Consent means freely agreeing to something, without pressure, fear or "
            "manipulation, and it can be withdrawn at any time. You always have the right "
            "to say no, and your body belongs to you.",

            "Regular check-ups with a healthcare provider, when accessible to you, can help "
            "catch and address concerns early, and are a normal, healthy part of taking "
            "care of yourself, not something to feel embarrassed about.",

            "If you have questions or concerns, a trusted adult, a school counsellor, or a "
            "local clinic can be a good place to start. You deserve clear answers, treated "
            "with respect and without judgement.",

            "This article offers general education only. For guidance about your own body "
            "or health, please speak with a qualified healthcare provider.",
        ],
    },
    {
        "slug": "nutrition",
        "icon": "fa-apple-whole",
        "category_key": "nutrition",
        "title_key": "ha5_title",
        "summary_key": "ha5_summary",
        "category_label_key": "ha5_category",
        "body": [
            "Good nutrition supports your energy, growth, mood and overall health. A "
            "balanced plate generally includes vegetables or fruit, a source of protein "
            "(such as beans, eggs, fish or meat), whole grains, and plenty of water.",

            "Iron-rich foods are especially helpful around your period, since your body "
            "loses some iron during menstruation. Good examples include beans, leafy green "
            "vegetables, groundnuts and, where available, lean meat.",

            "Eating well does not have to be expensive. Local, seasonal fruits and "
            "vegetables are often the most affordable and freshest option. Simple meals "
            "made from a few whole ingredients are just as valuable as anything "
            "complicated.",

            "Try to drink water regularly throughout the day, especially in hot weather or "
            "during exercise. Good nutrition is about balance and consistency, not "
            "perfection or strict rules. Small, steady habits make the biggest "
            "difference.",
        ],
    },
    {
        "slug": "recognising-abuse",
        "icon": "fa-eye",
        "category_key": "abuse",
        "title_key": "ha6_title",
        "summary_key": "ha6_summary",
        "category_label_key": "ha6_category",
        "body": [
            "Abuse can take more than one form. It may be physical (hitting, pushing), "
            "emotional or psychological (constant criticism, threats, humiliation), "
            "financial (controlling your money or stopping you from earning), or sexual "
            "(any unwanted sexual contact or pressure).",

            "Some warning signs to be aware of, in your own relationships or in someone you "
            "care about, include being controlled or constantly checked on, being isolated "
            "from friends or family, feeling afraid of someone's reactions, unexplained "
            "injuries, and being constantly blamed or put down.",

            "If any of this sounds familiar, please remember: abuse is never your fault, "
            "no matter what you were told or how it happened.",

            "If you are able to, talk to someone you trust about what is happening. "
            "SheConnect's confidential Report Abuse feature lets you record what happened "
            "privately, because only you can see your own report. If you are in immediate "
            "danger, please go to the Emergency Help page and contact your local emergency "
            "service right away.",

            "You deserve to be safe, respected and heard.",
        ],
    },
]


def get_health_article(slug):
    return next((a for a in HEALTH_ARTICLES if a["slug"] == slug), None)


def localize_health_articles(lang):
    localized = []
    for article in HEALTH_ARTICLES:
        item = dict(article)
        item["title"] = translate(item.pop("title_key"), lang)
        item["summary"] = translate(item.pop("summary_key"), lang)
        item["category_label"] = translate(item.pop("category_label_key"), lang)
        localized.append(item)
    return localized

# Features page cards. "live" cards render a real link; everything else
# renders a disabled "Coming Soon" button so nothing points at a broken page.
FEATURE_CARDS = [
    {"icon": "fa-heart-pulse", "title_key": "f1_title", "desc_key": "f1_desc",
     "status": "live", "endpoint": "health_resources", "label_key": "explore_health_resources_btn"},
    {"icon": "fa-droplet", "title_key": "f2_title", "desc_key": "f2_desc",
     "status": "live", "endpoint": "tracker", "label_key": "open_cycle_tracker_btn"},
    {"icon": "fa-shield-heart", "title_key": "f3_title", "desc_key": "f3_desc",
     "status": "live", "endpoint": "report_abuse", "label_key": "report_confidentially_btn"},
    {"icon": "fa-phone", "title_key": "f4_title", "desc_key": "f4_desc",
     "status": "live", "endpoint": "emergency", "label_key": "get_help_btn"},
    {"icon": "fa-people-group", "title_key": "f5_title", "desc_key": "f5_desc",
     "status": "live", "endpoint": "community", "label_key": "join_community_btn"},
    {"icon": "fa-hand-sparkles", "title_key": "f6_title", "desc_key": "f6_desc",
     "status": "live", "endpoint": "health_article", "endpoint_args": {"slug": "personal-hygiene"},
     "label_key": "read_hygiene_resources_btn"},
    {"icon": "fa-laptop-code", "title_key": "f7_title", "desc_key": "f7_desc",
     "status": "live", "endpoint": "education", "label_key": "start_learning_btn"},
    {"icon": "fa-bell", "title_key": "f8_title", "desc_key": "f8_desc",
     "status": "live", "endpoint": "notifications", "label_key": "view_notifications_btn"},
]

# Technology Learning courses. Card titles, descriptions and durations are
# translated (short strings, resolved per-request); the lesson body stays in
# English for this increment, matching the same scope decision already made
# for the other educational content on this site.
TECH_COURSES = [
    {
        "slug": "computer-basics",
        "icon": "fa-desktop",
        "difficulty_key": "difficulty_beginner",
        "title_key": "course1_title",
        "desc_key": "course1_desc",
        "duration_key": "course1_duration",
        "lessons": [
            {
                "title_key": "course1_lesson1_title",
                "explanation": [
                    "A computer is made of several parts that work together. The two main "
                    "types of parts are hardware and software.",

                    "Hardware includes the parts you can touch, such as the screen, the "
                    "keyboard, the mouse or touchpad, and the case that holds the main "
                    "processor and storage.",

                    "Software is the set of programs that tell the hardware what to do. "
                    "This includes the operating system, such as Windows or macOS, and "
                    "programs like a web browser or word processor.",

                    "The processor, often called the CPU, acts like the brain of the "
                    "computer. It carries out instructions very quickly so the computer "
                    "can respond when you type, click or open a program.",
                ],
                "example": (
                    "When you press a key on the keyboard, the keyboard sends a signal to "
                    "the processor. The processor works out what letter you pressed and "
                    "sends it to the screen so you see it appear."
                ),
                "activity": (
                    "Look at the computer or device you are using right now. Try to name "
                    "three hardware parts you can see or touch, such as the screen, "
                    "keyboard and mouse."
                ),
            },
            {
                "title_key": "course1_lesson2_title",
                "explanation": [
                    "Files are the individual items you save on a computer, such as a "
                    "document, a photo or a song. Every file has a name and a file type, "
                    "shown by letters after a dot, such as docx for a document or jpg for "
                    "a photo.",

                    "Folders help you keep files organised. You can think of a folder "
                    "like a drawer that holds related files together, so you do not have "
                    "to search through everything at once.",

                    "Software falls into different categories. System software, like the "
                    "operating system, runs the computer itself. Application software, "
                    "like a word processor or web browser, helps you complete specific "
                    "tasks.",

                    "Keeping your files and folders organised with clear names makes it "
                    "much easier to find what you need later.",
                ],
                "example": (
                    "You could create a folder called School Work, and inside it, save "
                    "files such as Essay Draft and Class Notes, instead of leaving them "
                    "scattered across the computer."
                ),
                "activity": (
                    "On paper or in your mind, plan how you would organise three folders "
                    "for your own files, for example School, Photos and Personal "
                    "Documents."
                ),
            },
            {
                "title_key": "course1_lesson3_title",
                "explanation": [
                    "Now that you understand the main parts of a computer and how files "
                    "and folders work, it helps to practise a few everyday actions.",

                    "Opening a program usually means clicking or double clicking its "
                    "icon. Closing a program means selecting the close button, often "
                    "shown as an X in the corner of the window.",

                    "Saving a file regularly protects your work. Most programs let you "
                    "save by selecting a Save option in a menu, or by using a keyboard "
                    "shortcut such as Ctrl and S together.",

                    "Restarting a computer can solve many small problems, such as a "
                    "program that is running slowly or not responding.",
                ],
                "example": (
                    "If you are writing a document and want to keep your progress, you "
                    "would select File, then Save, and choose a folder and file name "
                    "before saving."
                ),
                "activity": (
                    "If you have access to a computer, try opening a program, creating a "
                    "new folder, and saving a simple text file inside it. If you do not "
                    "have access right now, write down the steps you would follow."
                ),
            },
        ],
    },
    {
        "slug": "internet-safety",
        "icon": "fa-shield-halved",
        "difficulty_key": "difficulty_beginner",
        "title_key": "course2_title",
        "desc_key": "course2_desc",
        "duration_key": "course2_duration",
        "lessons": [
            {
                "title_key": "course2_lesson1_title",
                "explanation": [
                    "A password protects your accounts from people who should not have "
                    "access to them. A weak password can be guessed or discovered "
                    "quickly, which puts your information at risk.",

                    "A strong password is usually at least eight characters long and "
                    "combines uppercase letters, lowercase letters, numbers and symbols.",

                    "It is safer to use a different password for each important account, "
                    "such as email and banking, so that if one password is discovered, "
                    "your other accounts stay protected.",

                    "A password manager is a tool that can safely store many passwords "
                    "for you, so you do not need to remember every one yourself.",
                ],
                "example": (
                    "A weak password like password123 is easy to guess. A stronger "
                    "version might combine unrelated words and numbers, such as "
                    "Purple7River!Star."
                ),
                "activity": (
                    "Think of an account you use often. Without writing your real "
                    "password anywhere, think through whether it includes uppercase and "
                    "lowercase letters, a number and a symbol, and consider how you could "
                    "make it stronger."
                ),
            },
            {
                "title_key": "course2_lesson2_title",
                "explanation": [
                    "A scam is an attempt to trick you into giving away money, passwords "
                    "or personal information. Scams often arrive as emails, messages or "
                    "links that look convincing but are not genuine.",

                    "Warning signs of a scam include urgent language asking you to act "
                    "immediately, requests for your password or bank details, and links "
                    "or senders that look slightly different from the real organisation.",

                    "Before clicking a link, you can check where it leads by looking "
                    "closely at the web address. Misspelled names or unusual extra words "
                    "are common signs of a fake website.",

                    "If a message feels suspicious, it is safer to contact the "
                    "organisation directly through their official website or phone "
                    "number, rather than replying to the message or clicking its links.",
                ],
                "example": (
                    "A message claiming to be from your bank might ask you to click a "
                    "link and enter your password urgently. A real bank will never ask "
                    "for your full password this way."
                ),
                "activity": (
                    "Think of a message or email you have received that felt unusual. "
                    "Without clicking anything, list two or three signs that made it "
                    "feel suspicious."
                ),
            },
            {
                "title_key": "course2_lesson3_title",
                "explanation": [
                    "Personal information includes details like your full name, home "
                    "address, phone number, school and daily routine. Sharing too much "
                    "of this online can put your safety and privacy at risk.",

                    "Before posting online, it helps to ask yourself who can see the "
                    "post, and whether the information could be used to find or identify "
                    "you in person.",

                    "Privacy settings on social media let you control who can see your "
                    "posts and personal details. It is worth checking these settings "
                    "regularly, since they can change when apps are updated.",

                    "If someone online makes you feel uncomfortable or unsafe, you can "
                    "block them, tell a trusted adult, and if needed, use SheConnect's "
                    "confidential Report Abuse feature.",
                ],
                "example": (
                    "Instead of posting that you are home alone or sharing your exact "
                    "location in real time, you could share a photo or update later, "
                    "after you have left that place."
                ),
                "activity": (
                    "Open the privacy settings on one app or account you use, if you "
                    "have access to one, and check who is currently able to see your "
                    "posts and personal details."
                ),
            },
        ],
    },
    {
        "slug": "intro-to-coding",
        "icon": "fa-code",
        "difficulty_key": "difficulty_beginner",
        "title_key": "course3_title",
        "desc_key": "course3_desc",
        "duration_key": "course3_duration",
        "lessons": [
            {
                "title_key": "course3_lesson1_title",
                "explanation": [
                    "Coding means writing instructions that a computer can follow. "
                    "These instructions are written in a programming language, which is "
                    "a structured way of communicating with a computer.",

                    "Computers do not understand human language directly. A programming "
                    "language acts like a bridge, turning instructions that people can "
                    "read into a form the computer can carry out.",

                    "There are many programming languages, each suited to different "
                    "tasks. Some common ones include Python, JavaScript and HTML. Many "
                    "beginners start with Python because its instructions read similarly "
                    "to plain English.",

                    "Coding is used to build many things you may use every day, "
                    "including websites, mobile apps, games and the software that runs "
                    "on computers and phones.",
                ],
                "example": (
                    "A simple coded instruction might tell a computer to display a "
                    "message on the screen, such as showing the words Welcome to "
                    "SheConnect when a website loads."
                ),
                "activity": (
                    "Think of three apps or websites you use often. Write down what you "
                    "think a computer might need to be told to do for each one to work."
                ),
            },
            {
                "title_key": "course3_lesson2_title",
                "explanation": [
                    "Computers follow instructions exactly as written, one step at a "
                    "time, in the order they are given. This is why coding often "
                    "involves careful, logical thinking.",

                    "An algorithm is simply a clear set of steps for completing a task. "
                    "You already use algorithms in everyday life, such as the steps you "
                    "follow to make tea or get ready for school.",

                    "Good algorithms are precise. If a step is missing or unclear, the "
                    "computer cannot guess what you meant, so it may not work correctly.",

                    "Testing your instructions carefully, one step at a time, helps you "
                    "find and fix mistakes before the final result.",
                ],
                "example": (
                    "An algorithm for making tea might be: boil water, place a tea bag "
                    "in a cup, pour in the hot water, wait a few minutes, then add milk "
                    "or sugar if you like."
                ),
                "activity": (
                    "Write out the steps of an everyday algorithm, such as how you get "
                    "ready in the morning or how you walk to a familiar place, as "
                    "clearly as you can."
                ),
            },
            {
                "title_key": "course3_lesson3_title",
                "explanation": [
                    "A program is a set of coded instructions saved together so a "
                    "computer can run them. Even a very short program can produce a "
                    "useful result.",

                    "One of the most common first programs simply displays a message on "
                    "the screen. This is often called a Hello World program, and it "
                    "helps confirm that your code runs correctly.",

                    "In Python, you can display a message using the print function. "
                    "Typing print, followed by your message inside quotation marks and "
                    "brackets, tells the computer to show that text.",

                    "Starting small and testing often is a good habit. As you become "
                    "more comfortable, you can build up to longer and more complex "
                    "programs.",
                ],
                "example": (
                    "The instruction print(\"Hello, world\") tells a computer to display "
                    "the text Hello, world on the screen when the program runs."
                ),
                "activity": (
                    "On paper, or using any code editor you have access to, write out "
                    "the instruction print followed by your own name in quotation marks."
                ),
            },
        ],
    },
    {
        "slug": "python-basics",
        "icon": "fa-terminal",
        "difficulty_key": "difficulty_beginner",
        "title_key": "course4_title",
        "desc_key": "course4_desc",
        "duration_key": "course4_duration",
        "lessons": [
            {
                "title_key": "course4_lesson1_title",
                "explanation": [
                    "In Python, you store information using variables. A variable is "
                    "like a labelled container that holds a value, which you can use "
                    "again later in your program.",

                    "Python has several common data types. Text is stored as a string, "
                    "whole numbers are stored as integers, and numbers with decimal "
                    "points are stored as floats.",

                    "To create a variable, you choose a name and use an equals sign to "
                    "give it a value. For example, name equals Amina stores the text "
                    "Amina inside a variable called name.",

                    "Choosing clear, descriptive variable names makes your code easier "
                    "to read and understand later, both for you and for anyone else "
                    "looking at it.",
                ],
                "example": (
                    "The line age = 16 creates a variable called age and stores the "
                    "number 16 inside it, which the program can use later."
                ),
                "activity": (
                    "Write two variables of your own, one storing your name as text and "
                    "one storing your age as a number, using the pattern shown above."
                ),
            },
            {
                "title_key": "course4_lesson2_title",
                "explanation": [
                    "Programs often need to make decisions based on information. In "
                    "Python, this is done using an if statement, which checks whether "
                    "something is true.",

                    "An if statement runs a block of code only when its condition is "
                    "true. You can add an else section to run different code when the "
                    "condition is false.",

                    "Conditions often compare values, such as checking whether a number "
                    "is greater than another number, or whether two pieces of text are "
                    "exactly the same.",

                    "Using conditions allows your program to respond differently "
                    "depending on the situation, instead of always doing exactly the "
                    "same thing.",
                ],
                "example": (
                    "A program could check if age is 18 or more and print You are an "
                    "adult, or otherwise print You are not yet 18, using an if and an "
                    "else."
                ),
                "activity": (
                    "Think of a simple decision, such as whether it is raining, and "
                    "write out in plain English what your program should do in each "
                    "case, using an if and an else."
                ),
            },
            {
                "title_key": "course4_lesson3_title",
                "explanation": [
                    "You can combine variables and conditions to build a small, useful "
                    "program. Planning what you want the program to do before you start "
                    "writing code makes the process much easier.",

                    "A good first step is to write down the goal of your program in "
                    "plain language, then break it into smaller steps you can turn into "
                    "code one at a time.",

                    "Testing your program after each small change helps you catch "
                    "mistakes early, rather than trying to fix many problems at once at "
                    "the end.",

                    "Do not worry about writing perfect code the first time. Improving "
                    "a program gradually, through practice and small corrections, is a "
                    "normal part of learning to code.",
                ],
                "example": (
                    "A small program could store a person's age in a variable, then use "
                    "an if statement to print whether they are old enough to vote, based "
                    "on the rules in their country."
                ),
                "activity": (
                    "Plan a very small program of your own, such as one that stores "
                    "your favourite subject as a variable and prints a short message "
                    "about it. Write out the steps in plain language first."
                ),
            },
        ],
    },
    {
        "slug": "web-development",
        "icon": "fa-globe",
        "difficulty_key": "difficulty_intermediate",
        "title_key": "course5_title",
        "desc_key": "course5_desc",
        "duration_key": "course5_duration",
        "lessons": [
            {
                "title_key": "course5_lesson1_title",
                "explanation": [
                    "A website is a collection of linked pages that you can view "
                    "through a web browser, such as Chrome or Firefox. Websites are "
                    "stored on computers called servers, which send the pages to your "
                    "device when you visit them.",

                    "Every website is built using a combination of technologies. The "
                    "two most basic building blocks are HTML, which structures the "
                    "content, and CSS, which styles how it looks.",

                    "A browser reads the code sent by the server and turns it into the "
                    "page you see, including text, images, colours and layout.",

                    "Understanding how websites are built helps you make sense of what "
                    "you see online, and gives you the foundation to start creating "
                    "your own web pages.",
                ],
                "example": (
                    "When you visit a website, your browser requests the page from a "
                    "server, receives the HTML and CSS code, and displays it as the "
                    "finished page you see on screen."
                ),
                "activity": (
                    "Visit any website and try to identify three separate elements on "
                    "the page, such as a heading, an image and a button, that were "
                    "likely created using HTML."
                ),
            },
            {
                "title_key": "course5_lesson2_title",
                "explanation": [
                    "HTML, short for HyperText Markup Language, is used to structure "
                    "the content of a webpage, such as headings, paragraphs, images and "
                    "links.",

                    "HTML uses tags to mark different parts of a page. A tag is usually "
                    "written with angle brackets, and most tags have an opening and a "
                    "closing version.",

                    "Common HTML tags include one for a main heading, one for a "
                    "paragraph of text, and one for an image, each used to structure a "
                    "different kind of content.",

                    "Well organised HTML makes a webpage easier to read for both people "
                    "and browsers, and forms the foundation that CSS later builds on.",
                ],
                "example": (
                    "The tag h1 with the text Welcome to SheConnect inside it creates a "
                    "large heading that displays that text on a webpage."
                ),
                "activity": (
                    "On paper, write out simple HTML for a small webpage with one "
                    "heading and one paragraph, using the heading and paragraph tag "
                    "pattern shown above."
                ),
            },
            {
                "title_key": "course5_lesson3_title",
                "explanation": [
                    "CSS, short for Cascading Style Sheets, is used to style HTML "
                    "content, controlling things like colours, spacing, fonts and "
                    "layout so a webpage looks organised and attractive.",

                    "CSS works by selecting an HTML element and then describing how it "
                    "should look. For example, you can select all paragraphs and set "
                    "their colour, size or spacing.",

                    "A basic CSS rule has two parts: a selector, which chooses what to "
                    "style, and a set of properties inside curly brackets, which "
                    "describe how it should look.",

                    "Together, HTML and CSS form the foundation of almost every website "
                    "you visit. Once you are comfortable with the basics, you can "
                    "explore adding interactivity with JavaScript.",
                ],
                "example": (
                    "A rule that selects the paragraph tag and sets its colour to "
                    "purple tells the browser to display every paragraph on the page in "
                    "purple text."
                ),
                "activity": (
                    "Imagine you want every heading on a page to appear in pink. Write "
                    "out what a simple CSS rule for that might look like, using the "
                    "pattern shown above."
                ),
            },
        ],
    },
    {
        "slug": "git-and-github",
        "icon": "fa-code-branch",
        "difficulty_key": "difficulty_intermediate",
        "title_key": "course6_title",
        "desc_key": "course6_desc",
        "duration_key": "course6_duration",
        "lessons": [
            {
                "title_key": "course6_lesson1_title",
                "explanation": [
                    "Git is a tool that helps you keep track of changes to your files "
                    "over time, which is especially useful when writing code. It lets "
                    "you save versions of your work and go back to an earlier version "
                    "if needed.",

                    "Without Git, it can be difficult to remember what changed between "
                    "different versions of a project, especially if several people are "
                    "working on it together.",

                    "Git works by saving snapshots of your project at different points "
                    "in time. Each snapshot records exactly what your files looked like "
                    "at that moment.",

                    "Learning Git takes practice, but it is one of the most valuable "
                    "skills for anyone interested in software development or working on "
                    "shared projects.",
                ],
                "example": (
                    "If you accidentally break part of your code, Git allows you to "
                    "look back at an earlier saved version and see exactly what "
                    "changed, so you can fix the problem."
                ),
                "activity": (
                    "Think of a piece of written work you have edited many times, such "
                    "as an essay. Imagine how it could help to have saved versions you "
                    "could return to at any point."
                ),
            },
            {
                "title_key": "course6_lesson2_title",
                "explanation": [
                    "A repository, often shortened to repo, is a project folder that "
                    "Git is keeping track of. It contains your files along with the "
                    "full history of changes made to them.",

                    "A commit is a saved snapshot of your project at a specific point "
                    "in time. Each commit usually includes a short message describing "
                    "what was changed and why.",

                    "Writing clear commit messages, such as Added login page or Fixed "
                    "spelling in article, makes it much easier to understand a "
                    "project's history later.",

                    "Git tracks changes at the file level, so you can see exactly which "
                    "files were added, edited or removed in each commit you make.",
                ],
                "example": (
                    "After finishing a new page for a project, you might make a commit "
                    "with the message Added new education page, which saves that exact "
                    "version of your work."
                ),
                "activity": (
                    "Think of a small change you could make to a document, such as "
                    "fixing a typing mistake. Write a short, clear commit message "
                    "describing that change."
                ),
            },
            {
                "title_key": "course6_lesson3_title",
                "explanation": [
                    "GitHub is a website that hosts Git projects online. It lets you "
                    "store your code safely, share it with others and work together on "
                    "the same project.",

                    "A basic workflow usually involves saving your changes locally with "
                    "Git, then uploading, or pushing, those changes to GitHub so others "
                    "can see your progress.",

                    "Once a project is on GitHub, other people can view it, suggest "
                    "changes, or copy it to build their own version, depending on the "
                    "permissions you choose.",

                    "Many software projects around the world are shared and developed "
                    "using GitHub, making it a valuable platform to become familiar "
                    "with as you continue learning.",
                ],
                "example": (
                    "After making several commits to a project, you would push those "
                    "changes to GitHub, where the updated files then become visible to "
                    "anyone with access to the repository."
                ),
                "activity": (
                    "If you have a GitHub account, look at any public repository and "
                    "try to identify where the file list and commit history are shown. "
                    "If you do not have an account, write down what you think those two "
                    "sections would show."
                ),
            },
        ],
    },
]


def get_course(slug):
    return next((c for c in TECH_COURSES if c["slug"] == slug), None)


def localize_courses(lang, completed_slugs=None):
    completed_slugs = completed_slugs or set()
    localized = []
    for course in TECH_COURSES:
        item = dict(course)
        item["title"] = translate(item.pop("title_key"), lang)
        item["description"] = translate(item.pop("desc_key"), lang)
        item["duration"] = translate(item.pop("duration_key"), lang)
        item["difficulty"] = translate(item.pop("difficulty_key"), lang)
        item["is_completed"] = item["slug"] in completed_slugs
        localized.append(item)
    return localized


def localize_single_course(course, lang):
    item = dict(course)
    item["title"] = translate(item.pop("title_key"), lang)
    item["description"] = translate(item.pop("desc_key"), lang)
    item["duration"] = translate(item.pop("duration_key"), lang)
    item["difficulty"] = translate(item.pop("difficulty_key"), lang)
    return item


# Scholarship Opportunities. These are clearly-labelled demonstration
# listings only, not real, currently active programmes. Each one links to an
# internal detail page (never a guessed external URL) that repeats the same
# information alongside a disclaimer to verify everything on the relevant
# official website before applying.
SCHOLARSHIPS = [
    {
        "slug": "stem-scholarship",
        "icon": "fa-award",
        "name_key": "scholarship1_name",
        "desc_key": "scholarship1_desc",
        "eligibility_key": "scholarship1_eligibility",
        "level_key": "scholarship1_level",
        "status_key": "scholarship1_status",
    },
    {
        "slug": "secondary-education-grant",
        "icon": "fa-graduation-cap",
        "name_key": "scholarship2_name",
        "desc_key": "scholarship2_desc",
        "eligibility_key": "scholarship2_eligibility",
        "level_key": "scholarship2_level",
        "status_key": "scholarship2_status",
    },
    {
        "slug": "tech-leadership-award",
        "icon": "fa-hand-holding-dollar",
        "name_key": "scholarship3_name",
        "desc_key": "scholarship3_desc",
        "eligibility_key": "scholarship3_eligibility",
        "level_key": "scholarship3_level",
        "status_key": "scholarship3_status",
    },
    {
        "slug": "nursing-bursary",
        "icon": "fa-scroll",
        "name_key": "scholarship4_name",
        "desc_key": "scholarship4_desc",
        "eligibility_key": "scholarship4_eligibility",
        "level_key": "scholarship4_level",
        "status_key": "scholarship4_status",
    },
]


def get_scholarship(slug):
    return next((s for s in SCHOLARSHIPS if s["slug"] == slug), None)


def localize_scholarships(lang):
    localized = []
    for scholarship in SCHOLARSHIPS:
        item = dict(scholarship)
        item["name"] = translate(item.pop("name_key"), lang)
        item["description"] = translate(item.pop("desc_key"), lang)
        item["eligibility"] = translate(item.pop("eligibility_key"), lang)
        item["level"] = translate(item.pop("level_key"), lang)
        item["status"] = translate(item.pop("status_key"), lang)
        localized.append(item)
    return localized


def localize_single_scholarship(scholarship, lang):
    item = dict(scholarship)
    item["name"] = translate(item.pop("name_key"), lang)
    item["description"] = translate(item.pop("desc_key"), lang)
    item["eligibility"] = translate(item.pop("eligibility_key"), lang)
    item["level"] = translate(item.pop("level_key"), lang)
    item["status"] = translate(item.pop("status_key"), lang)
    return item


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


class MenstrualCycle(db.Model):
    __tablename__ = "menstrual_cycle"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    cycle_length = db.Column(db.Integer, nullable=False, default=28)
    predicted_next_period = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    symptom_records = db.relationship(
        "SymptomRecord", backref="cycle", cascade="all, delete-orphan"
    )


class SymptomRecord(db.Model):
    __tablename__ = "symptom_record"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    cycle_id = db.Column(db.Integer, db.ForeignKey("menstrual_cycle.id"), nullable=False)
    symptom = db.Column(db.String(80), nullable=False)
    mood = db.Column(db.String(40), nullable=False)
    record_date = db.Column(db.Date, nullable=False)


class AbuseReport(db.Model):
    __tablename__ = "abuse_report"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    report_type = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=False)
    incident_date = db.Column(db.Date, nullable=False)
    location = db.Column(db.String(200), nullable=True)
    immediate_danger = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(40), nullable=False, default="Submitted")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    evidence_files = db.relationship(
        "Evidence", backref="report", cascade="all, delete-orphan"
    )

    @property
    def reference_number(self):
        return f"SC-{self.id:06d}"


class Evidence(db.Model):
    __tablename__ = "evidence"

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey("abuse_report.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class CourseProgress(db.Model):
    __tablename__ = "course_progress"
    __table_args__ = (
        db.UniqueConstraint("user_id", "course_slug", name="uq_course_progress_user_course"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    course_slug = db.Column(db.String(80), nullable=False)
    completed = db.Column(db.Boolean, nullable=False, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)


class CommunityPost(db.Model):
    __tablename__ = "community_post"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(40), nullable=False)
    is_anonymous = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    support_reactions = db.relationship(
        "SupportReaction", backref="post", cascade="all, delete-orphan"
    )


class SupportReaction(db.Model):
    __tablename__ = "support_reaction"
    __table_args__ = (
        db.UniqueConstraint("user_id", "post_id", name="uq_support_reaction_user_post"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("community_post.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Notification(db.Model):
    __tablename__ = "notification"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(255), nullable=True)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


def create_notification(user_id, message, link=None):
    # Adds to the session only; the calling route's own db.session.commit()
    # (right after the action that triggered this notification) saves it,
    # so the notification and its triggering change commit atomically.
    db.session.add(Notification(user_id=user_id, message=message, link=link))


# Community post categories. The stored value on each post is the short key
# (e.g. "general"), never the translated label, so a post stays correctly
# categorised no matter which language the viewer has selected.
COMMUNITY_CATEGORIES = [
    {"key": "general", "label_key": "community_cat_general"},
    {"key": "womens_health", "label_key": "community_cat_womens_health"},
    {"key": "education", "label_key": "community_cat_education"},
    {"key": "safety", "label_key": "community_cat_safety"},
    {"key": "encouragement", "label_key": "community_cat_encouragement"},
]

COMMUNITY_CATEGORY_KEYS = {c["key"] for c in COMMUNITY_CATEGORIES}


def localize_community_categories(lang):
    return [
        {"key": c["key"], "label": translate(c["label_key"], lang)}
        for c in COMMUNITY_CATEGORIES
    ]


CYCLE_LENGTH_MIN = 15
CYCLE_LENGTH_MAX = 45

ABUSE_REPORT_TYPES = [
    "Physical Abuse", "Sexual Abuse", "Emotional or Psychological Abuse",
    "Financial Abuse", "Harassment", "Other",
]

SYMPTOM_OPTIONS = [
    "Cramps", "Headache", "Bloating", "Fatigue",
    "Breast Tenderness", "Back Pain", "Nausea", "Acne", "None",
]

# Each mood is shown with an emoji in the dropdown, but only the plain
# "value" (no emoji) is ever submitted and saved to the database.
MOOD_OPTIONS = [
    {"value": "Happy", "emoji": "\U0001F60A"},
    {"value": "Calm", "emoji": "\U0001F60C"},
    {"value": "Sad", "emoji": "\U0001F622"},
    {"value": "Irritable", "emoji": "\U0001F620"},
    {"value": "Anxious", "emoji": "\U0001F630"},
    {"value": "Tired", "emoji": "\U0001F634"},
]


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
    unread_notifications_count = 0
    user_id = session.get("user_id")
    if user_id is not None:
        user = db.session.get(User, user_id)
        if user:
            full_name = user.full_name
            first_name = user.full_name.split(" ")[0]
            unread_notifications_count = Notification.query.filter_by(
                user_id=user_id, is_read=False
            ).count()
        else:
            session.pop("user_id", None)

    lang = get_current_language()

    def t(key, **kwargs):
        return translate(key, lang, **kwargs)

    return {
        "current_first_name": first_name,
        "current_full_name": full_name,
        "unread_notifications_count": unread_notifications_count,
        "css_version": asset_version("css/style.css"),
        "js_version": asset_version("js/script.js"),
        "current_year": date.today().year,
        "t": t,
        "current_lang": lang,
        "current_lang_code": lang.upper(),
        "language_names": LANGUAGE_NAMES,
        "page_nav_order": PAGE_NAV_ORDER,
        "page_nav_names": {
            endpoint: translate(label_key, lang)
            for endpoint, label_key in PAGE_NAV_LABEL_KEYS.items()
        },
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
        site_search_pages=localize_site_search_pages(lang),
    )


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = db.session.get(User, session["user_id"])
    lang = get_current_language()
    today = date.today().isoformat()

    errors = {}
    success_message = None
    form_data = {
        "full_name": user.full_name,
        "date_of_birth": user.date_of_birth.isoformat(),
        "country": user.country,
    }

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        dob_raw = request.form.get("date_of_birth", "").strip()
        country = request.form.get("country", "").strip()

        form_data = {"full_name": full_name, "date_of_birth": dob_raw, "country": country}

        if not full_name:
            errors["full_name"] = translate("err_full_name_required", lang)

        dob_value = None
        if not dob_raw:
            errors["date_of_birth"] = translate("err_dob_required", lang)
        else:
            try:
                dob_value = datetime.strptime(dob_raw, "%Y-%m-%d").date()
                if dob_value > date.today():
                    errors["date_of_birth"] = translate("err_dob_future", lang)
            except ValueError:
                errors["date_of_birth"] = translate("err_dob_invalid", lang)

        if country not in AFRICAN_COUNTRIES:
            errors["country"] = translate("err_country_required", lang)

        if not errors:
            user.full_name = full_name
            user.date_of_birth = dob_value
            user.country = country
            db.session.commit()

            success_message = translate("profile_updated_success", lang)
            form_data = {
                "full_name": user.full_name,
                "date_of_birth": user.date_of_birth.isoformat(),
                "country": user.country,
            }

    return render_template(
        "profile.html",
        member_email=user.email,
        member_full_name=user.full_name,
        member_country=user.country,
        member_date_of_birth=user.date_of_birth.strftime("%d %B %Y"),
        countries=AFRICAN_COUNTRIES,
        today=today,
        errors=errors,
        form_data=form_data,
        success_message=success_message,
        # Stay in edit mode after a failed submission so the user sees her
        # attempted values and the error messages; otherwise (a fresh GET, or
        # a successful save) the page opens in view mode.
        show_edit_mode=bool(errors),
    )


@app.route("/tracker", methods=["GET", "POST"])
@login_required
def tracker():
    user_id = session["user_id"]
    errors = {}
    success_message = None

    if request.method == "POST":
        form_type = request.form.get("form_type", "")

        if form_type == "cycle":
            start_date_raw = request.form.get("start_date", "").strip()
            cycle_length_raw = request.form.get("cycle_length", "").strip()

            start_date_value = None
            if not start_date_raw:
                errors["start_date"] = "Please enter the first day of your last period."
            else:
                try:
                    start_date_value = datetime.strptime(start_date_raw, "%Y-%m-%d").date()
                    if start_date_value > date.today():
                        errors["start_date"] = "The start date cannot be in the future."
                except ValueError:
                    errors["start_date"] = "Enter a valid date."

            cycle_length_value = 28
            if not cycle_length_raw:
                errors.setdefault("cycle_length", "Please select your average cycle length.")
            else:
                try:
                    cycle_length_value = int(cycle_length_raw)
                    if cycle_length_value < CYCLE_LENGTH_MIN or cycle_length_value > CYCLE_LENGTH_MAX:
                        errors["cycle_length"] = (
                            f"Cycle length must be between {CYCLE_LENGTH_MIN} and {CYCLE_LENGTH_MAX} days."
                        )
                except ValueError:
                    errors["cycle_length"] = "Enter a valid number of days."

            if not errors:
                predicted_next_period = start_date_value + timedelta(days=cycle_length_value)
                new_cycle = MenstrualCycle(
                    user_id=user_id,
                    start_date=start_date_value,
                    cycle_length=cycle_length_value,
                    predicted_next_period=predicted_next_period,
                )
                db.session.add(new_cycle)
                db.session.commit()
                success_message = "Your period and cycle length have been saved."

        elif form_type == "symptom":
            record_date_raw = request.form.get("record_date", "").strip()
            symptom = request.form.get("symptom", "").strip()
            mood = request.form.get("mood", "").strip()

            latest_cycle = (
                MenstrualCycle.query.filter_by(user_id=user_id)
                .order_by(MenstrualCycle.start_date.desc())
                .first()
            )

            if not latest_cycle:
                errors["symptom_form"] = "Please log your period above first, then add symptoms."

            record_date_value = None
            if not record_date_raw:
                errors["record_date"] = "Please choose a date."
            else:
                try:
                    record_date_value = datetime.strptime(record_date_raw, "%Y-%m-%d").date()
                    if record_date_value > date.today():
                        errors["record_date"] = "The date cannot be in the future."
                except ValueError:
                    errors["record_date"] = "Enter a valid date."

            if not symptom:
                errors["symptom"] = "Please select a symptom."
            if not mood:
                errors["mood"] = "Please select a mood."

            if not errors:
                new_record = SymptomRecord(
                    user_id=user_id,
                    cycle_id=latest_cycle.id,
                    symptom=symptom,
                    mood=mood,
                    record_date=record_date_value,
                )
                db.session.add(new_record)
                db.session.commit()
                success_message = "Your symptom and mood record has been saved."

    cycles = (
        MenstrualCycle.query.filter_by(user_id=user_id)
        .order_by(MenstrualCycle.start_date.desc())
        .all()
    )
    symptom_records = (
        SymptomRecord.query.filter_by(user_id=user_id)
        .order_by(SymptomRecord.record_date.desc())
        .all()
    )
    latest_cycle = cycles[0] if cycles else None

    return render_template(
        "tracker.html",
        errors=errors,
        success_message=success_message,
        cycles=cycles,
        symptom_records=symptom_records,
        latest_cycle=latest_cycle,
        symptom_options=SYMPTOM_OPTIONS,
        mood_options=MOOD_OPTIONS,
        today=date.today().isoformat(),
    )


def _save_evidence_file(uploaded_file):
    """Validate and store one uploaded evidence file.

    Returns (original_filename, stored_filename) on success, or (None, error)
    where error is a user-facing message if the file was rejected. The file
    is written to EVIDENCE_UPLOAD_DIR, which is outside static/, so nothing
    here is ever reachable at a public URL.
    """
    original_name = secure_filename(uploaded_file.filename or "")
    if not original_name:
        return None, "Please choose a valid file."

    extension = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if extension not in ALLOWED_EVIDENCE_EXTENSIONS:
        return None, "Evidence must be a PNG, JPG, JPEG or PDF file."

    os.makedirs(EVIDENCE_UPLOAD_DIR, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}.{extension}"
    uploaded_file.save(os.path.join(EVIDENCE_UPLOAD_DIR, stored_name))
    return (original_name, stored_name), None


@app.route("/report-abuse", methods=["GET", "POST"])
@login_required
def report_abuse():
    user_id = session["user_id"]
    errors = {}
    submitted_report = None

    if request.method == "POST":
        report_type = request.form.get("report_type", "").strip()
        description = request.form.get("description", "").strip()
        incident_date_raw = request.form.get("incident_date", "").strip()
        location = request.form.get("location", "").strip()
        immediate_danger = request.form.get("immediate_danger") == "yes"
        uploaded_file = request.files.get("evidence")

        if report_type not in ABUSE_REPORT_TYPES:
            errors["report_type"] = "Please select the type of abuse."

        if not description or len(description) < 10:
            errors["description"] = "Please enter a description of at least 10 characters."

        incident_date_value = None
        if not incident_date_raw:
            errors["incident_date"] = "Please select the date of the incident."
        else:
            try:
                incident_date_value = datetime.strptime(incident_date_raw, "%Y-%m-%d").date()
                if incident_date_value > date.today():
                    errors["incident_date"] = "The incident date cannot be in the future."
            except ValueError:
                errors["incident_date"] = "Enter a valid date."

        evidence_to_save = None
        if uploaded_file and uploaded_file.filename:
            saved, upload_error = _save_evidence_file(uploaded_file)
            if upload_error:
                errors["evidence"] = upload_error
            else:
                evidence_to_save = saved

        if not errors:
            new_report = AbuseReport(
                user_id=user_id,
                report_type=report_type,
                description=description,
                incident_date=incident_date_value,
                location=location or None,
                immediate_danger=immediate_danger,
            )
            db.session.add(new_report)
            db.session.commit()

            if evidence_to_save:
                original_name, stored_name = evidence_to_save
                db.session.add(Evidence(
                    report_id=new_report.id,
                    original_filename=original_name,
                    stored_filename=stored_name,
                ))
                db.session.commit()

            # Private wording only: a notification must never repeat the
            # report's type, description or any other submitted detail.
            create_notification(
                user_id,
                translate("notif_abuse_report_received", get_current_language()),
                link=url_for("report_abuse"),
            )
            db.session.commit()

            submitted_report = new_report

    reports = (
        AbuseReport.query.filter_by(user_id=user_id)
        .order_by(AbuseReport.created_at.desc())
        .all()
    )

    return render_template(
        "report_abuse.html",
        errors=errors,
        submitted_report=submitted_report,
        reports=reports,
        report_types=ABUSE_REPORT_TYPES,
        today=date.today().isoformat(),
    )


@app.route("/report-abuse/evidence/<int:evidence_id>")
@login_required
def download_evidence(evidence_id):
    evidence = db.session.get(Evidence, evidence_id)
    if not evidence or evidence.report.user_id != session["user_id"]:
        # 404, not 403 — never confirm to a visitor that a given evidence
        # id belongs to someone else's confidential report.
        abort(404)

    return send_from_directory(
        EVIDENCE_UPLOAD_DIR,
        evidence.stored_filename,
        as_attachment=True,
        download_name=evidence.original_filename,
    )


@app.route("/health-resources")
@login_required
def health_resources():
    lang = get_current_language()
    articles = localize_health_articles(lang)

    seen = set()
    categories = []
    for article in articles:
        if article["category_key"] not in seen:
            seen.add(article["category_key"])
            categories.append({"key": article["category_key"], "label": article["category_label"]})

    return render_template("health_resources.html", articles=articles, categories=categories)


@app.route("/health-resources/<slug>")
@login_required
def health_article(slug):
    article = get_health_article(slug)
    if not article:
        abort(404)

    lang = get_current_language()
    localized = dict(article)
    localized["title"] = translate(localized.pop("title_key"), lang)
    localized["summary"] = translate(localized.pop("summary_key"), lang)
    localized["category_label"] = translate(localized.pop("category_label_key"), lang)

    return render_template("health_article.html", article=localized)


@app.route("/education")
@login_required
def education():
    user_id = session["user_id"]
    lang = get_current_language()

    completed_slugs = {
        p.course_slug for p in
        CourseProgress.query.filter_by(user_id=user_id, completed=True).all()
    }

    courses = localize_courses(lang, completed_slugs)
    scholarships = localize_scholarships(lang)

    return render_template(
        "education.html",
        courses=courses,
        scholarships=scholarships,
        completed_count=len(completed_slugs),
        total_courses=len(TECH_COURSES),
    )


@app.route("/education/course/<slug>")
@login_required
def course_overview(slug):
    if not get_course(slug):
        abort(404)
    return redirect(url_for("course_lesson", slug=slug, lesson_num=1))


@app.route("/education/course/<slug>/lesson/<int:lesson_num>")
@login_required
def course_lesson(slug, lesson_num):
    course = get_course(slug)
    if not course:
        abort(404)

    lessons = course["lessons"]
    total = len(lessons)
    if lesson_num < 1 or lesson_num > total:
        abort(404)

    lang = get_current_language()
    localized_course = localize_single_course(course, lang)

    lesson_data = lessons[lesson_num - 1]
    lesson = {
        "number": lesson_num,
        "total": total,
        "title": translate(lesson_data["title_key"], lang),
        "explanation": lesson_data["explanation"],
        "example": lesson_data["example"],
        "activity": lesson_data["activity"],
    }

    is_completed = CourseProgress.query.filter_by(
        user_id=session["user_id"], course_slug=slug, completed=True
    ).first() is not None

    return render_template(
        "course_lesson.html",
        course=localized_course,
        lesson=lesson,
        is_completed=is_completed,
        is_final=lesson_num == total,
        prev_num=lesson_num - 1 if lesson_num > 1 else None,
        next_num=lesson_num + 1 if lesson_num < total else None,
    )


@app.route("/education/course/<slug>/complete", methods=["POST"])
@login_required
def complete_course(slug):
    course = get_course(slug)
    if not course:
        abort(404)

    user_id = session["user_id"]
    lang = get_current_language()

    progress = CourseProgress.query.filter_by(user_id=user_id, course_slug=slug).first()
    already_completed = progress.completed if progress else False

    if progress:
        progress.completed = True
        progress.completed_at = datetime.utcnow()
    else:
        db.session.add(CourseProgress(
            user_id=user_id,
            course_slug=slug,
            completed=True,
            completed_at=datetime.utcnow(),
        ))

    final_lesson = len(course["lessons"])

    if not already_completed:
        course_title = translate(course["title_key"], lang)
        create_notification(
            user_id,
            translate("notif_course_completed", lang, course=course_title),
            link=url_for("course_lesson", slug=slug, lesson_num=final_lesson),
        )

    db.session.commit()

    return redirect(url_for("course_lesson", slug=slug, lesson_num=final_lesson))


@app.route("/education/scholarship/<slug>")
@login_required
def scholarship_detail(slug):
    scholarship = get_scholarship(slug)
    if not scholarship:
        abort(404)

    lang = get_current_language()
    localized = localize_single_scholarship(scholarship, lang)

    return render_template("scholarship_detail.html", scholarship=localized)


@app.route("/community", methods=["GET", "POST"])
@login_required
def community():
    user_id = session["user_id"]
    lang = get_current_language()

    errors = {}
    form_data = {"content": "", "category": "", "is_anonymous": False}

    if request.method == "POST":
        content = request.form.get("content", "").strip()
        category = request.form.get("category", "").strip()
        is_anonymous = request.form.get("is_anonymous") == "yes"

        form_data = {"content": content, "category": category, "is_anonymous": is_anonymous}

        if not content:
            errors["content"] = translate("err_post_content_required", lang)
        elif len(content) > 1000:
            errors["content"] = translate("err_post_content_too_long", lang)

        if category not in COMMUNITY_CATEGORY_KEYS:
            errors["category"] = translate("err_post_category_required", lang)

        if not errors:
            db.session.add(CommunityPost(
                user_id=user_id,
                content=content,
                category=category,
                is_anonymous=is_anonymous,
            ))
            db.session.commit()
            return redirect(url_for("community"))

    posts = CommunityPost.query.order_by(CommunityPost.created_at.desc()).all()

    author_ids = {p.user_id for p in posts}
    authors = {u.id: u.full_name for u in User.query.filter(User.id.in_(author_ids)).all()}

    my_support_post_ids = {
        r.post_id for r in SupportReaction.query.filter_by(user_id=user_id).all()
    }

    category_labels = {c["key"]: c["label"] for c in localize_community_categories(lang)}

    display_posts = []
    for p in posts:
        display_posts.append({
            "id": p.id,
            "content": p.content,
            "category_label": category_labels.get(p.category, p.category),
            "created_at": p.created_at,
            "is_anonymous": p.is_anonymous,
            "author_name": (
                translate("anonymous_member_label", lang) if p.is_anonymous
                else authors.get(p.user_id, translate("anonymous_member_label", lang))
            ),
            "is_owner": p.user_id == user_id,
            "support_count": len(p.support_reactions),
            "has_supported": p.id in my_support_post_ids,
        })

    return render_template(
        "community.html",
        posts=display_posts,
        categories=localize_community_categories(lang),
        errors=errors,
        form_data=form_data,
    )


@app.route("/community/post/<int:post_id>/support", methods=["POST"])
@login_required
def toggle_support(post_id):
    post = db.session.get(CommunityPost, post_id)
    if not post:
        abort(404)

    user_id = session["user_id"]
    existing = SupportReaction.query.filter_by(user_id=user_id, post_id=post_id).first()
    if existing:
        db.session.delete(existing)
    else:
        db.session.add(SupportReaction(user_id=user_id, post_id=post_id))
        if post.user_id != user_id:
            lang = get_current_language()
            create_notification(
                post.user_id,
                translate("notif_support_received", lang),
                link=url_for("community", _anchor=f"post-{post_id}"),
            )
    db.session.commit()

    return redirect(url_for("community", _anchor=f"post-{post_id}"))


@app.route("/community/post/<int:post_id>/delete", methods=["POST"])
@login_required
def delete_post(post_id):
    post = db.session.get(CommunityPost, post_id)
    if not post:
        abort(404)

    # A community post is already publicly visible on the feed, so its
    # existence is not a secret the way a confidential abuse report or a
    # private CourseProgress row is; a plain 403 is enough to block a
    # non-owner from deleting it.
    if post.user_id != session["user_id"]:
        abort(403)

    db.session.delete(post)
    db.session.commit()

    return redirect(url_for("community"))


@app.route("/notifications")
@login_required
def notifications():
    user_id = session["user_id"]
    items = (
        Notification.query.filter_by(user_id=user_id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    return render_template("notifications.html", notifications=items)


@app.route("/notifications/<int:notification_id>/open")
@login_required
def open_notification(notification_id):
    notification = db.session.get(Notification, notification_id)
    if not notification or notification.user_id != session["user_id"]:
        # 404, not 403 — a notification is private to its recipient, the
        # same treatment as a confidential abuse report or CourseProgress row.
        abort(404)

    if not notification.is_read:
        notification.is_read = True
        db.session.commit()

    return redirect(notification.link or url_for("notifications"))


@app.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id):
    notification = db.session.get(Notification, notification_id)
    if not notification or notification.user_id != session["user_id"]:
        abort(404)

    notification.is_read = True
    db.session.commit()

    return redirect(url_for("notifications"))


@app.route("/notifications/read-all", methods=["POST"])
@login_required
def mark_all_notifications_read():
    user_id = session["user_id"]
    Notification.query.filter_by(user_id=user_id, is_read=False).update({"is_read": True})
    db.session.commit()

    return redirect(url_for("notifications"))


@app.route("/notifications/<int:notification_id>/delete", methods=["POST"])
@login_required
def delete_notification(notification_id):
    notification = db.session.get(Notification, notification_id)
    if not notification or notification.user_id != session["user_id"]:
        abort(404)

    db.session.delete(notification)
    db.session.commit()

    return redirect(url_for("notifications"))


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
