// Auth state
let authToken = localStorage.getItem('authToken');
let currentUser = localStorage.getItem('username');

// Add to watchlist function
window.addToWatchlist = async function(event, brandName, extension) {
    event.preventDefault();
    console.log('Adding to watchlist - Raw inputs:', { brandName, extension });
    
    // Check authentication first
    const authToken = localStorage.getItem('authToken');
    if (!authToken) {
        console.log('No auth token found, showing login modal');
        const loginModal = new bootstrap.Modal(document.getElementById('loginModal'));
        loginModal.show();
        return;
    }
    
    try {
        // Type checking and validation
        if (!brandName || typeof brandName !== 'string') {
            console.error('Invalid brand name:', brandName);
            showToast('Invalid domain name format', 'error');
            return;
        }
        
        if (!extension || typeof extension !== 'string') {
            console.error('Invalid extension:', extension);
            showToast('Invalid extension format', 'error');
            return;
        }

        // Clean the domain name by removing the extension if it's present
        const cleanDomainName = brandName.includes(`.${extension}`) 
            ? brandName.split(`.${extension}`)[0] 
            : brandName;
            
        console.log('Cleaned domain name:', cleanDomainName);
        
        const payload = {
            domain_name: cleanDomainName,
            domain_extension: extension
        };
        console.log('Request payload:', payload);
        
        const response = await fetch('/watchlist', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify(payload)
        });

        console.log('Response status:', response.status);
        
        if (response.status === 401) {
            console.log('Token expired or invalid, showing login modal');
            localStorage.removeItem('authToken');
            localStorage.removeItem('username');
            const loginModal = new bootstrap.Modal(document.getElementById('loginModal'));
            loginModal.show();
            return;
        }
        
        if (response.status === 422) {
            const errorData = await response.json();
            console.error('Validation error:', errorData);
            showToast(errorData.detail || 'Invalid request format', 'error');
            return;
        }

        if (response.ok) {
            showToast('Domain added to watchlist successfully', 'success');
            // Update watchlist count if we're on the favorites page
            const watchlistCount = document.getElementById('watchlistCount');
            if (watchlistCount) {
                const currentCount = parseInt(watchlistCount.textContent);
                watchlistCount.textContent = currentCount + 1;
            }
            
            // Update button appearance
            const button = event.target.closest('.watchlist-btn');
            if (button) {
                button.classList.add('btn-info');
                button.disabled = true;
                button.innerHTML = '<i class="bi bi-eye-fill"></i>';
            }
        } else {
            const errorData = await response.json();
            console.error('Server error:', errorData);
            showToast(errorData.detail || 'Failed to add domain to watchlist', 'error');
        }
    } catch (error) {
        console.error('Error adding to watchlist:', error);
        showToast('Failed to add domain to watchlist', 'error');
    }
};

