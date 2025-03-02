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
                console.log('Raw API Response:', brands);
                
                // Clear previous results
                resultsDiv.innerHTML = '';
                
                // Process each brand
                brands.forEach((brand, index) => {
                    console.log(`Processing brand ${index + 1}:`, brand);
                    
                    // Create brand card container
                    const brandCardContainer = document.createElement('div');
                    brandCardContainer.className = 'col-md-6 col-lg-4 mb-4';
                    
                    // Create brand card header
                    const brandCard = `
                        <div class="brand-card">
                            <div class="d-flex justify-content-between align-items-start mb-3">
                                <h3 class="h4 mb-0">${brand.name}</h3>
                                <span class="badge bg-secondary">#${index + 1}</span>
                            </div>
                            <div class="domains-container"></div>
                        </div>
                    `;
                    brandCardContainer.innerHTML = brandCard;
                    
                    // Get domain entries
                    const allDomainEntries = Object.entries(brand.domains || {});
                    console.log('Domain entries:', allDomainEntries);
                    
                    // Get the domains container
                    const domainsContainer = brandCardContainer.querySelector('.domains-container');
                    
                    // Process first 3 domains
                    allDomainEntries.slice(0, 3).forEach(([ext, info]) => {
                        const domainCard = createDomainCard(brand.name, ext, info);
                        domainsContainer.appendChild(domainCard);
                    });
                    
                    // Create container for remaining domains
                    if (allDomainEntries.length > 3) {
                        const remainingContainer = document.createElement('div');
                        remainingContainer.className = 'remaining-domains';
                        remainingContainer.style.display = 'none';
                        
                        // Process remaining domains
                        allDomainEntries.slice(3).forEach(([ext, info]) => {
                            const domainCard = createDomainCard(brand.name, ext, info);
                            remainingContainer.appendChild(domainCard);
                        });
                        
                        domainsContainer.appendChild(remainingContainer);
                        
                        // Add toggle button
                        const toggleButton = document.createElement('button');
                        toggleButton.className = 'btn btn-sm btn-outline-secondary w-100 mt-2 toggle-domains';
                        toggleButton.innerHTML = `
                            <span class="more-text">Show More Extensions</span>
                            <span class="less-text" style="display: none;">Show Less</span>
                        `;
                        
                        toggleButton.addEventListener('click', function() {
                            const remainingDomains = this.previousElementSibling;
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
                        
                        domainsContainer.appendChild(toggleButton);
                    }
                    
                    resultsDiv.appendChild(brandCardContainer);
                });
                
                // Update score circles
                document.querySelectorAll('.score-circle').forEach(circle => {
                    const scoreValue = circle.querySelector('.score-value').textContent;
                    circle.style.setProperty('--score-value', scoreValue);
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
            
            const authToken = localStorage.getItem('authToken');
            
            if (!authToken) {
                const loginModal = new bootstrap.Modal(document.getElementById('loginModal'));
                loginModal.show();
                return;
            }

            try {
                const response = await fetch('/favorites', {
                    headers: {
                        'Authorization': `Bearer ${authToken}`
                    }
                });

                if (response.ok) {
                    // Replace the current page content with the favorites page
                    document.open();
                    document.write(await response.text());
                    document.close();
                    // Update the URL
                    window.history.pushState({}, '', '/favorites');
                } else if (response.status === 401) {
                    // Clear invalid token
                    localStorage.removeItem('authToken');
                    localStorage.removeItem('username');
                    // Show login modal
                    const loginModal = new bootstrap.Modal(document.getElementById('loginModal'));
                    loginModal.show();
                } else {
                    console.error('Error loading favorites:', await response.text());
                }
            } catch (error) {
                console.error('Error:', error);
            }
        });
    }

    // Intercept all fetch requests to add authorization header
    const originalFetch = window.fetch;
    window.fetch = function(url, options = {}) {
        const authToken = localStorage.getItem('authToken');
        if (authToken) {
            options.headers = {
                ...options.headers,
                'Authorization': `Bearer ${authToken}`
            };
        }
        return originalFetch(url, options);
    };

    // Add this before any navigation that requires authentication
    function addAuthHeadersToXHR() {
        const authToken = localStorage.getItem('authToken');
        if (authToken) {
            const xhr = new XMLHttpRequest();
            const open = xhr.open;
            xhr.open = function() {
                const result = open.apply(this, arguments);
                this.setRequestHeader('Authorization', `Bearer ${authToken}`);
                return result;
            };
        }
    }

    // Call this when the page loads
    addAuthHeadersToXHR();
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
    event.preventDefault();
    
    // Get the score data from the domain card
    const domainCard = event.target.closest('.domain-card');
    const totalScore = parseInt(domainCard.querySelector('.score-value').textContent);
    const scoreDetails = domainCard.querySelectorAll('.score-item');
    
    // Extract individual scores
    const scores = {
        length_score: 0,
        dictionary_score: 0,
        pronounceability_score: 0,
        repetition_score: 0,
        tld_score: 0
    };
    
    scoreDetails.forEach(item => {
        const scoreType = item.querySelector('small').textContent.toLowerCase();
        const scoreValue = parseInt(item.querySelector('.score-bar').style.width);
        switch(scoreType) {
            case 'length':
                scores.length_score = scoreValue;
                break;
            case 'dictionary':
                scores.dictionary_score = scoreValue;
                break;
            case 'pronounceability':
                scores.pronounceability_score = scoreValue;
                break;
            case 'repetition':
                scores.repetition_score = scoreValue;
                break;
            case 'tld':
                scores.tld_score = scoreValue;
                break;
        }
    });

    try {
        const response = await fetch('/favorites', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({
                brand_name: brandName,
                domain_name: domainName,
                domain_extension: extension,
                price: price,
                total_score: totalScore,
                ...scores
            })
        });

        if (response.ok) {
            showToast('Added to favorites!');
            const button = event.target.closest('.favorite-btn');
            button.classList.add('btn-success');
        } else {
            const data = await response.json();
            showToast(data.detail || 'Failed to add to favorites', 'error');
        }
    } catch (error) {
        console.error('Error adding to favorites:', error);
        showToast('Failed to add to favorites', 'error');
    }
}

