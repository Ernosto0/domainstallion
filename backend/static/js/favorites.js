// Auth state
let authToken = localStorage.getItem('authToken');
let currentUser = localStorage.getItem('username');

// Declare functions in the global scope
window.deleteFavorite = null;
window.removeFromWatchlist = null;
window.toggleAlert = null;

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
                                    data-favorite-id="${favorite.id}">
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
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM fully loaded");
    
    // Make sure functions are available in the global scope
    window.deleteFavorite = deleteFavorite;
    window.removeFromWatchlist = removeFromWatchlist;
    window.toggleAlert = toggleAlert;
    
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize score bars
    initializeScoreBars();
    
    // Update auth UI
    updateAuthUI();
    
    // Sort buttons functionality
    const sortButtons = document.querySelectorAll('.btn-group .btn[data-sort]');
    sortButtons.forEach(button => {
        button.addEventListener('click', function() {
            const sortBy = this.getAttribute('data-sort');
            const container = this.closest('.tab-pane').querySelector('.row');
            const items = Array.from(container.children);
            
            // Sort the items
            items.sort((a, b) => {
                let aValue = a.getAttribute(`data-${sortBy}`);
                let bValue = b.getAttribute(`data-${sortBy}`);
                
                // Handle numeric values
                if (sortBy === 'score') {
                    return parseInt(bValue) - parseInt(aValue); // Descending for scores
                }
                
                // Handle status values
                if (sortBy === 'status') {
                    // Sort available domains first
                    if (aValue === 'available' && bValue !== 'available') return -1;
                    if (aValue !== 'available' && bValue === 'available') return 1;
                    return aValue.localeCompare(bValue);
                }
                
                // Handle date values (assuming they're in a sortable format)
                if (sortBy === 'date') {
                    return new Date(bValue) - new Date(aValue); // Newest first
                }
                
                // Default string comparison
                return aValue.localeCompare(bValue);
            });
            
            // Reappend the sorted items
            items.forEach(item => container.appendChild(item));
            
            // Update active state on buttons
            this.closest('.btn-group').querySelectorAll('.btn').forEach(btn => {
                btn.classList.remove('active', 'btn-primary');
                btn.classList.add('btn-outline-secondary');
            });
            this.classList.remove('btn-outline-secondary');
            this.classList.add('active', 'btn-primary');
        });
    });

    // Add event listeners for favorite and watchlist buttons
    addButtonEventListeners();
});

// Initialize score bars based on data-score attributes
function initializeScoreBars() {
    document.querySelectorAll('.score-bar').forEach(bar => {
        const score = bar.getAttribute('data-score');
        if (score) {
            bar.style.width = score + '%';
        }
    });
}

// Add event listeners to buttons using data attributes
function addButtonEventListeners() {
    // Favorite delete buttons
    document.querySelectorAll('button[data-favorite-id]').forEach(button => {
        button.addEventListener('click', function() {
            const favoriteId = this.getAttribute('data-favorite-id');
            deleteFavorite(favoriteId);
        });
    });
    
    // Watchlist remove buttons
    document.querySelectorAll('button[data-watchlist-id]').forEach(button => {
        button.addEventListener('click', function() {
            const watchlistId = this.getAttribute('data-watchlist-id');
            removeFromWatchlist(watchlistId);
        });
    });
    
    // Alert toggle buttons
    document.querySelectorAll('button[data-domain-id]').forEach(button => {
        button.addEventListener('click', function() {
            const domainId = this.getAttribute('data-domain-id');
            toggleAlert(domainId, this);
        });
    });
}