// Intercept all fetch requests to add authorization header
const originalFetch = window.fetch;
window.fetch = function(url, options = {}) {
    options = options || {};
    options.headers = options.headers || {};
    const authToken = localStorage.getItem('authToken');
    if (authToken) {
        options.headers['Authorization'] = `Bearer ${authToken}`;
    }
    return originalFetch(url, options);
};

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
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <div class="d-flex align-items-center gap-3">
                                    <h3 class="h4 mb-0">${brand.name}.com</h3>
                                    <div class="score-circle-main" style="--score-value: ${brand.domains.com?.score?.total_score || 0}">
                                        <div class="score-circle-inner">
                                            <span class="score-value">${brand.domains.com?.score?.total_score || 0}</span>
                                        </div>
                                    </div>
                                </div>
                                <span class="badge bg-secondary">#${index + 1}</span>
                            </div>
                            ${brand.domains.com ? `
                            <div class="domain-score mb-3">
                                <div class="score-details">
                                    ${Object.entries(brand.domains.com.score.details).map(([key, detail]) => `
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
                            ` : ''}
                            <div class="domains-container"></div>
                        </div>
                    `;
                    brandCardContainer.innerHTML = brandCard;
                    
                    // Get domain entries
                    const allDomainEntries = Object.entries(brand.domains || {})
                        .sort(([ext1], [ext2]) => ext2 === 'com' ? 1 : ext1 === 'com' ? -1 : 0); // Move .com to end
                    console.log('Domain entries:', allDomainEntries);
                    
                    // Get the domains container
                    const domainsContainer = brandCardContainer.querySelector('.domains-container');
                    
                    // Process first 3 domains (excluding .com since it's in the header)
                    const nonComDomains = allDomainEntries.filter(([ext]) => ext !== 'com');
                    nonComDomains.slice(0, 3).forEach(([ext, info]) => {
                        const domainCard = createDomainCard(brand.name, ext, info, false);
                        domainsContainer.appendChild(domainCard);
                    });
                    
                    // Create container for remaining domains
                    if (nonComDomains.length > 3) {
                        const remainingContainer = document.createElement('div');
                        remainingContainer.className = 'remaining-domains';
                        remainingContainer.style.display = 'none';
                        
                        // Process remaining domains
                        nonComDomains.slice(3).forEach(([ext, info]) => {
                            const domainCard = createDomainCard(brand.name, ext, info, false);
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
            console.log('Auth token present:', !!authToken);
            
            if (!authToken) {
                const loginModal = new bootstrap.Modal(document.getElementById('loginModal'));
                loginModal.show();
                return;
            }

            try {
                console.log('Fetching favorites and watchlist...');
                const response = await fetch('/favorites', {
                    method: 'GET',
                    headers: {
                        'Authorization': `Bearer ${authToken}`,
                        'Accept': 'text/html',
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                console.log('Response status:', response.status);
                const responseText = await response.text();
                console.log('Response text length:', responseText.length);
                console.log('First 500 characters of response:', responseText.substring(0, 500));

                if (response.ok) {
                    // Replace the current page content with the favorites page
                    document.documentElement.innerHTML = responseText;
                    console.log('Page content updated');
                    
                    // Check if watchlist tab and content exist
                    const watchlistTab = document.getElementById('watchlist-tab');
                    const watchlistContent = document.getElementById('watchlist');
                    console.log('Watchlist tab exists:', !!watchlistTab);
                    console.log('Watchlist content exists:', !!watchlistContent);
                    
                    if (watchlistContent) {
                        const watchlistItems = watchlistContent.querySelectorAll('.watchlist-list > div');
                        console.log('Number of watchlist items found:', watchlistItems.length);
                        watchlistItems.forEach((item, index) => {
                            console.log(`Watchlist item ${index + 1}:`, item.dataset);
                        });
                    }
                    
                    // Reinitialize necessary functions and event listeners
                    console.log('Initializing favorites page...');
                    initializeFavoritesPage();
                    
                    // Reinitialize any necessary scripts
                    updateAuthUI();
                    
                    // Reinitialize Bootstrap components if needed
                    if (typeof bootstrap !== 'undefined') {
                        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
                        tooltipTriggerList.map(function (tooltipTriggerEl) {
                            return new bootstrap.Tooltip(tooltipTriggerEl);
                        });
                    }
                } else if (response.status === 401) {
                    console.log('Unauthorized access, showing login modal');
                    localStorage.removeItem('authToken');
                    localStorage.removeItem('username');
                    const loginModal = new bootstrap.Modal(document.getElementById('loginModal'));
                    loginModal.show();
                } else {
                    console.error('Error fetching favorites. Status:', response.status);
                    console.error('Response text:', responseText);
                    showToast('Failed to load favorites: ' + (responseText || 'Unknown error'), 'error');
                }
            } catch (error) {
                console.error('Error in favorites fetch:', error);
                showToast('Failed to load favorites: ' + error.message, 'error');
            }
        });
    }

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

    // Add CSS for the main score circle and update small circle
    const style = document.createElement('style');
    style.textContent = `
        .score-circle-main {
            width: 42px;
            height: 42px;
            position: relative;
            background: conic-gradient(
                #198754 calc(var(--score-value) * 1%),
                #e9ecef calc(var(--score-value) * 1%)
            );
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .score-circle-main .score-circle-inner {
            width: 34px;
            height: 34px;
            background: white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .score-circle-main .score-value {
            font-size: 16px;
            font-weight: bold;
            color: #198754;
        }

        .score-circle-small {
            width: 28px;
            height: 28px;
            position: relative;
            background: conic-gradient(
                #6c757d calc(var(--score-value) * 1%),
                #e9ecef calc(var(--score-value) * 1%)
            );
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .score-circle-small .score-circle-inner {
            width: 20px;
            height: 20px;
            background: white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .score-circle-small .score-value {
            font-size: 10px;
            font-weight: bold;
            color: #6c757d;
        }

        .score-details {
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 0.5rem;
        }

        .score-item {
            margin-bottom: 0.5rem;
        }

        .score-bar-container {
            height: 8px;
            background: #e9ecef;
            border-radius: 4px;
            overflow: hidden;
            margin-right: 1rem;
        }

        .score-bar {
            height: 100%;
            background: #198754;
            border-radius: 4px;
            transition: width 0.3s ease;
        }

        .score-tooltip {
            display: none;
            position: absolute;
            background: #343a40;
            color: white;
            padding: 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.875rem;
            z-index: 1000;
            max-width: 200px;
        }

        .score-item:hover .score-tooltip {
            display: block;
        }
    `;
    document.head.appendChild(style);
});

// Update UI based on auth state
function updateAuthUI() {
    const loginRegisterNav = document.getElementById('loginRegisterNav');
    const userNav = document.getElementById('userNav');
    const username = document.getElementById('username');
    
    // Only proceed if elements exist
    if (loginRegisterNav && userNav && username) {
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
            // Store auth data
            localStorage.setItem('authToken', data.access_token);
            localStorage.setItem('username', username);
            currentUser = username;
            authToken = data.access_token;
            
            // Update UI
            updateAuthUI();
            
            // Hide login modal
            const loginModal = bootstrap.Modal.getInstance(document.getElementById('loginModal'));
            if (loginModal) {
                loginModal.hide();
            }
            
            // Show success message
            showToast('Successfully logged in', 'success');
            
            // Restore previous results if they exist
            const pendingResults = localStorage.getItem('pendingResults');
            if (pendingResults) {
                const resultsContainer = document.querySelector('.results-container');
                if (resultsContainer) {
                    resultsContainer.style.display = 'block';
                    resultsContainer.innerHTML = pendingResults;
                    
                    // Reinitialize any necessary components
                    document.querySelectorAll('.score-circle').forEach(circle => {
                        const scoreValue = circle.querySelector('.score-value').textContent;
                        circle.style.setProperty('--score-value', scoreValue);
                    });
                    
                    // Clear stored results
                    localStorage.removeItem('pendingResults');
                }
                
                // Check for pending favorite action
                const pendingAction = localStorage.getItem('pendingFavoriteAction');
                if (pendingAction) {
                    try {
                        const action = JSON.parse(pendingAction);
                        if (action.type === 'addToFavorites') {
                            // Slight delay to ensure everything is initialized
                            setTimeout(() => {
                                addToFavorites(
                                    new Event('click'),
                                    action.brandName,
                                    action.domainName,
                                    action.extension,
                                    action.price
                                );
                            }, 500);
                        }
                    } catch (e) {
                        console.error('Error retrying pending favorite action:', e);
                    } finally {
                        localStorage.removeItem('pendingFavoriteAction');
                    }
                }
            }
        } else {
            errorDiv.textContent = data.detail;
            errorDiv.classList.remove('d-none');
        }
    } catch (error) {
        console.error('Login error:', error);
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
    
    const authToken = localStorage.getItem('authToken');
    if (!authToken) {
        // Store the current results before showing login modal
        const resultsContainer = document.querySelector('.results-container');
        if (resultsContainer) {
            localStorage.setItem('pendingResults', resultsContainer.innerHTML);
            localStorage.setItem('pendingFavoriteAction', JSON.stringify({
                type: 'addToFavorites',
                brandName,
                domainName,
                extension,
                price
            }));
        }
        
        showToast('Please log in to add domains to favorites', 'warning');
        const loginModal = new bootstrap.Modal(document.getElementById('loginModal'));
        loginModal.show();
        return;
    }
    
    // Clean the domain name by removing the extension if it's present
    const cleanDomainName = domainName.replace(`.${extension}`, '');
    
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
        
        // Map score types to the correct field names
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
                domain_name: cleanDomainName,
                domain_extension: extension,
                price: price,
                total_score: totalScore,
                ...scores
            })
        });

        if (response.ok) {
            showToast('Added to favorites!', 'success');
            const button = event.target.closest('.favorite-btn');
            button.classList.add('btn-success');
            button.disabled = true;
            button.innerHTML = '<span class="heart-icon">♥</span>';
        } else if (response.status === 401) {
            showToast('Your session has expired. Please log in again.', 'warning');
            localStorage.removeItem('authToken');
            localStorage.removeItem('username');
            const loginModal = new bootstrap.Modal(document.getElementById('loginModal'));
            loginModal.show();
        } else {
            const data = await response.json();
            showToast(data.detail || 'Failed to add to favorites', 'error');
        }
    } catch (error) {
        console.error('Error adding to favorites:', error);
        showToast('Failed to add to favorites', 'error');
    }
}

