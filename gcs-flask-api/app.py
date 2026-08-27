from flask import Flask, request, jsonify
from google.cloud import storage
import json
import os

app = Flask(__name__)

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
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy"}), 200

@app.route('/api/users', methods=['GET'])
def get_all_users():
    """Retrieve all users."""
    users = get_users_from_gcs()
    if isinstance(users, tuple):
        return users
    return jsonify(users), 200

@app.route('/api/users/<int:user_id>', methods=['GET'])
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
def update_user(user_id):
    """Update an existing user."""
    data = request.get_json()
    users = get_users_from_gcs()
    if isinstance(users, tuple):
        return users
    
    user = next((u for u in users if u['id'] == user_id), None)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    user.update({k: v for k, v in data.items() if v is not None})
    if save_users_to_gcs(users):
        return jsonify(user), 200
    return jsonify({"error": "Failed to update user"}), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Delete a user."""
    users = get_users_from_gcs()
    if isinstance(users, tuple):
        return users
    
    users = [u for u in users if u['id'] != user_id]
    if len(users) == len(get_users_from_gcs()):
        return jsonify({"error": "User not found"}), 404
    
    if save_users_to_gcs(users):
        return jsonify({"message": "User deleted successfully"}), 200
    return jsonify({"error": "Failed to delete user"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
