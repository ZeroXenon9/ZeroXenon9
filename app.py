import os
import json
import uuid
import sqlite3
import numpy as np
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template
from PIL import Image

app = Flask(__name__)
UPLOAD_FOLDER = Path("uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)
DB_PATH = "photos.db"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

try:
    import face_recognition
    FACE_BACKEND = "face_recognition"
except ImportError:
    import cv2
    FACE_BACKEND = "opencv"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            upload_time TEXT NOT NULL,
            face_encodings TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def is_allowed(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def encode_faces_fr(image_path: str) -> list[list[float]]:
    """Extract face encodings using face_recognition library."""
    image = face_recognition.load_image_file(image_path)
    encodings = face_recognition.face_encodings(image)
    return [enc.tolist() for enc in encodings]


def encode_faces_cv(image_path: str) -> list[list[float]]:
    """
    Fallback: use OpenCV Haar cascade for detection,
    then extract a flattened histogram as a rough embedding.
    Less accurate but works without dlib.
    """
    img = cv2.imread(image_path)
    if img is None:
        return []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    encodings = []
    for (x, y, w, h) in faces:
        face_roi = cv2.resize(gray[y:y+h, x:x+w], (64, 64))
        hist = cv2.calcHist([face_roi], [0], None, [128], [0, 256])
        cv2.normalize(hist, hist)
        encodings.append(hist.flatten().tolist())
    return encodings


def encode_faces(image_path: str) -> list[list[float]]:
    if FACE_BACKEND == "face_recognition":
        return encode_faces_fr(image_path)
    return encode_faces_cv(image_path)


def faces_match_fr(known_encodings: list, candidate_encodings: list, tolerance: float = 0.6) -> bool:
    if not known_encodings or not candidate_encodings:
        return False
    known = [np.array(e) for e in known_encodings]
    for candidate in candidate_encodings:
        results = face_recognition.compare_faces(known, np.array(candidate), tolerance=tolerance)
        if any(results):
            return True
    return False


def faces_match_cv(known_encodings: list, candidate_encodings: list, threshold: float = 0.7) -> bool:
    if not known_encodings or not candidate_encodings:
        return False
    for known in known_encodings:
        known_vec = np.array(known)
        for candidate in candidate_encodings:
            candidate_vec = np.array(candidate)
            # Bhattacharyya coefficient-like comparison using dot product on normalized histograms
            score = float(np.dot(known_vec, candidate_vec))
            if score >= threshold:
                return True
    return False


def faces_match(known_encodings: list, candidate_encodings: list) -> bool:
    if FACE_BACKEND == "face_recognition":
        return faces_match_fr(known_encodings, candidate_encodings)
    return faces_match_cv(known_encodings, candidate_encodings)


def make_thumbnail(src_path: str, thumb_path: str, size: tuple = (300, 300)):
    with Image.open(src_path) as img:
        img.thumbnail(size, Image.LANCZOS)
        img.save(thumb_path, optimize=True)


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", backend=FACE_BACKEND)


@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/api/photos", methods=["GET"])
def list_photos():
    db = get_db()
    rows = db.execute("SELECT id, original_name, filename, upload_time FROM photos ORDER BY upload_time DESC").fetchall()
    db.close()
    photos = [dict(r) for r in rows]
    for p in photos:
        p["url"] = f"/uploads/{p['filename']}"
        p["thumb_url"] = f"/uploads/thumb_{p['filename']}"
    return jsonify(photos)


@app.route("/api/upload", methods=["POST"])
def upload_photos():
    files = request.files.getlist("photos")
    if not files:
        return jsonify({"error": "No files uploaded"}), 400

    saved = []
    errors = []
    for f in files:
        if not f.filename:
            continue
        if not is_allowed(f.filename):
            errors.append(f"{f.filename}: unsupported format")
            continue

        ext = Path(f.filename).suffix.lower()
        photo_id = str(uuid.uuid4())
        filename = f"{photo_id}{ext}"
        save_path = UPLOAD_FOLDER / filename
        f.save(str(save_path))

        # Make thumbnail
        try:
            make_thumbnail(str(save_path), str(UPLOAD_FOLDER / f"thumb_{filename}"))
        except Exception:
            pass

        # Extract face encodings (may be slow for large batches)
        try:
            encodings = encode_faces(str(save_path))
        except Exception:
            encodings = []

        db = get_db()
        db.execute(
            "INSERT INTO photos (id, filename, original_name, upload_time, face_encodings) VALUES (?,?,?,?,?)",
            (photo_id, filename, f.filename, datetime.utcnow().isoformat(), json.dumps(encodings)),
        )
        db.commit()
        db.close()

        saved.append({
            "id": photo_id,
            "filename": filename,
            "original_name": f.filename,
            "url": f"/uploads/{filename}",
            "thumb_url": f"/uploads/thumb_{filename}",
            "faces_found": len(encodings),
        })

    return jsonify({"saved": saved, "errors": errors})


@app.route("/api/find-person", methods=["POST"])
def find_person():
    ref_file = request.files.get("reference")
    if not ref_file:
        return jsonify({"error": "No reference photo provided"}), 400

    # Save reference temporarily
    ref_id = str(uuid.uuid4())
    ext = Path(ref_file.filename or "ref.jpg").suffix.lower() or ".jpg"
    ref_path = UPLOAD_FOLDER / f"_ref_{ref_id}{ext}"
    ref_file.save(str(ref_path))

    try:
        ref_encodings = encode_faces(str(ref_path))
    except Exception as e:
        ref_path.unlink(missing_ok=True)
        return jsonify({"error": f"Could not process reference photo: {e}"}), 400
    finally:
        ref_path.unlink(missing_ok=True)

    if not ref_encodings:
        return jsonify({"error": "No face detected in the reference photo. Please use a clear, front-facing photo."}), 400

    db = get_db()
    rows = db.execute("SELECT id, filename, original_name, upload_time, face_encodings FROM photos").fetchall()
    db.close()

    matches = []
    for row in rows:
        stored_encodings = json.loads(row["face_encodings"] or "[]")
        if faces_match(ref_encodings, stored_encodings):
            matches.append({
                "id": row["id"],
                "filename": row["filename"],
                "original_name": row["original_name"],
                "upload_time": row["upload_time"],
                "url": f"/uploads/{row['filename']}",
                "thumb_url": f"/uploads/thumb_{row['filename']}",
            })

    return jsonify({"matches": matches, "total": len(matches)})


@app.route("/api/delete", methods=["POST"])
def delete_photos():
    data = request.get_json()
    ids = data.get("ids", []) if data else []
    if not ids:
        return jsonify({"error": "No photo IDs provided"}), 400

    db = get_db()
    deleted = []
    for photo_id in ids:
        row = db.execute("SELECT filename FROM photos WHERE id=?", (photo_id,)).fetchone()
        if row:
            for path in [UPLOAD_FOLDER / row["filename"], UPLOAD_FOLDER / f"thumb_{row['filename']}"]:
                path.unlink(missing_ok=True)
            db.execute("DELETE FROM photos WHERE id=?", (photo_id,))
            deleted.append(photo_id)
    db.commit()
    db.close()

    return jsonify({"deleted": deleted, "count": len(deleted)})


@app.route("/api/reindex/<photo_id>", methods=["POST"])
def reindex_photo(photo_id):
    """Re-run face detection on a single photo (useful after backend upgrade)."""
    db = get_db()
    row = db.execute("SELECT filename FROM photos WHERE id=?", (photo_id,)).fetchone()
    if not row:
        db.close()
        return jsonify({"error": "Photo not found"}), 404

    path = str(UPLOAD_FOLDER / row["filename"])
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
