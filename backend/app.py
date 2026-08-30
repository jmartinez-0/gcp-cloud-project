from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, auth
import os
from dotenv import load_dotenv
from functools import wraps

# Merge this with my ../backend-data/app.py code to create a single Flask app that uses both GCS and Firebase for user management.

load_dotenv()

app = Flask(__name__)
CORS(app)

# Initialize Firebase Admin SDK
# Download your Firebase service account key from Firebase Console
# Project Settings → Service Accounts → Generate new private key
firebase_admin.initialize_app(credentials.Certificate('path/to/serviceAccountKey.json'))

# Token verification decorator
def verify_firebase_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            return jsonify({'error': 'Missing token'}), 401
        
        try:
            decoded_token = auth.verify_id_token(token)
            request.user_id = decoded_token['uid']
            request.user_email = decoded_token.get('email', '')
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({'error': f'Invalid token: {str(e)}'}), 401
    
    return decorated_function

# Example: mock user data (replace with database later)
USERS = [
    {'id': '1', 'name': 'John Doe', 'email': 'john@example.com'},
    {'id': '2', 'name': 'Jane Smith', 'email': 'jane@example.com'},
]

@app.route('/api/users', methods=['GET'])
@verify_firebase_token
def get_users():
    """Get all users (requires auth)"""
    return jsonify(USERS)

@app.route('/api/users/<user_id>', methods=['GET'])
@verify_firebase_token
def get_user(user_id):
    """Get single user (requires auth)"""
    user = next((u for u in USERS if u['id'] == user_id), None)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user)

@app.route('/api/users/<user_id>', methods=['PUT'])
@verify_firebase_token
def update_user(user_id):
    """Update user (requires auth)"""
    user = next((u for u in USERS if u['id'] == user_id), None)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.json
    user.update(data)
    return jsonify(user)

@app.route('/api/users/<user_id>', methods=['DELETE'])
@verify_firebase_token
def delete_user(user_id):
    """Delete user (requires auth)"""
    global USERS
    USERS = [u for u in USERS if u['id'] != user_id]
    return jsonify({'message': 'User deleted'})

@app.route('/health', methods=['GET'])
def health():
    """Health check (no auth required)"""
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, port=port)