// Delete favorite function
function deleteFavorite(favoriteId) {
    if (!confirm('Are you sure you want to remove this domain from your favorites?')) {
        return;
    }
    
    fetch(`/favorites/${favoriteId}`, {
        method: 'DELETE',
        headers: {
            'Authorization': `Bearer ${authToken}`
        }
    })
    .then(response => {
        if (response.ok) {
            // Remove the card from the DOM
            const card = document.querySelector(`[data-favorite-id="${favoriteId}"]`);
            if (card) {
                card.closest('.col-md-6').remove();
            } else {
                // If we can't find by data attribute, try to find the button and navigate up
                const button = document.querySelector(`button[onclick*="deleteFavorite(${favoriteId})"]`);
                if (button) {
                    button.closest('.col-md-6').remove();
                }
            }
            
            // Update the count
            const count = document.getElementById('favoritesCount');
            if (count) {
                count.textContent = parseInt(count.textContent) - 1;
            }
            
            showToast('Domain removed from favorites', 'success');
        } else {
            showToast('Failed to remove domain', 'error');
        }
    })
    .catch(error => {
        console.error('Error removing favorite:', error);
        showToast('An error occurred', 'error');
    });
}

// Remove from watchlist function
function removeFromWatchlist(watchlistId) {
    if (!confirm('Are you sure you want to remove this domain from your watchlist?')) {
        return;
    }
    
    fetch(`/watchlist/${watchlistId}`, {
        method: 'DELETE',
        headers: {
            'Authorization': `Bearer ${authToken}`
        }
    })
    .then(response => {
        if (response.ok) {
            // Remove the card from the DOM
            const card = document.querySelector(`[data-watchlist-id="${watchlistId}"]`);
            if (card) {
                card.closest('.col-md-6').remove();
            } else {
                // If we can't find by data attribute, try to find the button and navigate up
                const button = document.querySelector(`button[onclick*="removeFromWatchlist(${watchlistId})"]`);
                if (button) {
                    button.closest('.col-md-6').remove();
                }
            }
            
            // Update the count
            const count = document.getElementById('watchlistCount');
            if (count) {
                count.textContent = parseInt(count.textContent) - 1;
            }
            
            showToast('Domain removed from watchlist', 'success');
        } else {
            showToast('Failed to remove domain', 'error');
        }
    })
    .catch(error => {
        console.error('Error removing from watchlist:', error);
        showToast('An error occurred', 'error');
    });
}

// Make toggleAlert available in the global scope
function toggleAlert(watchlistId, button) {
    console.log("toggleAlert called with ID:", watchlistId);
    const currentState = button.getAttribute('data-notify') === 'true';
    const newState = !currentState;
    
    fetch(`/watchlist/${watchlistId}/notify`, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
            notify_when_available: newState
        })
    })
    .then(response => {
        if (response.ok) {
            // Update button state
            button.setAttribute('data-notify', newState.toString());
            button.classList.toggle('active', newState);
            
            // Update icon
            const icon = button.querySelector('i');
            if (icon) {
                if (newState) {
                    icon.classList.remove('bi-bell-slash');
                    icon.classList.add('bi-bell');
                    button.setAttribute('title', 'Notifications enabled');
                } else {
                    icon.classList.remove('bi-bell');
                    icon.classList.add('bi-bell-slash');
                    button.setAttribute('title', 'Get notified when available');
                }
            }
            
            // Update tooltip
            const tooltip = bootstrap.Tooltip.getInstance(button);
            if (tooltip) {
                tooltip.dispose();
                new bootstrap.Tooltip(button);
            }
            
            showToast(newState ? 'Notifications enabled' : 'Notifications disabled', 'success');
        } else {
            response.json().then(errorData => {
                showToast(errorData.detail || 'Failed to update notification settings', 'error');
            }).catch(() => {
                showToast('Failed to update notification settings', 'error');
            });
        }
    })
    .catch(error => {
        console.error('Error toggling alert:', error);
        showToast('Failed to update notification settings', 'error');
    });
}

// Toast notification function
function showToast(message, type = 'info') {
    // Check if toast container exists, create if not
    let toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }
    
    // Create toast element
    const toastId = 'toast-' + Date.now();
    const toastHtml = `
        <div id="${toastId}" class="toast align-items-center text-white bg-${type === 'success' ? 'success' : type === 'error' ? 'danger' : 'primary'}" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;
    
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    
    // Initialize and show the toast
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, { delay: 5000 });
    toast.show();
    
    // Remove toast after it's hidden
    toastElement.addEventListener('hidden.bs.toast', function() {
        toastElement.remove();
    });
} 