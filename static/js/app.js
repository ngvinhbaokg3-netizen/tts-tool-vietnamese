javascript
// Global configuration
const API_BASE = '/api';

// Axios defaults
axios.defaults.headers.common['Content-Type'] = 'application/json';

// Check if user is logged in
const token = localStorage.getItem('token');
if (token) {
    axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
}

// Utility functions
function showAlert(message, type = 'success') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3`;
    alertDiv.style.zIndex = '9999';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(alertDiv);
    
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

function showLoading() {
    const loadingDiv = document.createElement('div');
    loadingDiv.id = 'globalLoading';
    loadingDiv.className = 'position-fixed top-0 start-0 w-100 h-100 d-flex justify-content-center align-items-center';
    loadingDiv.style.backgroundColor = 'rgba(0,0,0,0.7)';
    loadingDiv.style.zIndex = '9999';
    loadingDiv.innerHTML = `
        <div class="text-center">
            <div class="spinner-border text-primary" style="width: 3rem; height: 3rem;"></div>
            <p class="mt-3 text-white">Đang xử lý...</p>
        </div>
    `;
    document.body.appendChild(loadingDiv);
}

function hideLoading() {
    const loadingDiv = document.getElementById('globalLoading');
    if (loadingDiv) {
        loadingDiv.remove();
    }
}

// API functions
async function apiCall(method, endpoint, data = null) {
    try {
        const response = await axios({
            method: method,
            url: `${API_BASE}${endpoint}`,
            data: data
        });
        return response.data;
    } catch (error) {
        if (error.response) {
            throw new Error(error.response.data.error || 'API Error');
        }
        throw error;
    }
}

// Auth functions
function isLoggedIn() {
    return !!localStorage.getItem('token');
}

function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = '/';
}

// Format functions
function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString('vi-VN', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    // Check protected pages
    const protectedPages = ['/dashboard', '/admin'];
    const currentPath = window.location.pathname;
    
    if (protectedPages.includes(currentPath) && !isLoggedIn()) {
        window.location.href = '/';
    }
    
    // Setup AJAX error handling
    axios.interceptors.response.use(
        response => response,
        error => {
            if (error.response && error.response.status === 401) {
                // Token expired or invalid
                logout();
            }
            return Promise.reject(error);
        }
    );
    
    console.log('TTS Tool Vietnamese initialized');
});