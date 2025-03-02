// Wait for the DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Common elements
    const form = document.getElementById('brandForm');
    const loading = document.getElementById('loading');
    const resultsContainer = document.querySelector('.results-container');
    const resultsDiv = document.getElementById('results');
    const favoritesContainer = document.querySelector('.favorites-container');
    const searchContainer = document.querySelector('.search-container');
    const viewFavoritesBtn = document.getElementById('viewFavorites');

    if (form) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            // Show loading spinner
            loading.style.display = 'block';
            resultsContainer.style.display = 'none';
            
            const keywords = document.getElementById('keywordInput').value;
            const numSuggestions = 20;
            
            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ 
                        keywords,
                        num_suggestions: numSuggestions
                    }),
                });
                
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                
                const brands = await response.json();
                console.log('Received brands:', brands);
                
                // Clear previous results
                resultsDiv.innerHTML = '';
                
                // Display results with a counter
                brands.forEach((brand, index) => {
                    // Create domain status cards for each extension
                    const allDomainEntries = Object.entries(brand.domains);
                    const initialDomains = allDomainEntries.slice(0, 3); // Show first 3 domains initially
                    const remainingDomains = allDomainEntries.slice(3);

                    const createDomainCard = ([ext, info], brandName) => {
                        const statusClass = info.available ? 'domain-available' : 'domain-unavailable';
                        const statusText = info.available ? `Available - ${info.price}` : 'Taken';
                        
                        return `
                            <div class="domain-card mb-2">
                                <div class="d-flex justify-content-between align-items-center">
                                    <span class="domain-name">.${ext}</span>
                                    <span class="domain-badge ${statusClass}">${statusText}</span>
                                </div>
                                ${info.available ? `
                                    <div class="mt-2 d-flex gap-2">
                                        <a href="https://domains.google.com/registrar/search?searchTerm=${info.domain}" 
                                           target="_blank" 
                                           class="btn btn-sm btn-outline-primary flex-grow-1">
                                            Register Domain
                                        </a>
                                        <button class="btn btn-sm btn-outline-success favorite-btn"
                                                onclick="addToFavorites(event, '${brandName}', '${info.domain}', '${ext}', '${info.price}')">
                                            <span class="heart-icon">♥</span>
                                        </button>
                                    </div>
                                ` : ''}
                            </div>
                        `;
                    };

                    const initialDomainCards = initialDomains.map(entry => createDomainCard(entry, brand.name)).join('');
                    const remainingDomainCards = remainingDomains.map(entry => createDomainCard(entry, brand.name)).join('');
                    
                    const brandCard = `
                        <div class="col-md-6 col-lg-4 mb-4">
                            <div class="brand-card">
                                <div class="d-flex justify-content-between align-items-start mb-3">
                                    <h3 class="h4 mb-0">${brand.name}</h3>
                                    <span class="badge bg-secondary">#${index + 1}</span>
                                </div>
                                <div class="domains-container">
                                    ${initialDomainCards}
                                    <div class="remaining-domains" style="display: none;">
                                        ${remainingDomainCards}
                                    </div>
                                    ${remainingDomains.length > 0 ? `
                                        <button class="btn btn-sm btn-outline-secondary w-100 mt-2 toggle-domains">
                                            <span class="more-text">Show More Extensions</span>
                                            <span class="less-text" style="display: none;">Show Less</span>
                                        </button>
                                    ` : ''}
                                </div>
                            </div>
                        </div>
                    `;
                    
                    resultsDiv.innerHTML += brandCard;
                });
                
                // Add event listeners for toggle buttons
                document.querySelectorAll('.toggle-domains').forEach(button => {
                    button.addEventListener('click', function() {
                        const container = this.closest('.domains-container');
                        const remainingDomains = container.querySelector('.remaining-domains');
                        const moreText = this.querySelector('.more-text');
                        const lessText = this.querySelector('.less-text');
                        
                        if (remainingDomains.style.display === 'none') {
                            remainingDomains.style.display = 'block';
                            moreText.style.display = 'none';
                            lessText.style.display = 'inline';
                        } else {
                            remainingDomains.style.display = 'none';
                            moreText.style.display = 'inline';
                            lessText.style.display = 'none';
                        }
                    });
                });
                
                // Show results
                resultsContainer.style.display = 'block';
                
                // Scroll to results
                resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
                
            } catch (error) {
                console.error('Error:', error);
                resultsDiv.innerHTML = `
                    <div class="col-12 text-center">
                        <div class="alert alert-danger">
                            An error occurred while generating brand names. Please try again.
                        </div>
                    </div>
                `;
                resultsContainer.style.display = 'block';
            } finally {
                loading.style.display = 'none';
            }
        });
    }

    // Add smooth scrolling to all links with hash
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        if (anchor.getAttribute('href') !== '#') {  // Skip empty hash
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth'
                    });
                }
            });
        }
    });

    // Initialize tooltips if Bootstrap is present
    if (typeof bootstrap !== 'undefined') {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }

    // Handle favorites view
    if (viewFavoritesBtn) {
        viewFavoritesBtn.addEventListener('click', async function(e) {
            e.preventDefault();
            
            if (!authToken) {
                const loginModal = new bootstrap.Modal(document.getElementById('loginModal'));
                loginModal.show();
                return;
            }

            try {
                console.log('Fetching favorites with token:', authToken);
                const response = await fetch('/favorites', {
                    method: 'GET',
                    headers: {
                        'Authorization': `Bearer ${authToken}`,
                        'Accept': 'application/json'
                    }
                });

                console.log('Response status:', response.status);
                const responseText = await response.text();
                console.log('Response text:', responseText);

                if (!response.ok) {
                    if (response.status === 401) {
                        // Token expired or invalid, clear auth and show login
                        localStorage.removeItem('authToken');
                        localStorage.removeItem('username');
                        authToken = null;
                        currentUser = null;
                        updateAuthUI();
                        const loginModal = new bootstrap.Modal(document.getElementById('loginModal'));
                        loginModal.show();
                        return;
                    }
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const favorites = JSON.parse(responseText);
                const favoritesDiv = document.getElementById('favorites');
                favoritesDiv.innerHTML = '';

                if (favorites.length === 0) {
                    favoritesDiv.innerHTML = `
                        <div class="col-12">
                            <div class="alert alert-info">
                                You haven't saved any favorites yet.
                            </div>
                        </div>
                    `;
                } else {
                    favorites.forEach(favorite => {
                        const favoriteCard = `
                            <div class="col-md-6 col-lg-4 mb-4">
                                <div class="brand-card">
                                    <div class="d-flex justify-content-between align-items-start mb-3">
                                        <h3 class="h4 mb-0">${favorite.brand_name}</h3>
                                        <button class="btn btn-sm btn-outline-danger" 
                                                onclick="removeFavorite(${favorite.id})">
                                            Remove
                                        </button>
                                    </div>
                                    <div class="domain-card mb-2">
                                        <div class="d-flex justify-content-between align-items-center">
                                            <span class="domain-name">${favorite.domain_name}${favorite.domain_extension}</span>
                                            <span class="domain-badge domain-available">Price: ${favorite.price}</span>
                                        </div>
                                        <div class="mt-2">
                                            <a href="https://domains.google.com/registrar/search?searchTerm=${favorite.domain_name}${favorite.domain_extension}" 
                                               target="_blank" 
                                               class="btn btn-sm btn-outline-primary w-100">
                                                Register Domain
                                            </a>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `;
                        favoritesDiv.innerHTML += favoriteCard;
                    });
                }

                // Show favorites, hide other containers
                favoritesContainer.classList.remove('d-none');
                resultsContainer.style.display = 'none';
                searchContainer.classList.add('d-none');
            } catch (error) {
                console.error('Error fetching favorites:', error);
                const favoritesDiv = document.getElementById('favorites');
                favoritesDiv.innerHTML = `
                    <div class="col-12">
                        <div class="alert alert-danger">
                            Failed to load favorites. Please try logging in again.
                            <br>
                            Error: ${error.message}
                        </div>
                    </div>
                `;
                favoritesContainer.classList.remove('d-none');
                resultsContainer.style.display = 'none';
                searchContainer.classList.add('d-none');
            }
        });
    }
});

