"""AILP factory, persistent evidence API and explicit review consent."""

import hmac
import os
import sqlite3
from pathlib import Path

from flask import Blueprint, Flask, abort, current_app, g, jsonify, render_template, request

DECISIONS = {"Accepted", "Modified", "Rejected"}


def create_app(config=None):
    """Create an isolated application for a release or a test."""
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get("AILP_DATABASE", "runtime/ailp.db"),
        STUDENT_TOKEN=os.environ.get("AILP_STUDENT_TOKEN", ""),
        EDUCATOR_TOKEN=os.environ.get("AILP_EDUCATOR_TOKEN", ""),
        VERSION=os.environ.get("AILP_VERSION", "development"),
        MAX_CONTENT_LENGTH=32 * 1024,
    )
    if config:
        app.config.update(config)
    tokens = [app.config["STUDENT_TOKEN"], app.config["EDUCATOR_TOKEN"]]
    if any(len(t) < 24 for t in tokens) or tokens[0] == tokens[1]:
        raise ValueError("Two distinct role tokens of at least 24 characters are required")
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(app.config["DATABASE"]) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS evidence (
                id INTEGER PRIMARY KEY, source TEXT NOT NULL, prompt TEXT NOT NULL,
                response TEXT NOT NULL, decision TEXT, reasoning TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS privacy (id INTEGER PRIMARY KEY, shared INTEGER NOT NULL);
            INSERT OR IGNORE INTO privacy VALUES (1, 0);
        """)

    app.register_blueprint(api)
    app.teardown_appcontext(close_database)
    return app


api = Blueprint("ailp", __name__)


def database():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_database(_error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def role():
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    if hmac.compare_digest(token, current_app.config["STUDENT_TOKEN"]):
        return "student"
    if hmac.compare_digest(token, current_app.config["EDUCATOR_TOKEN"]):
        return "educator"
    abort(401)


def student():
    if role() != "student":
        abort(403)


def text_fields(names):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, "JSON object required")
    for name in names:
        if not isinstance(data.get(name), str) or not 1 <= len(data[name].strip()) <= 4000:
            abort(400, f"{name} must contain 1 to 4000 characters")
    return data


@api.after_request
def headers(response):
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@api.errorhandler(400)
@api.errorhandler(401)
@api.errorhandler(403)
@api.errorhandler(404)
@api.errorhandler(413)
def error(err):
    return jsonify(error=err.description), err.code


@api.get("/")
def index():
    return render_template("index.html", version=current_app.config["VERSION"])


@api.get("/health")
def health():
    database().execute("SELECT 1").fetchone()
    return jsonify(status="ok", version=current_app.config["VERSION"])


@api.get("/metrics")
def metrics():
    count = database().execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
    return f"ailp_up 1\nailp_evidence_count {count}\n", 200, {"Content-Type": "text/plain"}


@api.get("/api/evidence")
def evidence_list():
    student()
    rows = database().execute("SELECT * FROM evidence ORDER BY id").fetchall()
    return jsonify([dict(row) for row in rows])


@api.post("/api/evidence")
def evidence_import():
    student()
    data = text_fields(["source", "prompt", "response"])
    if data.get("consent") is not True:
        abort(400, "Explicit import consent required")
    db = database()
    cur = db.execute(
        "INSERT INTO evidence (source, prompt, response) VALUES (?, ?, ?)",
        (data["source"], data["prompt"], data["response"]),
    )
    db.commit()
    return jsonify(id=cur.lastrowid), 201


@api.put("/api/evidence/<int:record_id>/decision")
def decision_update(record_id):
    student()
    data = text_fields(["decision", "reasoning"])
    if data["decision"] not in DECISIONS:
        abort(400, "Decision must be Accepted, Modified or Rejected")
    db = database()
    cur = db.execute(
        "UPDATE evidence SET decision=?, reasoning=? WHERE id=?",
        (data["decision"], data["reasoning"], record_id),
    )
    if cur.rowcount == 0:
        abort(404)
    db.commit()
    return jsonify(status="saved")


@api.route("/api/privacy", methods=["GET", "PUT"])
def privacy():
    student()
    db = database()
    if request.method == "PUT":
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or type(data.get("shared")) is not bool:
            abort(400, "shared must be a boolean")
        db.execute("UPDATE privacy SET shared=? WHERE id=1", (int(data["shared"]),))
        db.commit()
    return jsonify(shared=bool(db.execute("SELECT shared FROM privacy").fetchone()[0]))


@api.get("/api/passport")
def passport():
    viewer = role()
    db = database()
    shared = bool(db.execute("SELECT shared FROM privacy").fetchone()[0])
    if viewer == "educator" and not shared:
        abort(403, "The student has not granted educator access")
    records = [dict(row) for row in db.execute("SELECT * FROM evidence ORDER BY id")]
    return jsonify(
        title="AI Learning Passport",
        evidence=records,
        shared=shared,
        review="Human educator judgement; no automated integrity score",
    )


@api.delete("/api/evidence/<int:record_id>")
def evidence_delete(record_id):
    student()
    db = database()
    cur = db.execute("DELETE FROM evidence WHERE id=?", (record_id,))
    if cur.rowcount == 0:
        abort(404)
    db.commit()
    return "", 204
