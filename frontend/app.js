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
    const userCredential = await signInWithEmailAndPassword(auth, email, password);
    const token = await userCredential.user.getIdToken();
    localStorage.setItem('firebaseToken', token);

    document.getElementById('login-section').style.display = 'none';
    document.getElementById('users-section').style.display = 'block';

    fetchUsers();
  } catch (error) {
    alert('Login failed: ' + error.message);
  }
}

async function fetchUsers() {
  const token = localStorage.getItem('firebaseToken');

  try {
    const response = await fetch(`${BACKEND_URL}/api/users`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });

    if (!response.ok) throw new Error('Unauthorized');

    const users = await response.json();
    const userList = document.getElementById('user-list');
    userList.innerHTML = users.map(user => `
      <div class="user-card">
        <p><strong>${user.name || 'N/A'}</strong></p>
        <p>Email: ${user.email || 'N/A'}</p>
      </div>
    `).join('');
  } catch (error) {
    alert('Failed to fetch users: ' + error.message);
  }
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

  if (loginBtn) loginBtn.addEventListener('click', handleLogin);
  if (signupBtn) signupBtn.addEventListener('click', handleSignup);
  if (logoutBtn) logoutBtn.addEventListener('click', handleLogout);
});

setInterval(async () => {
  if (auth.currentUser) {
    const token = await auth.currentUser.getIdToken(true);
    localStorage.setItem('firebaseToken', token);
  }
}, 3600000);
