// Auth state
let authToken = localStorage.getItem('authToken');
let currentUser = localStorage.getItem('username');

// Update UI based on auth state
function updateAuthUI() {
    const loginRegisterNav = document.getElementById('loginRegisterNav');
    const userNav = document.getElementById('userNav');
    const username = document.getElementById('username');
    const profileUsername = document.getElementById('profileUsername');
    
    if (authToken && currentUser) {
        loginRegisterNav.classList.add('d-none');
        userNav.classList.remove('d-none');
        username.textContent = currentUser;
        profileUsername.textContent = currentUser;
        loadUserProfile();
        loadFavorites();
    } else {
        loginRegisterNav.classList.remove('d-none');
        userNav.classList.add('d-none');
        username.textContent = '';
        window.location.href = '/'; // Redirect to home if not logged in
    }
}

// Load user profile
async function loadUserProfile() {
    try {
        const response = await fetch('/user/profile', {
            headers: {
                'Authorization': `Bearer ${authToken}`,
            },
        });
        
        if (response.ok) {
            const profile = await response.json();
            document.getElementById('profileEmail').textContent = profile.email;
        }
    } catch (error) {
        console.error('Error loading profile:', error);
    }
}

// Load favorites
let favorites = [];
async function loadFavorites() {
    try {
        const response = await fetch('/favorites', {
            headers: {
                'Authorization': `Bearer ${authToken}`,
            },
        });
        
        if (response.ok) {
            favorites = await response.json();
            document.getElementById('savedDomainsCount').textContent = favorites.length;
            displayFavorites(favorites);
        }
    } catch (error) {
        console.error('Error loading favorites:', error);
    }
}

// Display favorites
function displayFavorites(favoritesToShow) {
    const favoritesList = document.getElementById('favoritesList');
    favoritesList.innerHTML = '';
    
    if (favoritesToShow.length === 0) {
        favoritesList.innerHTML = `
            <div class="col-12 text-center py-5">
                <h4 class="text-muted">No favorites yet</h4>
                <p class="mb-0">Start adding domains to your favorites list!</p>
                <a href="/" class="btn btn-primary mt-3">Search Domains</a>
            </div>
        `;
        return;
    }
    
    favoritesToShow.forEach(favorite => {
        const favoriteCard = `
            <div class="col-md-6 col-xl-4 mb-4">
                <div class="card h-100">
                    <div class="card-body">
                        <h5 class="card-title text-truncate" title="${favorite.brand_name}">${favorite.brand_name}</h5>
                        <p class="card-text mb-2">
                            <span class="domain-name">${favorite.domain_name}</span>
                            <span class="badge bg-success ms-2">${favorite.price}</span>
                        </p>
                        <div class="d-flex gap-2">
                            <a href="https://domains.google.com/registrar/search?searchTerm=${favorite.domain_name}" 
                               target="_blank" 
                               class="btn btn-sm btn-outline-primary flex-grow-1">
                                Register Domain
                            </a>
                            <button class="btn btn-sm btn-outline-danger" 
                                    onclick="removeFavorite(${favorite.id})">
                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-trash" viewBox="0 0 16 16">
                                    <path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0z"/>
                                    <path d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4zM2.5 3h11V2h-11z"/>
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        favoritesList.innerHTML += favoriteCard;
    });
}

// Remove favorite
async function removeFavorite(favoriteId) {
    if (!confirm('Are you sure you want to remove this domain from your favorites?')) {
        return;
    }
    
    try {
        const response = await fetch(`/favorites/${favoriteId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${authToken}`,
            },
        });
        
        if (response.ok) {
            // Remove from local array and update display
            favorites = favorites.filter(f => f.id !== favoriteId);
            document.getElementById('savedDomainsCount').textContent = favorites.length;
            displayFavorites(favorites);
            
            // Show toast notification
            const toast = document.createElement('div');
            toast.className = 'toast-notification';
            toast.textContent = 'Removed from favorites';
            document.body.appendChild(toast);
            
            // Remove toast after animation
            setTimeout(() => {
                toast.remove();
            }, 3000);
        }
    } catch (error) {
        console.error('Error removing favorite:', error);
        alert('Failed to remove favorite. Please try again.');
    }
}

// Handle login
document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;
    const errorDiv = document.getElementById('loginError');
    
    try {
        const response = await fetch('/token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`,
        });
        
        const data = await response.json();
        
        if (response.ok) {
            localStorage.setItem('authToken', data.access_token);
            localStorage.setItem('username', username);
            currentUser = username;
            authToken = data.access_token;
            updateAuthUI();
            bootstrap.Modal.getInstance(document.getElementById('loginModal')).hide();
        } else {
            errorDiv.textContent = data.detail;
            errorDiv.classList.remove('d-none');
        }
    } catch (error) {
        errorDiv.textContent = 'An error occurred. Please try again.';
        errorDiv.classList.remove('d-none');
    }
});

// Handle register
document.getElementById('registerForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('registerUsername').value;
    const email = document.getElementById('registerEmail').value;
    const password = document.getElementById('registerPassword').value;
    const errorDiv = document.getElementById('registerError');
    
    try {
        const response = await fetch('/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, email, password }),
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Auto-login after registration
            const loginResponse = await fetch('/token', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`,
            });
            
            const loginData = await loginResponse.json();
            
            if (loginResponse.ok) {
                localStorage.setItem('authToken', loginData.access_token);
                localStorage.setItem('username', username);
                currentUser = username;
                authToken = loginData.access_token;
                updateAuthUI();
                bootstrap.Modal.getInstance(document.getElementById('registerModal')).hide();
            }
        } else {
            errorDiv.textContent = data.detail;
            errorDiv.classList.remove('d-none');
        }
    } catch (error) {
        errorDiv.textContent = 'An error occurred. Please try again.';
        errorDiv.classList.remove('d-none');
    }
});

// Handle logout
document.getElementById('logout').addEventListener('click', (e) => {
    e.preventDefault();
    localStorage.removeItem('authToken');
    localStorage.removeItem('username');
    authToken = null;
    currentUser = null;
    window.location.href = '/';
});

// Handle sorting
document.getElementById('sortByName').addEventListener('click', () => {
    const sorted = [...favorites].sort((a, b) => a.brand_name.localeCompare(b.brand_name));
    displayFavorites(sorted);
});

document.getElementById('sortByPrice').addEventListener('click', () => {
    const sorted = [...favorites].sort((a, b) => {
        const priceA = parseFloat(a.price.replace(/[^0-9.-]+/g, ''));
        const priceB = parseFloat(b.price.replace(/[^0-9.-]+/g, ''));
        return priceA - priceB;
    });
    displayFavorites(sorted);
});

// Initialize auth UI on page load
updateAuthUI(); 