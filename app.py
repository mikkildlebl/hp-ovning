"""
Högskoleprovet Pro backend — Flask + SQLite (local) / PostgreSQL (production)
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

DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_PG = bool(DATABASE_URL)

app = Flask(__name__, static_folder=str(BASE))
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = USE_PG  # HTTPS in production

# ── DB abstraction ────────────────────────────────────────────────────────────

if USE_PG:
    import psycopg2
    import psycopg2.extras

    def get_db():
        url = DATABASE_URL
        # Render/Heroku provide postgres:// but psycopg2 needs postgresql://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(url)
        conn.autocommit = False
        return conn

    def db_fetchall(cur, query, params=()):
        cur.execute(query.replace("?", "%s"), params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def db_fetchone(cur, query, params=()):
        cur.execute(query.replace("?", "%s"), params)
        if cur.description is None:
            return None
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
        return dict(zip(cols, row)) if row else None

    def init_db():
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id       SERIAL PRIMARY KEY,
                    username TEXT   UNIQUE NOT NULL,
                    pw_hash  TEXT   NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS seen (
                    user_id     INTEGER NOT NULL,
                    question_id TEXT    NOT NULL,
                    PRIMARY KEY (user_id, question_id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS prefix_known (
                    user_id   INTEGER NOT NULL,
                    prefix_id TEXT    NOT NULL,
                    PRIMARY KEY (user_id, prefix_id)
                )
            """)
            conn.commit()

else:
    def get_db():
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        return conn

    def db_fetchall(cur, query, params=()):
        cur.execute(query, params)
        return [dict(r) for r in cur.fetchall()]

    def db_fetchone(cur, query, params=()):
        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None

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
                PRIMARY KEY (user_id, question_id)
            );
            CREATE TABLE IF NOT EXISTS prefix_known (
                user_id    INTEGER NOT NULL,
                prefix_id  TEXT    NOT NULL,
                PRIMARY KEY (user_id, prefix_id)
            );
            """)

# ── Auth helpers ──────────────────────────────────────────────────────────────

def current_user_id():
    return session.get("user_id")

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
        conn = get_db()
        cur = conn.cursor()
        if USE_PG:
            cur.execute(
                "INSERT INTO users (username, pw_hash) VALUES (%s, %s) RETURNING id",
                (username, pw_hash)
            )
            uid = cur.fetchone()[0]
            conn.commit()
        else:
            cur.execute("INSERT INTO users (username, pw_hash) VALUES (?,?)", (username, pw_hash))
            uid = cur.lastrowid
            conn.commit()
        conn.close()
        session["user_id"] = uid
        session["username"] = username
        return jsonify({"ok": True, "username": username})
    except Exception as e:
        if "unique" in str(e).lower() or "UNIQUE" in str(e):
            return jsonify({"error": "username taken"}), 409
        raise

@app.post("/api/login")
def login():
    data = request.json or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    conn = get_db()
    cur = conn.cursor()
    row = db_fetchone(cur, "SELECT * FROM users WHERE username=?", (username,))
    conn.close()
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
    conn = get_db()
    cur = conn.cursor()
    rows = db_fetchall(cur, "SELECT question_id FROM seen WHERE user_id=?", (uid,))
    conn.close()
    return jsonify({"seen": [r["question_id"] for r in rows]})

@app.post("/api/seen")
def post_seen():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not logged in"}), 401
    ids = request.json.get("ids", [])
    if not ids:
        return jsonify({"ok": True})
    conn = get_db()
    cur = conn.cursor()
    if USE_PG:
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO seen (user_id, question_id) VALUES %s ON CONFLICT DO NOTHING",
            [(uid, qid) for qid in ids]
        )
    else:
        cur.executemany(
            "INSERT OR IGNORE INTO seen (user_id, question_id) VALUES (?,?)",
            [(uid, qid) for qid in ids]
        )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.post("/api/reset")
def reset_seen():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not logged in"}), 401
    conn = get_db()
    cur = conn.cursor()
    if USE_PG:
        cur.execute("DELETE FROM seen WHERE user_id=%s", (uid,))
    else:
        cur.execute("DELETE FROM seen WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# ── Prefix/suffix known routes ────────────────────────────────────────────────

@app.get("/api/prefix-known")
def get_prefix_known():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not logged in"}), 401
    conn = get_db()
    cur = conn.cursor()
    rows = db_fetchall(cur, "SELECT prefix_id FROM prefix_known WHERE user_id=?", (uid,))
    conn.close()
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
    conn = get_db()
    cur = conn.cursor()
    if know:
        if USE_PG:
            cur.execute(
                "INSERT INTO prefix_known (user_id, prefix_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                (uid, pid)
            )
        else:
            cur.execute(
                "INSERT OR IGNORE INTO prefix_known (user_id, prefix_id) VALUES (?,?)",
                (uid, pid)
            )
    else:
        if USE_PG:
            cur.execute(
                "DELETE FROM prefix_known WHERE user_id=%s AND prefix_id=%s", (uid, pid)
            )
        else:
            cur.execute(
                "DELETE FROM prefix_known WHERE user_id=? AND prefix_id=?", (uid, pid)
            )
    conn.commit()
    conn.close()
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
    print("Högskoleprovet Pro running at http://localhost:3456")
    app.run(port=3456, debug=False)

init_db()  # also run when started by gunicorn
