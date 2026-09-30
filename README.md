# SheConnect

A Flask and SQLite web platform that brings together health information,
safety support, education and community into one connected space for
African women and girls.

## Overview and Purpose

SheConnect exists to make it easier for African women and girls to find
information and support that can genuinely change their day-to-day
safety, health and confidence. Access to reliable health information,
a safe way to report abuse, education, and a supportive community
should not depend on where a woman lives or what she has already been
through.

The platform brings five things into one place that are too often
scattered or hard to reach: trusted health information, a confidential
way to report abuse, practical technology education and scholarship
opportunities, a moderated community space, and clear emergency
guidance. Everything is designed around one simple idea: every woman
and girl deserves to feel informed, supported and connected, wherever
she is.

This is a student project built with Python and Flask as part of a
software engineering portfolio.

## Main Features

**Accounts and profile**
- Registration with full name, email, date of birth and country, a
  live password-strength indicator, and secure password hashing
  (passwords are never stored as plain text)
- Login, logout and session-based authentication
- A profile page with a view mode and an edit mode, letting a member
  update her name, date of birth and country (email stays read-only,
  since it is used for login)

**Health and wellbeing**
- Health Resources: six articles on menstrual health, hygiene, mental
  health and related topics, with search and category filtering
- Cycle Tracker: log a period and its length, get a predicted next
  period date, and record symptoms and mood over time

**Safety**
- Confidential Abuse Reporting: a private report form with a reference
  number, optional evidence upload (image or PDF), and an emergency
  flag; only the reporting user can ever see her own reports or files
- Emergency Help page with practical safety guidance and a Quick Exit
  button that immediately leaves the site

**Education**
- Technology Learning: six beginner courses (Computer Basics, Internet
  Safety, Introduction to Coding, Python Basics, Web Development, Git
  and GitHub), each split into three lessons with an explanation, a
  worked example and a short activity
- Per-user course progress tracking, with a visible completed count
- Scholarship Opportunities: example scholarship listings, clearly
  labelled as demonstrations with a reminder to verify details on the
  official website before applying

**Community**
- Members can post to a shared feed, optionally anonymously (the post
  still stores who wrote it, but her name is never shown publicly)
- A "Send Support" reaction that a member can add or remove, with a
  visible support count
- A member can delete only her own posts

**Notifications**
- An in-app notification centre with a bell icon and unread count in
  the navigation bar
