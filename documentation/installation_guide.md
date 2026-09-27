# Installation Guide

This guide explains how to install, configure, and run the Personal Finance
Advisor Bot on your own computer.

## 1. Prerequisites

- **Python 3.10 or newer** (the project was built and tested with Python
  3.12/3.13). Check your version with:
  ```bash
  python --version
  ```
- `pip` (comes with Python).
- (Optional) A free **Google Gemini API key**, if you want the AI Advisor to
  use live AI instead of its built-in fallback. Get one at
  <https://aistudio.google.com/app/apikey>.
- (Optional, Windows only) `ngrok`, only if you want to use the included
  `run_public.ps1` script to share your local app over the internet
  temporarily.

No external database server is required — the app uses a single SQLite file
that is created automatically.

## 2. Get the project onto your machine

Copy or clone the `Personal_Finance_Advisor_Bot` folder to your computer, and
open a terminal inside it (the folder that directly contains `app.py`).

## 3. Create a virtual environment (recommended)

A virtual environment keeps this project's Python packages separate from
everything else on your computer.

```bash
python -m venv .venv
```

Activate it:

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (Command Prompt)
.venv\Scripts\activate.bat

# macOS / Linux
source .venv/bin/activate
```

## 4. Install the dependencies

```bash
pip install -r requirements.txt
```

This installs, exactly as listed in `requirements.txt`:

- `Flask` and `Werkzeug` — the web framework and its security/password
  utilities.
- `Flask-SQLAlchemy` and `SQLAlchemy` — the database layer.
- `Flask-Login` — session-based authentication.
- `python-dotenv` — loads the `.env` configuration file.
- `google-genai` — the Google Gemini SDK used by the AI Advisor.
- `pytest` — the automated test framework (only needed if you plan to run
  the test suite).

> `requirements.txt` lists **minimum** versions, not exact pinned versions.
> If you want to freeze the exact versions that end up installed on your
> machine, run `pip freeze > requirements-lock.txt` afterwards.

## 5. Configure the environment file

The project reads its settings from a `.env` file, which is **not** included
in version control (see `.gitignore`) because it can contain secrets. A
template is provided as `.env.example`:

```env
# Flask secret key - used to sign session cookies (secure sessions)
SECRET_KEY=change_this_to_a_random_string

# Database connection (SQLite)
DATABASE_URI=sqlite:///finance.db

# Google Gemini AI
# Get your free key from: https://aistudio.google.com/app/apikey
GEMINI_API_KEY=your_gemini_api_key_here

# Gemini model to use for financial advice
GEMINI_MODEL=gemini-flash-latest
```

Copy it to a real `.env` file:

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Then open `.env` in a text editor and:

- **`SECRET_KEY`** — replace the placeholder with any long, random string.
  This key signs your login session cookies; if it stays as the placeholder
  value the app still runs (it falls back to a development-only default in
  `config.py`), but you should always set a real value before letting anyone
  else use the app.
- **`DATABASE_URI`** — you can normally leave this as
  `sqlite:///finance.db`. Flask-SQLAlchemy will place the actual file at
  `instance/finance.db` inside the project folder.
- **`GEMINI_API_KEY`** — optional. Leave it as the placeholder (or empty) if
  you do not want to use live AI; the AI Advisor page will still work using
  its built-in rule-based advice instead, and will say so on screen. Paste in
  a real key from Google AI Studio to enable live Gemini responses.
- **`GEMINI_MODEL`** — the Gemini model name to call. The default,
  `gemini-flash-latest`, works out of the box; only change it if you know you
  want a different Gemini model.

**Never commit your real `.env` file or share it** — it is already listed in
`.gitignore` for this reason.

## 6. Run the application

```bash
python app.py
```

The first time you run this, Flask-SQLAlchemy will automatically create the
SQLite database file at `instance/finance.db` with all the required tables
— you do not need to run any separate migration command.

By default the app starts at:

```
http://127.0.0.1:5000
```

Open that address in your browser, then register a new account from the
**Register** link on the login page.

### Optional environment variables (read directly by `app.py`)

| Variable       | Default       | Purpose |
|-----------------|---------------|----------|
| `HOST`          | `127.0.0.1`   | Network interface to bind to |
| `PORT`          | `5000`        | Port to listen on |
| `FLASK_DEBUG`   | `0`           | Set to `1` to enable Flask's interactive debugger **on localhost only** |

Example (macOS/Linux):
```bash
FLASK_DEBUG=1 python app.py
```
Example (Windows PowerShell):
```powershell
$env:FLASK_DEBUG="1"; python app.py
```

The app will **refuse to start** if `FLASK_DEBUG=1` is combined with a
`HOST` other than `127.0.0.1`, `localhost`, or `::1`. This is a deliberate
safety check in `app.py`: the interactive debugger it enables would let
anyone who can reach the server run arbitrary code, which is only acceptable
on your own machine.

## 7. (Optional) Sharing a local demo publicly

The project includes `run_public.ps1`, a Windows PowerShell script that
starts the Flask app and an `ngrok` tunnel together, so you can share a
temporary public URL (for example, to demo the project to someone else).
This is entirely optional and only needed if you want to show the app to
someone who is not on your local network.

```powershell
powershell -ExecutionPolicy Bypass -File .\run_public.ps1
```

It requires `ngrok` to be installed and configured with a free authtoken
first (`ngrok config add-authtoken YOUR_TOKEN`) — the script itself checks
for this and prints instructions if it is missing. Press `Ctrl+C` in that
terminal to stop both the app and the tunnel.

## 8. Installation troubleshooting

| Problem | Likely cause | Fix |
|----------|---------------|------|
| `ModuleNotFoundError: No module named 'flask'` (or similar) | Virtual environment not activated, or dependencies not installed | Activate the virtual environment, then re-run `pip install -r requirements.txt` |
| `pip install` fails to find `google-genai>=2.0` | Very old `pip`, or no internet connection | Upgrade pip (`pip install --upgrade pip`) and check your internet connection |
| App starts but the browser shows "connection refused" | Wrong host/port, or a firewall blocking it | Confirm the terminal output shows the address, and that you are opening the same `HOST:PORT` |
| `OSError: [Errno 98] Address already in use` (or similar on Windows) | Another process is already using port 5000 | Stop the other process, or run with a different port: `PORT=5001 python app.py` |
| AI Advisor always shows the "built-in analysis" fallback | No `GEMINI_API_KEY` set, or it's still the placeholder value | Add a real key to `.env` and restart the app (see Step 5) |
| Changes to `.env` don't seem to apply | The app was not restarted after editing `.env` | Stop the app (Ctrl+C) and run `python app.py` again — `.env` is only read at startup |
| Database seems "stuck" or locked while the app is running from a cloud-synced folder (OneDrive, Dropbox, etc.) | File-locking conflicts between the sync client and SQLite | This is a known limitation noted directly in `app.py`; the reloader is disabled for this reason. Avoid running from a folder that is actively syncing, or close the sync client while testing |

For errors that occur while **running the automated test suite** rather than
the app itself, see [`testing.md`](testing.md).