// Add toast notification function if it doesn't exist
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast-notification ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    // Remove the toast after 3 seconds
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// Add to watchlist
async function addToWatchlist(event, brandName, domainName, extension) {
    event.preventDefault();
    
    const authToken = localStorage.getItem('authToken');
    if (!authToken) {
        showToast('Please log in to add domains to watchlist', 'warning');
        const loginModal = new bootstrap.Modal(document.getElementById('loginModal'));
        loginModal.show();
        return;
    }
    
    // Clean the domain name by removing the extension if it's present
    const cleanDomainName = domainName.replace(`.${extension}`, '');
    
    try {
        const response = await fetch('/watchlist', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({
                domain_name: cleanDomainName,
                domain_extension: extension
            })
        });

        if (response.ok) {
            showToast('Added to watchlist!', 'success');
            const button = event.target.closest('.watchlist-btn');
            button.classList.add('btn-info');
            button.disabled = true;
            button.innerHTML = '<i class="bi bi-eye-fill"></i>';
        } else if (response.status === 401) {
            showToast('Your session has expired. Please log in again.', 'warning');
            localStorage.removeItem('authToken');
            localStorage.removeItem('username');
            const loginModal = new bootstrap.Modal(document.getElementById('loginModal'));
            loginModal.show();
        } else {
            const data = await response.json();
            showToast(data.detail || 'Failed to add to watchlist', 'error');
        }
    } catch (error) {
        console.error('Error adding to watchlist:', error);
        showToast('Failed to add to watchlist', 'error');
    }
}

