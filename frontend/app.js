// Replace with YOUR Firebase config from Firebase Console
const firebaseConfig = {
    apiKey: "YOUR_API_KEY",
    authDomain: "YOUR_PROJECT.firebaseapp.com",
    projectId: "YOUR_PROJECT_ID",
    storageBucket: "YOUR_BUCKET.appspot.com",
    messagingSenderId: "YOUR_SENDER_ID",
    appId: "YOUR_APP_ID"
};

const app = firebase.initializeApp(firebaseConfig);
const auth = firebase.getAuth(app);

// Set your backend URL here
const BACKEND_URL = 'http://localhost:5000'; // Change for production

async function handleSignup() {
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    
    if (!email || !password) {
        alert('Please enter email and password');
        return;
    }
    
    try {
        await firebase.auth().createUserWithEmailAndPassword(email, password);
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
        await firebase.auth().signInWithEmailAndPassword(email, password);
        const token = await auth.currentUser.getIdToken();
        localStorage.setItem('firebaseToken', token);
        
        document.getElementById('login-section').style.display = 'none';
        document.getElementById('users-section').style.display = 'block';
        
        fetchUsers();
    } catch (error) {
        alert('Login failed: ' + error.message);
    }
}

function handleLogout() {
    firebase.auth().signOut();
    localStorage.removeItem('firebaseToken');
    document.getElementById('login-section').style.display = 'block';
    document.getElementById('users-section').style.display = 'none';
}

async function fetchUsers() {
    const token = localStorage.getItem('firebaseToken');
    
    try {
        const response = await fetch(`${BACKEND_URL}/api/users`, {
            headers: {
                'Authorization': `Bearer ${token}`
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

// Auto-refresh token every hour
setInterval(async () => {
    if (auth.currentUser) {
        const token = await auth.currentUser.getIdToken(true);
        localStorage.setItem('firebaseToken', token);
    }
}, 3600000);
