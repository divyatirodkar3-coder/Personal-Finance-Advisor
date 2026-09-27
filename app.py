"""
app.py - Main entry point of the Personal Finance Advisor Bot.

WHAT IS A FLASK APPLICATION?
----------------------------
Flask is a web framework. It listens for browser requests like
"GET /dashboard" and runs a Python function called a "route" that
decides what HTML to send back.

The function below (create_app) builds and returns the app object.
We use this "app factory" style so tests can create a separate app later.
"""

import os

from flask import Flask, render_template, redirect, url_for
from flask_login import current_user

from config import DevelopmentConfig
from extensions import db, login_manager

# Importing the models package registers every table with SQLAlchemy.
# This MUST happen before db.create_all() is called. The import itself
# is the point (the names are used through the relationships), hence noqa.
import models  # noqa: F401

# Importing routes registers every blueprint (auth, dashboard, ...).
from routes import ALL_BLUEPRINTS


def create_app(config_class=DevelopmentConfig):
    """Create and configure the Flask application."""

    app = Flask(__name__)
    app.config.from_object(config_class)

    # Attach the shared database and login tools to this app
    db.init_app(app)

    # Turn on login handling. This needs a @login_manager.user_loader
    # function, which now exists in routes/auth.py (STAGE 5).
    login_manager.init_app(app)

    # Register every blueprint (auth, dashboard, ...).
    for blueprint in ALL_BLUEPRINTS:
        app.register_blueprint(blueprint)

    # ---------------------------------------------------------------
    # ROUTES
    # @app.route("/") means: when the browser opens the homepage,
    # run the function underneath it.
    # ---------------------------------------------------------------
    @app.route("/")
    def index():
        """Send visitors to the dashboard if logged in, else to login."""
        if current_user.is_authenticated:
            return redirect(url_for("dashboard.index"))
        return redirect(url_for("auth.login"))

    @app.route("/health")
    def health():
        """Tiny page used to check the server is alive."""
        return "OK - Personal Finance Advisor Bot is running"

    # ---------------------------------------------------------------
    # ERROR HANDLING  (Spec: "Handle ... error handling")
    #
    # Without these, the user sees a raw Python traceback. With them,
    # they see a friendly page and the detail is written to the log
    # instead. The message never leaks to the browser.
    # ---------------------------------------------------------------
    @app.errorhandler(400)
    def bad_request(error):
        return render_template("errors/400.html"), 400

    @app.errorhandler(401)
    def unauthorised(error):
        return render_template("errors/403.html"), 401

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return render_template("errors/400.html"), 405

    @app.errorhandler(413)
    def too_large(error):
        # Triggered by the 2 MB upload limit in config.py
        return render_template("errors/400.html"), 413

    @app.errorhandler(500)
    def server_error(error):
        # Undo any half-finished database work, then log the detail
        # privately. The visitor only sees the friendly page.
        try:
            db.session.rollback()
        except Exception:
            pass
        app.logger.exception("Server error while handling a request")
        return render_template("errors/500.html"), 500

    @app.errorhandler(Exception)
    def unexpected_error(error):
        """Last safety net for anything not covered above.

        HTTP errors (404, 400 ...) already have their own handlers, so
        this only sees genuinely unexpected problems. It is what stops
        a random bug from showing a traceback to the user.
        """
        from werkzeug.exceptions import HTTPException
        if isinstance(error, HTTPException):
            return error.get_response()

        try:
            db.session.rollback()
        except Exception:
            pass
        app.logger.exception("Unexpected error")
        return render_template("errors/500.html"), 500

    @app.after_request
    def security_headers(response):
        """Small headers that make the app a little safer.

        X-Content-Type-Options stops browsers guessing that a text file
        is really JavaScript. X-Frame-Options stops other sites from
        embedding our pages in an iframe (clickjacking).
        """
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

    # ---------------------------------------------------------------
    # CREATE DATABASE TABLES
    # This makes sure the .db file exists with all our tables.
    # (Tables themselves are added in STAGE 4.)
    # ---------------------------------------------------------------
    with app.app_context():
        db.create_all()

        # A quick startup check: every model class must be registered,
        # otherwise db.create_all() would silently create NO tables.
        # This line also stops linters complaining about the import above.
        app.logger.info("Database tables ready: %s",
                        ", ".join(models.__all__))

    return app


# Create the app so that "flask run" and the test suite can import it
app = create_app()


if __name__ == "__main__":
    # ---------------------------------------------------------------
    # LOCAL DEVELOPMENT SERVER
    # ---------------------------------------------------------------
    # WHY DEBUG IS OPT-IN, NOT HARDCODED
    # debug=True turns on Werkzeug's interactive debugger. If any
    # unhandled error happens, that page shows a Python console which
    # lets ANYONE WHO CAN REACH THIS SERVER RUN ARBITRARY CODE on
    # this machine. That is convenient on 127.0.0.1 and catastrophic
    # on a public ngrok URL, so debug is now OFF unless you ask for
    # it with FLASK_DEBUG=1.
    #
    # To run with the debugger while developing:
    #     $env:FLASK_DEBUG="1"; python app.py
    debug = os.getenv("FLASK_DEBUG", "0").strip() == "1"
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 5000))

    # Belt and braces: never let the debugger face the internet.
    if debug and host not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit(
            "Refusing to start: debug=True on host {0!r} would expose the "
            "Werkzeug code console to the public internet. Use "
            "127.0.0.1 for debug, or start without FLASK_DEBUG.".format(host)
        )

    # use_reloader=False stops the auto-restart, which avoids file-lock
    # issues with SQLite inside a OneDrive folder.
    app.run(host=host, port=port, debug=debug, use_reloader=False)
