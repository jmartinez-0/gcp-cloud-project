import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import {
  getAuth,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";

const appConfig = window.__APP_CONFIG__ || {};

const firebaseConfig = {
  apiKey: appConfig.FIREBASE_API_KEY || "",
  authDomain: appConfig.FIREBASE_AUTH_DOMAIN || "",
  projectId: appConfig.FIREBASE_PROJECT_ID || "",
  storageBucket: appConfig.FIREBASE_STORAGE_BUCKET || "",
  messagingSenderId: appConfig.FIREBASE_MESSAGING_SENDER_ID || "",
  appId: appConfig.FIREBASE_APP_ID || "",
  measurementId: appConfig.FIREBASE_MEASUREMENT_ID || undefined,
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const BACKEND_URL = appConfig.BACKEND_URL || 'http://localhost:5000';

async function getAuthHeaders() {
  if (!auth.currentUser) {
    throw new Error('You must be signed in');
  }

  const token = await auth.currentUser.getIdToken();
  return {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json'
  };
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${BACKEND_URL}${path}`, {
    ...options,
    headers: {
      ...(await getAuthHeaders()),
      ...options.headers
    }
  });

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(payload?.error || `Request failed (${response.status})`);
  }
  return payload;
}

async function checkBackendHealth() {
  return apiRequest('/api/health');
}

async function getUsers() {
  return apiRequest('/api/users');
}

async function getUser(userId) {
  return apiRequest(`/api/users/${userId}`);
}

async function createUser(userData) {
  return apiRequest('/api/users', {
    method: 'POST',
    body: JSON.stringify(userData)
  });
}

async function updateUser(userId, userData) {
  return apiRequest(`/api/users/${userId}`, {
    method: 'PUT',
    body: JSON.stringify(userData)
  });
}

async function deleteUser(userId) {
  return apiRequest(`/api/users/${userId}`, { method: 'DELETE' });
}

async function handleSignup() {
  const email = document.getElementById('email').value;
  const password = document.getElementById('password').value;

  if (!email || !password) {
    alert('Please enter email and password');
    return;
  }

  try {
    await createUserWithEmailAndPassword(auth, email, password);
    alert('Signup successful! Please log in.');
  } catch (error) {
    alert('Signup failed: ' + error.message);
  }
}

async function handleLogin() {
  const email = document.getElementById('email').value;
  const password = document.getElementById('password').value;

  if (!email || !password) {
    alert('Please enter email and password');
    return;
  }

  try {
    await signInWithEmailAndPassword(auth, email, password);
    document.getElementById('login-section').style.display = 'none';
    document.getElementById('users-section').style.display = 'block';

    await fetchUsers();
  } catch (error) {
    alert('Login failed: ' + error.message);
  }
}

async function fetchUsers() {
  try {
    const users = await getUsers();
    const userList = document.getElementById('user-list');
    userList.innerHTML = users.map(user => `
      <div class="user-card">
        <p><strong>${user.name || 'N/A'}</strong></p>
        <p>Email: ${user.email || 'N/A'}</p>
        <p>Firebase UID: ${user.uid || 'Legacy record'}</p>
        <button class="edit-user-btn" data-user-id="${user.id}">Edit</button>
        <button class="delete-user-btn" data-user-id="${user.id}">Delete</button>
      </div>
    `).join('');
    userList.querySelectorAll('.edit-user-btn').forEach(button => {
      button.addEventListener('click', () => beginEditUser(Number(button.dataset.userId)));
    });
    userList.querySelectorAll('.delete-user-btn').forEach(button => {
      button.addEventListener('click', () => handleDeleteUser(Number(button.dataset.userId)));
    });
  } catch (error) {
    alert('Failed to fetch users: ' + error.message);
  }
}

function getUserFormData() {
  return {
    name: document.getElementById('user-name').value.trim(),
    email: document.getElementById('user-email').value.trim(),
    age: Number(document.getElementById('user-age').value) || null,
    location: document.getElementById('user-location').value.trim() || null,
    job_title: document.getElementById('user-job-title').value.trim() || null,
    created_at: document.getElementById('user-created-at').value.trim() || null
  };
}

function setUserForm(user = {}) {
  document.getElementById('user-id').value = user.id || '';
  document.getElementById('user-name').value = user.name || '';
  document.getElementById('user-email').value = user.email || '';
  document.getElementById('user-age').value = user.age || '';
  document.getElementById('user-location').value = user.location || '';
  document.getElementById('user-job-title').value = user.job_title || '';
  document.getElementById('user-created-at').value = user.created_at || '';
}

async function beginEditUser(userId) {
  try {
    setUserForm(await getUser(userId));
    document.getElementById('user-form-title').textContent = 'Edit user';
    document.getElementById('cancel-edit-btn').hidden = false;
  } catch (error) {
    alert('Failed to load user: ' + error.message);
  }
}

async function handleUserFormSubmit(event) {
  event.preventDefault();
  const userId = document.getElementById('user-id').value;

  try {
    if (userId) {
      await updateUser(Number(userId), getUserFormData());
    } else {
      await createUser(getUserFormData());
    }
    resetUserForm();
    await fetchUsers();
  } catch (error) {
    alert('Failed to save user: ' + error.message);
  }
}

async function handleDeleteUser(userId) {
  if (!confirm('Delete this user?')) return;

  try {
    await deleteUser(userId);
    await fetchUsers();
  } catch (error) {
    alert('Failed to delete user: ' + error.message);
  }
}

function resetUserForm() {
  document.getElementById('user-form').reset();
  document.getElementById('user-id').value = '';
  document.getElementById('user-form-title').textContent = 'Create user';
  document.getElementById('cancel-edit-btn').hidden = true;
}

function handleLogout() {
  signOut(auth)
    .then(() => {
      localStorage.removeItem('firebaseToken');
      document.getElementById('login-section').style.display = 'block';
      document.getElementById('users-section').style.display = 'none';
    })
    .catch((error) => {
      alert('Logout failed: ' + error.message);
    });
}

document.addEventListener('DOMContentLoaded', () => {
  const loginBtn = document.getElementById('login-btn');
  const signupBtn = document.getElementById('signup-btn');
  const logoutBtn = document.getElementById('logout-btn');
  const userForm = document.getElementById('user-form');
  const cancelEditBtn = document.getElementById('cancel-edit-btn');

  if (loginBtn) loginBtn.addEventListener('click', handleLogin);
  if (signupBtn) signupBtn.addEventListener('click', handleSignup);
  if (logoutBtn) logoutBtn.addEventListener('click', handleLogout);
  if (userForm) userForm.addEventListener('submit', handleUserFormSubmit);
  if (cancelEditBtn) cancelEditBtn.addEventListener('click', resetUserForm);
});

setInterval(async () => {
  if (auth.currentUser) {
    await auth.currentUser.getIdToken(true);
  }
}, 3600000);

export {
  checkBackendHealth,
  getUsers,
  getUser,
  createUser,
  updateUser,
  deleteUser
};
