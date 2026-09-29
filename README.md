# SheConnect

## Overview

SheConnect is a digital support platform designed for African women and
girls. It brings together trusted health information, safety support,
education and access to a supportive community, all in one place, so that
help and information are easier to find when they are needed.

This is a student project built with Python and Flask.

## Purpose

SheConnect exists to make it easier for African women and girls to:

- find reliable health and safety information,
- feel supported and connected to a community,
- access emergency help resources, and
- learn about topics that affect their wellbeing, education and future.

## Current Features

The following features are built and working in this version of the project:

- User registration with full name, email, date of birth and country
- Secure password creation, a live password-strength indicator, and
  password hashing (passwords are never stored as plain text)
- User login, logout and session management
- A personalised welcome message and member status once signed in
- A user dashboard and profile summary page
- Health and educational feature pages
- An Emergency Help page
- A Subscription page with Free, Pro and Premium plans (Pro and Premium
  are shown for preview only — no real payment is processed yet)
- Responsive design that works on both desktop and mobile
- Font Awesome icons used throughout the interface
- Language selection between English, French, Mauritian Kreol and
  Nigerian Pidgin
- An SQLite database managed through Flask-SQLAlchemy

## Technologies Used

- Python
- Flask
- Flask-SQLAlchemy
- SQLite
- HTML
- CSS
- JavaScript
- Font Awesome

## Project Folder Structure

```
SheConnect/
├── app.py                     # Main Flask application and routes
├── translations.py            # Text used for the language selector
├── requirements.txt           # Python dependencies
├── static/
│   ├── css/
│   │   └── style.css          # Site styling
│   ├── js/
│   │   └── script.js          # Site interactivity
│   ├── images/
│   │   └── african-women-community.png
│   └── vendor/
│       └── fontawesome/       # Self-hosted Font Awesome icon files
├── templates/
│   ├── base.html              # Shared layout (navigation and footer)
│   ├── index.html             # Homepage
│   ├── register.html          # Registration page
│   ├── login.html             # Login page
│   ├── dashboard.html         # User dashboard
│   ├── profile.html           # User profile
│   ├── about.html             # About page
│   ├── features.html          # Features page
│   ├── emergency.html         # Emergency Help page
│   ├── subscription.html      # Subscription page
│   └── 404.html               # Page-not-found error page
└── instance/
    └── sheconnect.db          # SQLite database (created automatically)
```

## Installation Instructions

1. Make sure Python 3 is installed on your computer.
2. Open a terminal and navigate to the project folder:
   ```
   cd path\to\SheConnect
   ```
3. Create a virtual environment (only needed the first time):
   ```
   python -m venv .venv
   ```

## Activating the Virtual Environment on Windows

In Command Prompt or PowerShell, run:

```
.venv\Scripts\activate
```

You will know it worked because your terminal line will start with
`(.venv)`. To turn it off later, type `deactivate`.

## Installing Requirements

With the virtual environment active, install all required packages by
running:

```
pip install -r requirements.txt
```

## Running the Website

Once the requirements are installed, start the website with:

```
python app.py
```

Then open your browser and go to:

```
http://127.0.0.1:5000
```

The SQLite database file is created automatically the first time the app
runs, so no extra setup is needed.

## Supported Languages

SheConnect currently supports four languages, selectable from the
language menu in the navigation bar:

- English
- French
- Mauritian Kreol
- Nigerian Pidgin

The chosen language is remembered while you browse the site. Personal
information such as names, emails and countries is never translated.

## Future Improvements

These features are planned but are **not** built yet:

- Menstrual health tracking
- Community forum and live chat
- Confidential gender-based violence reporting
- Counsellor matching
- Email and SMS notifications
- Real subscription payments

## Author

Obueze Chisom Louisa
