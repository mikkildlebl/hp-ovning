"""
HP Övning backend — Flask + SQLite
Run: python app.py
"""
import os, json, secrets, sqlite3
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, send_file, session
import bcrypt

BASE      = Path(__file__).resolve().parent
_local    = Path(os.environ.get("LOCALAPPDATA", "")) / "HPOvning" if os.environ.get("LOCALAPPDATA") else None
LOCAL_DIR = _local if (_local and (_local / "hp_questions.json").exists()) else BASE
if LOCAL_DIR != BASE:
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR    = _local if _local else BASE
DB_DIR.mkdir(parents=True, exist_ok=True)
DB        = DB_DIR / "users.db"
TEXTS_DIR = LOCAL_DIR / "texts" if (LOCAL_DIR / "texts").exists() else BASE / "texts"
app  = Flask(__name__, static_folder=str(BASE))
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False

# ── DB setup ─────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT    UNIQUE NOT NULL,
            pw_hash  TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS seen (
            user_id     INTEGER NOT NULL,
            question_id TEXT    NOT NULL,
            PRIMARY KEY (user_id, question_id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS prefix_known (
            user_id    INTEGER NOT NULL,
            prefix_id  TEXT    NOT NULL,
            PRIMARY KEY (user_id, prefix_id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """)

# ── Auth helpers ──────────────────────────────────────────────────────────────

def current_user_id():
    return session.get("user_id")

def require_auth():
    uid = current_user_id()
    if not uid:
        return None, jsonify({"error": "not logged in"}), 401
    return uid, None, None

# ── Auth routes ───────────────────────────────────────────────────────────────

@app.post("/api/register")
def register():
    data = request.json or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    try:
        with get_db() as db:
            cur = db.execute("INSERT INTO users (username, pw_hash) VALUES (?,?)", (username, pw_hash))
            session["user_id"] = cur.lastrowid
            session["username"] = username
        return jsonify({"ok": True, "username": username})
    except sqlite3.IntegrityError:
        return jsonify({"error": "username taken"}), 409

@app.post("/api/login")
def login():
    data = request.json or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not row or not bcrypt.checkpw(password.encode(), row["pw_hash"].encode()):
        return jsonify({"error": "wrong username or password"}), 401
    session["user_id"]  = row["id"]
    session["username"] = row["username"]
    return jsonify({"ok": True, "username": username})

@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})

@app.get("/api/me")
def me():
    uid = current_user_id()
    if not uid:
        return jsonify({"loggedIn": False})
    return jsonify({"loggedIn": True, "username": session.get("username")})

# ── Progress routes ───────────────────────────────────────────────────────────

@app.get("/api/seen")
def get_seen():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not logged in"}), 401
    with get_db() as db:
        rows = db.execute("SELECT question_id FROM seen WHERE user_id=?", (uid,)).fetchall()
    return jsonify({"seen": [r["question_id"] for r in rows]})

@app.post("/api/seen")
def post_seen():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not logged in"}), 401
    ids = request.json.get("ids", [])
    with get_db() as db:
        db.executemany(
            "INSERT OR IGNORE INTO seen (user_id, question_id) VALUES (?,?)",
            [(uid, qid) for qid in ids]
        )
    return jsonify({"ok": True})

@app.post("/api/reset")
def reset_seen():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not logged in"}), 401
    qtype = request.json.get("type")  # optional: reset only one type
    with get_db() as db:
        if qtype:
            # We don't store type in seen table, so we'd need to cross-ref with questions
            # For simplicity just reset all
            pass
        db.execute("DELETE FROM seen WHERE user_id=?", (uid,))
    return jsonify({"ok": True})

# ── Prefix/suffix known routes ───────────────────────────────────────────────

@app.get("/api/prefix-known")
def get_prefix_known():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not logged in"}), 401
    with get_db() as db:
        rows = db.execute("SELECT prefix_id FROM prefix_known WHERE user_id=?", (uid,)).fetchall()
    return jsonify({"known": [r["prefix_id"] for r in rows]})

@app.post("/api/prefix-known")
def post_prefix_known():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not logged in"}), 401
    data = request.json or {}
    pid  = data.get("id")
    know = data.get("known", False)
    if not pid:
        return jsonify({"error": "missing id"}), 400
    with get_db() as db:
        if know:
            db.execute("INSERT OR IGNORE INTO prefix_known (user_id, prefix_id) VALUES (?,?)", (uid, pid))
        else:
            db.execute("DELETE FROM prefix_known WHERE user_id=? AND prefix_id=?", (uid, pid))
    return jsonify({"ok": True})

# ── Static files ──────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return send_file(BASE / "index.html")

@app.get("/hp_questions.json")
def questions_json():
    resp = send_file(LOCAL_DIR / "hp_questions.json")
    resp.headers['Cache-Control'] = 'no-store'
    return resp

@app.get("/images/<path:filename>")
def images(filename):
    return send_from_directory(BASE / "images", filename)

@app.get("/texts/<path:filename>")
def texts(filename):
    return send_from_directory(TEXTS_DIR, filename)

# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("Högskoleprovet pro running at http://localhost:3456")
    app.run(port=3456, debug=False)