// Remove from watchlist
async function removeFromWatchlist(watchlistId) {
    try {
        const response = await fetch(`/watchlist/${watchlistId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${authToken}`,
            }
        });
        
        if (response.ok) {
            // Remove the watchlist item from the DOM
            const watchlistElement = document.querySelector(`[data-watchlist-id="${watchlistId}"]`);
            if (watchlistElement) {
                watchlistElement.remove();
            }
            showToast('Domain removed from watchlist');
            
            // Update the watchlist count
            const countElement = document.getElementById('watchlistCount');
            if (countElement) {
                const currentCount = parseInt(countElement.textContent) - 1;
                countElement.textContent = currentCount;
            }
        } else {
            showToast('Failed to remove domain from watchlist', 'error');
        }
    } catch (error) {
        console.error('Error removing from watchlist:', error);
        showToast('Failed to remove from watchlist', 'error');
    }
}

// Update the createDomainCard function to remove detailed scores
function createDomainCard(brandName, ext, info, isFirstVariant = true) {
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
    
    // Create the base HTML structure
    domainCard.innerHTML = `
        <div class="d-flex justify-content-between align-items-center">
            <div class="d-flex align-items-center gap-2">
                <span class="domain-name h5 mb-0">${brandName}.${ext}</span>
                <div class="score-circle-small" style="--score-value: ${score.total_score}">
                    <div class="score-circle-inner">
                        <span class="score-value">${score.total_score}</span>
                    </div>
                </div>
            </div>
            <span class="domain-badge ${statusClass}">${statusText}</span>
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
        ` : `
            <div class="mt-2">
                <button class="btn btn-sm btn-outline-secondary w-100 watchlist-btn"
                        onclick="addToWatchlist(event, '${brandName}', '${ext}')">
                    <i class="bi bi-eye"></i> Add to Watchlist
                </button>
            </div>
        `}
    `;
    
    return domainCard;
}

// Function to initialize the favorites page
function initializeFavoritesPage() {
    console.log('Initializing favorites page...');
    
    // Check for watchlist elements
    const watchlistTab = document.getElementById('watchlist-tab');
    const watchlistContent = document.getElementById('watchlist');
    console.log('Found watchlist tab:', !!watchlistTab);
    console.log('Found watchlist content:', !!watchlistContent);
    
    if (watchlistContent) {
        const watchlistItems = watchlistContent.querySelectorAll('.watchlist-list > div');
        console.log('Found watchlist items:', watchlistItems.length);
    }

    // Define toggleAlert function
    window.toggleAlert = async function(id, button) {
        try {
            const currentState = button.getAttribute('data-notify') === 'true';
            const response = await fetch(`/watchlist/${id}/notify`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('authToken')}`
                },
                body: JSON.stringify({
                    notify_when_available: !currentState
                })
            });

            if (response.ok) {
                button.setAttribute('data-notify', (!currentState).toString());
                
                // Update button appearance
                if (!currentState) {
                    button.classList.add('active');
                    button.querySelector('i').classList.remove('bi-bell-slash');
                    button.querySelector('i').classList.add('bi-bell');
                    button.setAttribute('title', 'Notifications enabled');
                } else {
                    button.classList.remove('active');
                    button.querySelector('i').classList.remove('bi-bell');
                    button.querySelector('i').classList.add('bi-bell-slash');
                    button.setAttribute('title', 'Get notified when available');
                }
                
                // Update tooltip if it exists
                const tooltip = bootstrap.Tooltip.getInstance(button);
                if (tooltip) {
                    tooltip.dispose();
                }
                new bootstrap.Tooltip(button);

                showToast('success', !currentState ? 'Alerts enabled' : 'Alerts disabled');
            } else {
                showToast('error', 'Failed to update alert settings');
            }
        } catch (error) {
            console.error('Error toggling alert:', error);
            showToast('error', 'Failed to update alert settings');
        }
    };

    // Define removeFromWatchlist function
    window.removeFromWatchlist = async function(id) {
        console.log('Removing watchlist item:', id);
        try {
            const response = await fetch(`/watchlist/${id}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('authToken')}`
                }
            });

            console.log('Remove watchlist response:', response.status);
            if (response.ok) {
                // Remove the watchlist item from the UI
                const watchlistItem = document.querySelector(`[data-watchlist-id="${id}"]`);
                console.log('Found watchlist item to remove:', !!watchlistItem);
                if (watchlistItem) {
                    watchlistItem.remove();
                }
                // Update the watchlist count
                const watchlistCount = document.getElementById('watchlistCount');
                if (watchlistCount) {
                    const currentCount = parseInt(watchlistCount.textContent);
                    watchlistCount.textContent = currentCount - 1;
                    console.log('Updated watchlist count to:', currentCount - 1);
                }
                showToast('Domain removed from watchlist successfully', 'success');
            } else {
                showToast('Failed to remove domain from watchlist', 'error');
            }
        } catch (error) {
            console.error('Error removing from watchlist:', error);
            showToast('Failed to remove domain from watchlist', 'error');
        }
    };

    // Add sorting functionality for watchlist
    const watchlistSortButtons = document.querySelectorAll('#watchlist .btn-group button[data-sort]');
    console.log('Found watchlist sort buttons:', watchlistSortButtons.length);
    watchlistSortButtons.forEach(button => {
        button.addEventListener('click', () => {
            const sortBy = button.getAttribute('data-sort');
            console.log('Sorting watchlist by:', sortBy);
            const watchlistItems = Array.from(document.querySelectorAll('.watchlist-list > div'));
            console.log('Items to sort:', watchlistItems.length);
            
            watchlistItems.sort((a, b) => {
                const aValue = a.getAttribute(`data-${sortBy}`).toLowerCase();
                const bValue = b.getAttribute(`data-${sortBy}`).toLowerCase();
                console.log(`Comparing ${aValue} with ${bValue}`);
                return aValue.localeCompare(bValue);
            });
            
            const watchlistContainer = document.querySelector('.watchlist-list');
            watchlistItems.forEach(item => watchlistContainer.appendChild(item));
            console.log('Sorting complete');
        });
    });

    // Add sorting functionality for favorites
    const favoriteSortButtons = document.querySelectorAll('#favorites .btn-group button[data-sort]');
    console.log('Found favorites sort buttons:', favoriteSortButtons.length);
    favoriteSortButtons.forEach(button => {
        button.addEventListener('click', () => {
            const sortBy = button.getAttribute('data-sort');
            const favoriteItems = Array.from(document.querySelectorAll('.favorites-list > div'));
            
            favoriteItems.sort((a, b) => {
                const aValue = a.getAttribute(`data-${sortBy}`).toLowerCase();
                const bValue = b.getAttribute(`data-${sortBy}`).toLowerCase();
                return aValue.localeCompare(bValue);
            });
            
            const favoritesContainer = document.querySelector('.favorites-list');
            favoriteItems.forEach(item => favoritesContainer.appendChild(item));
        });
    });
    
    console.log('Favorites page initialization complete');
}

// Initialize auth UI on page load
updateAuthUI(); 