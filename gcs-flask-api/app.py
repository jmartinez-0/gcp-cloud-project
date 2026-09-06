from functools import wraps
from pathlib import Path

from flask import Flask, request, jsonify
from flask_cors import CORS
from google.cloud import storage
import firebase_admin
from firebase_admin import auth, credentials
import json
import os

app = Flask(__name__)
CORS(app)


def initialize_firebase():
    """Initialize Firebase Admin SDK from local or Google runtime credentials."""
    if firebase_admin._apps:
        return

    firebase_project_id = os.environ.get("FIREBASE_PROJECT_ID")
    firebase_options = {"projectId": firebase_project_id} if firebase_project_id else None
    service_account_path = (
        os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    )
    if service_account_path:
        credential_path = Path(service_account_path)
        if not credential_path.is_absolute():
            credential_path = (Path(__file__).resolve().parent.parent / credential_path).resolve()
        if not credential_path.is_file():
            raise RuntimeError(f"Firebase service-account file not found: {credential_path}")
        firebase_admin.initialize_app(
            credentials.Certificate(str(credential_path)),
            options=firebase_options,
        )
        return

    # Cloud Run and other Google-managed runtimes provide Application Default Credentials.
    firebase_admin.initialize_app(options=firebase_options)


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
        except Exception as error:
            app.logger.warning("Firebase ID token verification failed: %s", error)
            return jsonify({"error": "Invalid or expired Firebase token"}), 401

        request.firebase_user = decoded_token
        return route_handler(*args, **kwargs)

    return decorated_handler

# Initialize GCS client
storage_client = storage.Client()
BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME', 'your-bucket-name')
BLOB_PATH = 'users/users.json'

def get_users_from_gcs():
    """Retrieve users from GCS bucket."""
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(BLOB_PATH)
        data = blob.download_as_string()
        return json.loads(data)
    except Exception as e:
        return {"error": str(e)}, 500

def save_users_to_gcs(users):
    """Save users back to GCS bucket."""
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(BLOB_PATH)
        blob.upload_from_string(json.dumps(users, indent=2))
        return True
    except Exception as e:
        print(f"Error saving to GCS: {e}")
        return False

@app.route('/api/health', methods=['GET'])
@verify_firebase_token
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy"}), 200

@app.route('/api/users', methods=['GET'])
@verify_firebase_token
def get_all_users():
    """Retrieve all users."""
    users = get_users_from_gcs()
    if isinstance(users, tuple):
        return users
    return jsonify(users), 200

@app.route('/api/users/<int:user_id>', methods=['GET'])
@verify_firebase_token
def get_user(user_id):
    """Retrieve a specific user by ID."""
    users = get_users_from_gcs()
    if isinstance(users, tuple):
        return users
    user = next((u for u in users if u['id'] == user_id), None)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user), 200

@app.route('/api/users', methods=['POST'])
@verify_firebase_token
def create_user():
    """Create a new user."""
    data = request.get_json()
    if not data or 'name' not in data or 'email' not in data:
        return jsonify({"error": "Missing required fields: name, email"}), 400
    
    users = get_users_from_gcs()
    if isinstance(users, tuple):
        return users
    
    new_id = max([u['id'] for u in users]) + 1 if users else 1
    new_user = {
        "id": new_id,
        "uid": request.firebase_user["uid"],
        "name": data.get('name'),
        "email": data.get('email'),
        "age": data.get('age'),
        "location": data.get('location'),
        "job_title": data.get('job_title'),
        "created_at": data.get('created_at')
    }
    
    users.append(new_user)
    if save_users_to_gcs(users):
        return jsonify(new_user), 201
    return jsonify({"error": "Failed to create user"}), 500

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@verify_firebase_token
def update_user(user_id):
    """Update an existing user."""
    data = request.get_json()
    users = get_users_from_gcs()
    if isinstance(users, tuple):
        return users
    
    user = next((u for u in users if u['id'] == user_id), None)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    user.update({k: v for k, v in data.items() if k not in {'id', 'uid'} and v is not None})
    if save_users_to_gcs(users):
        return jsonify(user), 200
    return jsonify({"error": "Failed to update user"}), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@verify_firebase_token
def delete_user(user_id):
    """Delete a user."""
    users = get_users_from_gcs()
    if isinstance(users, tuple):
        return users
    
    remaining_users = [u for u in users if u['id'] != user_id]
    if len(remaining_users) == len(users):
        return jsonify({"error": "User not found"}), 404
    
    if save_users_to_gcs(remaining_users):
        return jsonify({"message": "User deleted successfully"}), 200
    return jsonify({"error": "Failed to delete user"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
