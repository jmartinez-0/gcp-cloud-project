import json
import os
import tempfile
from functools import wraps
from pathlib import Path
from threading import Lock

from flask import Flask, jsonify, request
from flask_cors import CORS
import firebase_admin
from firebase_admin import auth, credentials


app = Flask(__name__)
CORS(app)
DATA_FILE = Path(
    os.environ.get(
        "USERS_FILE",
        Path(__file__).resolve().parent.parent / "backend-data" / "users.json",
    )
).resolve()
DATA_LOCK = Lock()


def initialize_firebase():
    """Initialize Firebase Admin SDK from a local service-account JSON file."""
    if firebase_admin._apps:
        return

    service_account_path = (
        os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    )
    if not service_account_path:
        raise RuntimeError(
            "Set FIREBASE_SERVICE_ACCOUNT_PATH or GOOGLE_APPLICATION_CREDENTIALS "
            "to your Firebase service-account JSON file."
        )

    credential_path = Path(service_account_path)
    if not credential_path.is_absolute():
        credential_path = (Path(__file__).resolve().parent.parent / credential_path).resolve()
    if not credential_path.is_file():
        raise RuntimeError(f"Firebase service-account file not found: {credential_path}")
    firebase_admin.initialize_app(credentials.Certificate(str(credential_path)))


initialize_firebase()


def verify_firebase_token(route_handler):
    """Require a valid Firebase ID token for every API route."""
    @wraps(route_handler)
    def decorated_handler(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return jsonify({"error": "Missing Bearer token"}), 401

        token = authorization.removeprefix("Bearer ").strip()
        if not token:
            return jsonify({"error": "Missing Bearer token"}), 401

        try:
            decoded_token = auth.verify_id_token(token)
        except Exception:
            return jsonify({"error": "Invalid or expired Firebase token"}), 401

        request.firebase_user = decoded_token
        return route_handler(*args, **kwargs)

    return decorated_handler


def load_users():
    """Read the users list from the local JSON file."""
    try:
        with DATA_FILE.open(encoding="utf-8") as users_file:
            users = json.load(users_file)
        if not isinstance(users, list):
            raise ValueError("users JSON must contain an array")
        return users, None
    except (OSError, json.JSONDecodeError, ValueError) as error:
        return None, (jsonify({"error": f"Unable to read users file: {error}"}), 500)


def save_users(users):
    """Atomically replace the local JSON file with the updated users list."""
    try:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=DATA_FILE.parent,
            delete=False,
        ) as temporary_file:
            json.dump(users, temporary_file, indent=2)
            temporary_file.write("\n")
            temporary_path = Path(temporary_file.name)
        temporary_path.replace(DATA_FILE)
        return None
    except OSError as error:
        return jsonify({"error": f"Unable to save users file: {error}"}), 500


def get_users():
    users, error_response = load_users()
    if error_response:
        return error_response
    return jsonify(users), 200


@app.get("/api/health")
@verify_firebase_token
def health_check():
    return jsonify({"status": "healthy"}), 200


@app.get("/api/users")
@verify_firebase_token
def get_all_users():
    with DATA_LOCK:
        return get_users()


@app.get("/api/users/<int:user_id>")
@verify_firebase_token
def get_user(user_id):
    with DATA_LOCK:
        users, error_response = load_users()
        if error_response:
            return error_response
        user = next((user for user in users if user.get("id") == user_id), None)
        if user is None:
            return jsonify({"error": "User not found"}), 404
        return jsonify(user), 200


@app.post("/api/users")
@verify_firebase_token
def create_user():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data.get("name") or not data.get("email"):
        return jsonify({"error": "Missing required fields: name, email"}), 400

    with DATA_LOCK:
        users, error_response = load_users()
        if error_response:
            return error_response
        new_id = max((user.get("id", 0) for user in users), default=0) + 1
        new_user = {
            "id": new_id,
            "uid": request.firebase_user["uid"],
            **{key: data.get(key) for key in (
                "name", "email", "age", "location", "job_title", "created_at"
            )},
        }
        users.append(new_user)
        error_response = save_users(users)
        if error_response:
            return error_response
        return jsonify(new_user), 201


@app.put("/api/users/<int:user_id>")
@verify_firebase_token
def update_user(user_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    with DATA_LOCK:
        users, error_response = load_users()
        if error_response:
            return error_response
        user = next((user for user in users if user.get("id") == user_id), None)
        if user is None:
            return jsonify({"error": "User not found"}), 404
        user.update({
            key: value for key, value in data.items() if key not in {"id", "uid"}
        })
        error_response = save_users(users)
        if error_response:
            return error_response
        return jsonify(user), 200


@app.delete("/api/users/<int:user_id>")
@verify_firebase_token
def delete_user(user_id):
    with DATA_LOCK:
        users, error_response = load_users()
        if error_response:
            return error_response
        remaining_users = [user for user in users if user.get("id") != user_id]
        if len(remaining_users) == len(users):
            return jsonify({"error": "User not found"}), 404
        error_response = save_users(remaining_users)
        if error_response:
            return error_response
        return jsonify({"message": "User deleted successfully"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)