- Automatic notifications when a course is completed, when another
  member supports your post, and when a confidential report is
  received (using private wording only, never the report's contents)
- Mark one or all notifications as read, or delete a notification

**Navigation and usability**
- A site-wide search box on the dashboard that finds and opens any
  existing page as you type
- Fixed left/right arrows that step through the main site pages in a
  set order, with hover tooltips and keyboard-accessible labels
- Responsive layout that works on desktop, tablet and mobile
- Self-hosted Font Awesome icons throughout the interface
- Full interface translation into English, French, Mauritian Kreol and
  Nigerian Pidgin, switchable at any time from the navigation bar

## Technologies Used

- Python 3
- Flask
- Flask-SQLAlchemy
- SQLite
- Jinja2 templates
- HTML5 and CSS3
- Vanilla JavaScript (no frontend framework)
- Font Awesome (self-hosted, solid icon set)
- Werkzeug (password hashing and security helpers)

## Installation Instructions

1. Make sure Python 3.10 or later is installed on your computer.
2. Clone or download the repository, then open a terminal in the
   project folder:
   ```
   cd path\to\SheConnect
   ```

## Virtual Environment Setup

Create a virtual environment (only needed the first time):

```
python -m venv .venv
```

Activate it.

On Windows (Command Prompt or PowerShell):
```
.venv\Scripts\activate
```

On macOS or Linux:
```
source .venv/bin/activate
```

You will know it worked because your terminal line will start with
`(.venv)`. To turn it off later, type `deactivate`.

## Installing Requirements

With the virtual environment active, install all required packages:

```
pip install -r requirements.txt
```

## Running the Flask Application

Once the requirements are installed, start the website with:

```
python app.py
```

Then open your browser and go to:

```
http://127.0.0.1:5000
```

The app runs in debug mode by default, which is suitable for local
development and testing but should be turned off, along with setting
a real `SECRET_KEY`, before any production deployment.

## Database Information

SheConnect uses SQLite through Flask-SQLAlchemy. The database file is
created automatically the first time the app runs, so no manual setup
is needed.

- Location: `instance/sheconnect.db`
- All tables (users, menstrual cycles and symptom records, abuse
  reports and evidence, course progress, community posts and support
  reactions, notifications) are created automatically by
  `db.create_all()` on startup if they do not already exist
- Passwords are stored only as salted hashes, never as plain text
- Confidential abuse report evidence files are stored outside the
  `static/` folder, in `instance/evidence_uploads/`, so they are never
  served at a public URL; they can only be downloaded by the user who
  submitted the report
- The database file and the evidence uploads folder are excluded from
  version control (see `.gitignore`)

## Project Structure

```
SheConnect/
├── app.py                       # Flask application: routes, models, view logic
├── translations.py              # All interface text for the four supported languages
├── requirements.txt             # Python dependencies
├── .gitignore                   # Excludes .venv, __pycache__, the database and evidence uploads
├── static/
│   ├── css/
│   │   └── style.css            # All site styling
│   ├── js/
│   │   └── script.js            # Site interactivity (search, tabs, toggles, forms)
│   ├── images/
│   │   └── african-women-community.png
│   └── vendor/
│       └── fontawesome/         # Self-hosted Font Awesome icon files
├── templates/
│   ├── base.html                # Shared layout: navigation, footer, nav arrows
│   ├── index.html               # Homepage
│   ├── register.html            # Registration page
│   ├── login.html               # Login page
│   ├── dashboard.html           # Dashboard with quick actions and site search
│   ├── profile.html             # Profile view/edit page
│   ├── about.html                # About page
│   ├── features.html            # Features overview page
│   ├── emergency.html           # Emergency Help page
│   ├── subscription.html        # Subscription plans page
│   ├── tracker.html             # Cycle Tracker
│   ├── report_abuse.html        # Confidential Abuse Reporting
│   ├── health_resources.html    # Health Resources listing
│   ├── health_article.html      # Single health article
│   ├── education.html           # Technology Learning and Scholarships
│   ├── course_lesson.html       # A single lesson within a course
│   ├── scholarship_detail.html  # A single scholarship listing
│   ├── community.html           # Community Support feed
│   ├── notifications.html       # Notification centre
│   └── 404.html                 # Page-not-found error page
└── instance/                    # Created automatically; not in version control
    ├── sheconnect.db            # SQLite database
    └── evidence_uploads/        # Private confidential-report evidence files
```

## Safety and Privacy Note

SheConnect is a student project and a working prototype, not a
production safety service.

- Confidential abuse reports, cycle and symptom records, and course
  progress are private and visible only to the account that created
  them.
- SheConnect does **not** automatically contact emergency services,
  the police, or any authority on a user's behalf. If a user indicates
  she is in immediate danger, she is directed to contact her local
  emergency service herself.
- The Emergency Help page includes a Quick Exit button that
  immediately leaves the site and replaces it in browser history, for
  anyone who needs to close the page quickly.
- Community posts are visible to other logged-in members by design; a
  member can choose to post anonymously, in which case her name is
  never displayed, though the platform still privately associates the
  post with her account so she can manage it.
- Before any real-world deployment, the development `SECRET_KEY`,
  debug mode, and password-reset process would need to be replaced
  with production-grade equivalents.

## Supported Languages

SheConnect currently supports four languages, selectable from the
language menu in the navigation bar:

- English
- French
- Mauritian Kreol
- Nigerian Pidgin

The chosen language is remembered while browsing the site and applies
to the entire interface. Personal information such as names, emails
and countries is never translated.

## Future Improvements

These are natural next steps beyond the current version:

- Real payment processing for the Pro and Premium subscription plans
- Counsellor or mentor matching
- Email or SMS notifications, in addition to the in-app notification
  centre
- Reporting/moderation tools for community posts
- Automated end-to-end browser testing
- Production deployment configuration (a real `SECRET_KEY`, a
  production-grade database, and debug mode turned off)

## Author

Obueze Chisom Louisa

## GitHub Repository

https://github.com/Chijoan/SheConnect

## Deployed Website

_Not yet deployed. Link will be added here once the site is live._
