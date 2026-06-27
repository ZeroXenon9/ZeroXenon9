import os
import json
import uuid
import sqlite3
import numpy as np
from pathlib import Path
from datetime import datetime
from flask import (
    Flask, request, jsonify, send_from_directory,
    render_template, redirect, url_for, session
)
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image

# ── App setup ──────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

UPLOAD_BASE = Path("uploads")
UPLOAD_BASE.mkdir(exist_ok=True)
DB_PATH = "photos.db"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
FACE_MODEL = os.environ.get("FACE_MODEL", "small")  # "small" or "large"
MAX_FILE_MB = 20

login_manager = LoginManager(app)
login_manager.login_view = "login_page"

try:
    import face_recognition
    FACE_BACKEND = "face_recognition"
except ImportError:
    import cv2
    FACE_BACKEND = "opencv"


# ── User model ─────────────────────────────────────────────────────────────────
class User(UserMixin):
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email


@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    db.close()
    if row:
        return User(row["id"], row["username"], row["email"])
    return None


# ── DB helpers ─────────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id       TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email    TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at    TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS albums (
            id         TEXT PRIMARY KEY,
            user_id    TEXT NOT NULL REFERENCES users(id),
            name       TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS photos (
            id             TEXT PRIMARY KEY,
            user_id        TEXT NOT NULL REFERENCES users(id),
            filename       TEXT NOT NULL,
            original_name  TEXT NOT NULL,
            upload_time    TEXT NOT NULL,
            face_encodings TEXT
        );

        CREATE TABLE IF NOT EXISTS photo_albums (
            photo_id TEXT REFERENCES photos(id) ON DELETE CASCADE,
            album_id TEXT REFERENCES albums(id)  ON DELETE CASCADE,
            PRIMARY KEY (photo_id, album_id)
        );
    """)
    # Safe migrations for installs that have the old schema without user_id
    for col, defn in [("user_id", "TEXT"), ("face_encodings", "TEXT")]:
        try:
            conn.execute(f"ALTER TABLE photos ADD COLUMN {col} {defn}")
        except Exception:
            pass
    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def user_upload_dir(user_id: str) -> Path:
    p = UPLOAD_BASE / user_id
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── Image helpers ──────────────────────────────────────────────────────────────
def is_allowed(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def make_thumbnail(src_path: str, thumb_path: str, size: tuple = (300, 300)):
    with Image.open(src_path) as img:
        img.thumbnail(size, Image.LANCZOS)
        img.save(thumb_path, optimize=True)


# ── Face recognition ───────────────────────────────────────────────────────────
def encode_faces_fr(image_path: str) -> list:
    image = face_recognition.load_image_file(image_path)
    encodings = face_recognition.face_encodings(image, model=FACE_MODEL)
    return [enc.tolist() for enc in encodings]


def encode_faces_cv(image_path: str) -> list:
    img = cv2.imread(image_path)
    if img is None:
        return []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    encodings = []
    for (x, y, w, h) in faces:
        face_roi = cv2.resize(gray[y : y + h, x : x + w], (64, 64))
        hist = cv2.calcHist([face_roi], [0], None, [128], [0, 256])
        cv2.normalize(hist, hist)
        encodings.append(hist.flatten().tolist())
    return encodings


def encode_faces(image_path: str) -> list:
    if FACE_BACKEND == "face_recognition":
        return encode_faces_fr(image_path)
    return encode_faces_cv(image_path)


def faces_match_fr(known_encodings: list, candidate_encodings: list, tolerance: float = 0.6) -> tuple:
    if not known_encodings or not candidate_encodings:
        return False, 1.0
    known = [np.array(e) for e in known_encodings]
    best_distance = 1.0
    for candidate in candidate_encodings:
        cand_arr = np.array(candidate)
        distances = face_recognition.face_distance(known, cand_arr)
        min_dist = float(np.min(distances))
        if min_dist < best_distance:
            best_distance = min_dist
        if min_dist <= tolerance:
            return True, min_dist
    return False, best_distance


def faces_match_cv(known_encodings: list, candidate_encodings: list, threshold: float = 0.7) -> tuple:
    if not known_encodings or not candidate_encodings:
        return False, 0.0
    best_score = 0.0
    for known in known_encodings:
        known_vec = np.array(known)
        for candidate in candidate_encodings:
            score = float(np.dot(known_vec, np.array(candidate)))
            if score > best_score:
                best_score = score
            if score >= threshold:
                return True, score
    return False, best_score


def faces_match(known_encodings: list, candidate_encodings: list, tolerance: float = 0.6) -> tuple:
    if FACE_BACKEND == "face_recognition":
        return faces_match_fr(known_encodings, candidate_encodings, tolerance)
    return faces_match_cv(known_encodings, candidate_encodings, threshold=tolerance)


def photo_url(user_id: str, filename: str) -> str:
    return f"/uploads/{user_id}/{filename}"


def thumb_url(user_id: str, filename: str) -> str:
    return f"/uploads/{user_id}/thumb_{filename}"


# ── Auth pages ─────────────────────────────────────────────────────────────────
@app.route("/login")
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("auth.html")


@app.route("/auth/register", methods=["POST"])
def auth_register():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    email    = (data.get("email")    or "").strip().lower()
    password = data.get("password")  or ""

    if not username or not email or not password:
        return jsonify({"error": "All fields are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    db = get_db()
    if db.execute("SELECT 1 FROM users WHERE email=? OR username=?", (email, username)).fetchone():
        db.close()
        return jsonify({"error": "Username or email already taken"}), 409

    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, username, email, password_hash, created_at) VALUES (?,?,?,?,?)",
        (user_id, username, email, generate_password_hash(password), datetime.utcnow().isoformat()),
    )
    db.commit()
    db.close()

    user = User(user_id, username, email)
    login_user(user, remember=True)
    return jsonify({"ok": True, "username": username})


@app.route("/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json() or {}
    email    = (data.get("email")    or "").strip().lower()
    password =  data.get("password") or ""

    db = get_db()
    row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    db.close()

    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Invalid email or password"}), 401

    user = User(row["id"], row["username"], row["email"])
    login_user(user, remember=True)
    return jsonify({"ok": True, "username": row["username"]})


@app.route("/auth/logout", methods=["POST"])
@login_required
def auth_logout():
    logout_user()
    return jsonify({"ok": True})


# ── Main page ──────────────────────────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    return render_template("index.html", backend=FACE_BACKEND, user=current_user)


# ── File serving ───────────────────────────────────────────────────────────────
@app.route("/uploads/<user_id>/<path:filename>")
@login_required
def serve_upload(user_id, filename):
    if user_id != current_user.id:
        return jsonify({"error": "Forbidden"}), 403
    return send_from_directory(UPLOAD_BASE / user_id, filename)


# ── Photos API ─────────────────────────────────────────────────────────────────
@app.route("/api/photos", methods=["GET"])
@login_required
def list_photos():
    album_id = request.args.get("album_id")
    db = get_db()
    if album_id:
        rows = db.execute(
            """SELECT p.id, p.original_name, p.filename, p.upload_time
               FROM photos p
               JOIN photo_albums pa ON pa.photo_id = p.id
               WHERE p.user_id=? AND pa.album_id=?
               ORDER BY p.upload_time DESC""",
            (current_user.id, album_id),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT id, original_name, filename, upload_time FROM photos WHERE user_id=? ORDER BY upload_time DESC",
            (current_user.id,),
        ).fetchall()
    db.close()
    photos = []
    for r in rows:
        p = dict(r)
        p["url"]       = photo_url(current_user.id, p["filename"])
        p["thumb_url"] = thumb_url(current_user.id, p["filename"])
        photos.append(p)
    return jsonify(photos)


@app.route("/api/upload", methods=["POST"])
@login_required
def upload_photo():
    files = request.files.getlist("photos")
    album_id = request.form.get("album_id") or None
    if not files:
        return jsonify({"error": "No files uploaded"}), 400

    uid = current_user.id
    upload_dir = user_upload_dir(uid)
    saved = []
    errors = []

    for f in files:
        if not f.filename:
            continue
        if not is_allowed(f.filename):
            errors.append(f"{f.filename}: unsupported format")
            continue

        ext      = Path(f.filename).suffix.lower()
        photo_id = str(uuid.uuid4())
        filename = f"{photo_id}{ext}"
        save_path = upload_dir / filename

        f.save(str(save_path))

        try:
            make_thumbnail(str(save_path), str(upload_dir / f"thumb_{filename}"))
        except Exception:
            pass

        try:
            encodings = encode_faces(str(save_path))
        except Exception:
            encodings = []

        db = get_db()
        db.execute(
            "INSERT INTO photos (id, user_id, filename, original_name, upload_time, face_encodings) VALUES (?,?,?,?,?,?)",
            (photo_id, uid, filename, f.filename, datetime.utcnow().isoformat(), json.dumps(encodings)),
        )
        if album_id:
            db.execute("INSERT OR IGNORE INTO photo_albums (photo_id, album_id) VALUES (?,?)", (photo_id, album_id))
        db.commit()
        db.close()

        saved.append({
            "id":            photo_id,
            "filename":      filename,
            "original_name": f.filename,
            "url":           photo_url(uid, filename),
            "thumb_url":     thumb_url(uid, filename),
            "faces_found":   len(encodings),
        })

    return jsonify({"saved": saved, "errors": errors})


@app.route("/api/delete", methods=["POST"])
@login_required
def delete_photos():
    data = request.get_json()
    ids  = data.get("ids", []) if data else []
    if not ids:
        return jsonify({"error": "No photo IDs provided"}), 400

    uid      = current_user.id
    upload_dir = user_upload_dir(uid)
    db       = get_db()
    deleted  = []

    for photo_id in ids:
        row = db.execute("SELECT filename FROM photos WHERE id=? AND user_id=?", (photo_id, uid)).fetchone()
        if row:
            for path in [upload_dir / row["filename"], upload_dir / f"thumb_{row['filename']}"]:
                path.unlink(missing_ok=True)
            db.execute("DELETE FROM photos WHERE id=?", (photo_id,))
            deleted.append(photo_id)

    db.commit()
    db.close()
    return jsonify({"deleted": deleted, "count": len(deleted)})


@app.route("/api/find-person", methods=["POST"])
@login_required
def find_person():
    ref_files = request.files.getlist("reference")
    if not ref_files:
        return jsonify({"error": "No reference photo provided"}), 400

    tolerance = float(request.form.get("tolerance", 0.6))
    tolerance = max(0.3, min(0.9, tolerance))

    uid        = current_user.id
    upload_dir = user_upload_dir(uid)
    ref_encodings = []

    for ref_file in ref_files:
        ref_id  = str(uuid.uuid4())
        ext     = Path(ref_file.filename or "ref.jpg").suffix.lower() or ".jpg"
        ref_path = upload_dir / f"_ref_{ref_id}{ext}"
        ref_file.save(str(ref_path))
        try:
            encs = encode_faces(str(ref_path))
            ref_encodings.extend(encs)
        except Exception:
            pass
        finally:
            ref_path.unlink(missing_ok=True)

    if not ref_encodings:
        return jsonify({"error": "No face detected in the reference photo(s). Use a clear, front-facing photo."}), 400

    db   = get_db()
    rows = db.execute(
        "SELECT id, filename, original_name, upload_time, face_encodings FROM photos WHERE user_id=?",
        (uid,),
    ).fetchall()
    db.close()

    matches = []
    for row in rows:
        stored = json.loads(row["face_encodings"] or "[]")
        matched, distance = faces_match(ref_encodings, stored, tolerance)
        if matched:
            confidence = max(0, round((1 - distance) * 100))
            matches.append({
                "id":            row["id"],
                "filename":      row["filename"],
                "original_name": row["original_name"],
                "upload_time":   row["upload_time"],
                "url":           photo_url(uid, row["filename"]),
                "thumb_url":     thumb_url(uid, row["filename"]),
                "confidence":    confidence,
            })

    matches.sort(key=lambda m: m["confidence"], reverse=True)
    return jsonify({"matches": matches, "total": len(matches)})


# ── Albums API ─────────────────────────────────────────────────────────────────
@app.route("/api/albums", methods=["GET"])
@login_required
def list_albums():
    db   = get_db()
    rows = db.execute(
        """SELECT a.id, a.name, a.created_at,
                  COUNT(pa.photo_id) AS photo_count
           FROM albums a
           LEFT JOIN photo_albums pa ON pa.album_id = a.id
           WHERE a.user_id=?
           GROUP BY a.id
           ORDER BY a.created_at""",
        (current_user.id,),
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/albums", methods=["POST"])
@login_required
def create_album():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Album name is required"}), 400

    album_id = str(uuid.uuid4())
    db = get_db()
    db.execute(
        "INSERT INTO albums (id, user_id, name, created_at) VALUES (?,?,?,?)",
        (album_id, current_user.id, name, datetime.utcnow().isoformat()),
    )
    db.commit()
    db.close()
    return jsonify({"id": album_id, "name": name, "photo_count": 0}), 201


@app.route("/api/albums/<album_id>", methods=["DELETE"])
@login_required
def delete_album(album_id):
    db = get_db()
    row = db.execute("SELECT id FROM albums WHERE id=? AND user_id=?", (album_id, current_user.id)).fetchone()
    if not row:
        db.close()
        return jsonify({"error": "Album not found"}), 404
    db.execute("DELETE FROM albums WHERE id=?", (album_id,))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.route("/api/photos/<photo_id>/album", methods=["POST"])
@login_required
def assign_album(photo_id):
    data     = request.get_json() or {}
    album_id = data.get("album_id")
    db       = get_db()

    row = db.execute("SELECT id FROM photos WHERE id=? AND user_id=?", (photo_id, current_user.id)).fetchone()
    if not row:
        db.close()
        return jsonify({"error": "Photo not found"}), 404

    if album_id:
        db.execute("INSERT OR IGNORE INTO photo_albums (photo_id, album_id) VALUES (?,?)", (photo_id, album_id))
    else:
        db.execute("DELETE FROM photo_albums WHERE photo_id=?", (photo_id,))

    db.commit()
    db.close()
    return jsonify({"ok": True})


# ── Reindex ────────────────────────────────────────────────────────────────────
@app.route("/api/reindex/<photo_id>", methods=["POST"])
@login_required
def reindex_photo(photo_id):
    db  = get_db()
    row = db.execute("SELECT filename FROM photos WHERE id=? AND user_id=?", (photo_id, current_user.id)).fetchone()
    if not row:
        db.close()
        return jsonify({"error": "Photo not found"}), 404

    path = str(user_upload_dir(current_user.id) / row["filename"])
    try:
        encodings = encode_faces(path)
    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 500

    db.execute("UPDATE photos SET face_encodings=? WHERE id=?", (json.dumps(encodings), photo_id))
    db.commit()
    db.close()
    return jsonify({"faces_found": len(encodings)})


if __name__ == "__main__":
    init_db()
    print(f"Face recognition backend: {FACE_BACKEND}")
    app.run(debug=True, host="0.0.0.0", port=5000)