function createDomainCard(brandName, ext, info) {
    console.log(`Creating domain card for ${brandName}.${ext}:`, info);
    
    const domainCard = document.createElement('div');
    domainCard.className = 'domain-card mb-2';
    
    const statusClass = info.available ? 'domain-available' : 'domain-unavailable';
    const statusText = info.available ? `Available - ${info.price}` : 'Taken';
    
    // Ensure we have a valid score object
    const score = info.score || {
        total_score: 0,
        details: {
            length: { score: 0, description: "Score unavailable" },
            dictionary: { score: 0, description: "Score unavailable" },
            pronounceability: { score: 0, description: "Score unavailable" },
            repetition: { score: 0, description: "Score unavailable" },
            tld: { score: 0, description: "Score unavailable" }
        }
    };
    
    console.log('Score object:', score);
    
    domainCard.innerHTML = `
        <div class="d-flex justify-content-between align-items-center">
            <div>
                <span class="domain-name h5 mb-0">${brandName}.${ext}</span>
            </div>
            <span class="domain-badge ${statusClass}">${statusText}</span>
        </div>
        <div class="domain-score mt-3">
            <div class="score-circle-container d-flex justify-content-center align-items-center mb-3">
                <div class="score-circle" style="--score-value: ${score.total_score}">
                    <div class="score-circle-inner">
                        <span class="score-value">${score.total_score}</span>
                    </div>
                </div>
            </div>
            <div class="score-details">
                ${Object.entries(score.details).map(([key, detail]) => `
                    <div class="score-item d-flex align-items-center mb-1">
                        <div class="score-bar-container flex-grow-1">
                            <div class="score-bar" style="width: ${detail.score}%"></div>
                        </div>
                        <small class="ms-2">${key.charAt(0).toUpperCase() + key.slice(1)}</small>
                        <div class="score-tooltip">${detail.description}</div>
                    </div>
                `).join('')}
            </div>
        </div>
        ${info.available ? `
            <div class="mt-2 d-flex gap-2">
                <a href="https://domains.google.com/registrar/search?searchTerm=${brandName}.${ext}" 
                   target="_blank" 
                   class="btn btn-sm btn-outline-primary flex-grow-1">
                    Register Domain
                </a>
                <button class="btn btn-sm btn-outline-success favorite-btn"
                        onclick="addToFavorites(event, '${brandName}', '${brandName}.${ext}', '${ext}', '${info.price}')">
                    <span class="heart-icon">♥</span>
                </button>
            </div>
        ` : ''}
    `;
    
    return domainCard;
}

// Initialize auth UI on page load
updateAuthUI(); 