// Auth state
let authToken = localStorage.getItem('authToken');
let currentUser = localStorage.getItem('username');

// Update UI based on auth state
function updateAuthUI() {
    const loginRegisterNav = document.getElementById('loginRegisterNav');
    const userNav = document.getElementById('userNav');
    const username = document.getElementById('username');
    
    if (authToken && currentUser) {
        loginRegisterNav.classList.add('d-none');
        userNav.classList.remove('d-none');
        username.textContent = currentUser;
    } else {
        loginRegisterNav.classList.remove('d-none');
        userNav.classList.add('d-none');
        username.textContent = '';
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
    updateAuthUI();
});

// Remove favorite
async function removeFavorite(favoriteId) {
    try {
        const response = await fetch(`/favorites/${favoriteId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${authToken}`,
            },
        });
        
        if (response.ok) {
            // Refresh favorites view
            document.getElementById('viewFavorites').click();
        }
    } catch (error) {
        console.error('Error removing favorite:', error);
    }
}

// Add favorite
async function addToFavorites(event, brandName, domainName, extension, price) {
    if (!authToken) {
        bootstrap.Modal.getInstance(document.getElementById('loginModal')).show();
        return;
    }
    
    try {
        const response = await fetch('/favorites', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                brand_name: brandName,
                domain_name: domainName,
                domain_extension: extension,
                price: price,
            }),
        });
        
        if (response.ok) {
            const btn = event.target.closest('.favorite-btn');
            btn.classList.remove('btn-outline-success');
            btn.classList.add('btn-success');
            btn.disabled = true;
            btn.innerHTML = '<span class="heart-icon">♥</span> Saved';
            
            // Show toast notification
            const toast = document.createElement('div');
            toast.className = 'toast-notification';
            toast.textContent = 'Added to favorites!';
            document.body.appendChild(toast);
            
            // Remove toast after animation
            setTimeout(() => {
                toast.remove();
            }, 3000);
        }
    } catch (error) {
        console.error('Error adding to favorites:', error);
        alert('Failed to add to favorites. Please try again.');
    }
}

// Initialize auth UI on page load
updateAuthUI(); 