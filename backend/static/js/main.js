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

    // Advanced options toggle
    const advancedOptionsToggle = document.getElementById('advancedOptionsToggle');
    const advancedOptions = document.getElementById('advancedOptions');
    
    // Initialize range slider
    const lengthSlider = document.getElementById('lengthSlider');
    if (lengthSlider) {
        noUiSlider.create(lengthSlider, {
            start: [3, 15],
            connect: true,
            step: 1,
            range: {
                'min': 3,
                'max': 15
            },
            format: {
                to: value => Math.round(value),
                from: value => Math.round(value)
            },
            tooltips: [true, true]
        });

        // Update the display values
        const minLengthValue = document.getElementById('minLengthValue');
        const maxLengthValue = document.getElementById('maxLengthValue');
        
        lengthSlider.noUiSlider.on('update', function(values, handle) {
            if (handle === 0) {
                minLengthValue.textContent = values[0];
            } else {
                maxLengthValue.textContent = values[1];
            }
        });
    }
    
    if (advancedOptionsToggle) {
        advancedOptionsToggle.addEventListener('click', function() {
            const isHidden = advancedOptions.style.display === 'none';
            advancedOptions.style.display = isHidden ? 'block' : 'none';
            this.innerHTML = isHidden ? 
                '<i class="bi bi-gear-fill"></i> Hide Advanced Options' : 
                '<i class="bi bi-gear"></i> Advanced Options';
            
            // Add animation class
            if (isHidden) {
                advancedOptions.classList.add('fade-in');
            }
        });
    }

    if (form) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            // Hide advanced options menu if it's open
            if (advancedOptions && advancedOptionsToggle) {
                advancedOptions.style.display = 'none';
                advancedOptionsToggle.innerHTML = '<i class="bi bi-gear"></i> Advanced Options';
                advancedOptions.classList.remove('fade-in');
            }
            
            const keywords = document.getElementById('keywordInput').value.trim();
            const style = document.getElementById('styleSelect').value;
            const [minLength, maxLength] = lengthSlider.noUiSlider.get();
            const includeWord = document.getElementById('includeWord').value.trim();
            const similarTo = document.getElementById('similarTo').value.trim();
            
            // Get selected domain extensions
            const selectedExtensions = [];
            document.querySelectorAll('.extension-checkbox:checked').forEach(checkbox => {
                selectedExtensions.push(checkbox.getAttribute('data-ext'));
            });
            
            // Validate at least one extension is selected
            if (selectedExtensions.length === 0) {
                showToast('Please select at least one domain extension', 'error');
                return;
            }
            
            // Validate length values
            if (parseInt(minLength) > parseInt(maxLength)) {
                showToast('Minimum length cannot be greater than maximum length', 'error');
                return;
            }

            if (!keywords) {
                showToast('Please enter keywords', 'error');
                return;
            }

            // Only hide results container if it's a new search
            if (!e.target.hasAttribute('data-generating-more')) {
                resultsContainer.style.display = 'none';
                resultsDiv.innerHTML = '';
            }

            // Show loading indicator
            loading.style.display = 'block';
            
            // Start loading progress simulation
            simulateLoadingProgress();
            
            // Track the start time for response timing
            const startTime = new Date().getTime();
            
            try {
                const requestBody = {
                    keywords: keywords,
                    style: style,
                    num_suggestions: 20,
                    exclude_names: Array.from(document.querySelectorAll('.brand-card h3')).map(h => h.textContent.split('.')[0]),
                    min_length: parseInt(minLength),
                    max_length: parseInt(maxLength),
                    extensions: selectedExtensions
                };

                // Only add include_word if it's not empty
                if (includeWord) {
                    requestBody.include_word = includeWord;
                }
                
                // Add similar_to parameter if it's not empty
                if (similarTo) {
                    requestBody.similar_to = similarTo;
                }

                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 60000); // 30-second timeout

                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(requestBody),
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                
                // Ensure our loading steps progress to match the actual timing
                const responseTime = new Date().getTime() - startTime;
                adjustLoadingProgress(responseTime);

                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }

                const data = await response.json();
                console.log('Raw API Response:', JSON.stringify(data, null, 2));

                // Remove the additional loading indicator if it exists
                const moreLoading = document.getElementById('moreLoading');
                if (moreLoading) {
                    moreLoading.remove();
                }
                
                // Process each brand
                data.forEach((brand, index) => {
                    console.log(`Processing brand ${index + 1}:`, JSON.stringify(brand, null, 2));
                    
                    // Check for provider information in each domain
                    for (const [ext, domainInfo] of Object.entries(brand.domains)) {
                        console.log(`Domain ${brand.name}.${ext} providers:`, domainInfo.providers);
                        if (domainInfo.providers) {
                            console.log(`Provider keys for ${brand.name}.${ext}:`, Object.keys(domainInfo.providers));
                            if (domainInfo.providers.porkbun) {
                                console.log(`Porkbun price for ${brand.name}.${ext}: ${domainInfo.providers.porkbun}`);
                            }
                        }
                    }
                    
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
                                <div class="d-flex align-items-center gap-2">
                                    <span class="domain-badge ${brand.domains.com?.available ? 'domain-available' : 'domain-unavailable'}">
                                        ${brand.domains.com?.available ? `Available - ${brand.domains.com?.price}` : 'Taken'}
                                    </span>
                                    <span class="badge bg-secondary">#${document.querySelectorAll('.brand-card').length + index + 1}</span>
                                </div>
                            </div>
                            <div class="trademark-result"></div>
                            ${brand.domains.com ? `
                            <div class="domain-score mb-3">
                                <div class="score-details">
                                    ${Object.entries(brand.domains.com.score.details).map(([key, detail]) => `
                                        <div class="score-item d-flex align-items-center mb-1">
                                            <div class="score-bar-container flex-grow-1">
                                                <div class="score-bar" style="width: ${detail.score}%"></div>
                                            </div>
                                            <small class="ms-2">${key.charAt(0).toUpperCase() + key.slice(1)}</small>
                                            
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                            ${brand.domains.com.available ? `
                                <div class="d-flex gap-2 mb-3">
                                    <div class="d-flex gap-2 flex-grow-1">
                                        <div class="btn-group flex-grow-1">
                                            ${(() => {
                                                // Find first provider with valid price
                                                const providers = brand.domains.com?.providers || {};
                                                const validProviders = [
                                                    { id: 'godaddy', name: 'GoDaddy', price: providers.godaddy },
                                                    { id: 'porkbun', name: 'Porkbun', price: providers.porkbun },
                                                    { id: 'namesilo', name: 'Namesilo', price: providers.namesilo },
                                                    { id: 'dynadot', name: 'dynadot', price: providers.dynadot },
                                                    { id: 'namecheap', name: 'Namecheap', price: providers.namecheap }
                                                ].filter(p => p.price && !isNaN(p.price));
                                                
                                                // Default to godaddy if no valid providers
                                                const defaultProvider = validProviders.length > 0 ? validProviders[0] : { id: 'godaddy', name: 'GoDaddy' };
                                                
                                                return `<a href="https://${defaultProvider.id === 'godaddy' ? 'www.godaddy.com/domainsearch/find?domainToCheck=' : ''}${defaultProvider.id}.com/domains/${brand.name}.com" 
                                                   target="_blank" 
                                                   class="btn btn-sm btn-outline-primary register-domain-btn flex-grow-1"
                                                   data-domain="${brand.name}.com"
                                                   data-provider="${defaultProvider.id}">
                                                    <img src="/static/css/images/${defaultProvider.id}.ico" class="provider-icon" width="14" height="14" alt="${defaultProvider.name}"> Register Domain
                                                </a>`;
                                            })()}
                                            <button type="button" 
                                                    class="btn btn-sm btn-outline-primary dropdown-toggle dropdown-toggle-split" 
                                                    data-bs-toggle="dropdown" 
                                                    aria-expanded="false">
                                                <span class="visually-hidden">Toggle Dropdown</span>
                                            </button>
                                            <ul class="dropdown-menu dropdown-menu-end provider-dropdown">
                                                <li><h6 class="dropdown-header">Choose Provider</h6></li>
                                                ${brand.domains.com?.providers?.godaddy && !isNaN(brand.domains.com.providers.godaddy) ? `
                                                <li><a class="dropdown-item provider-option" href="#" data-provider="godaddy" data-domain="${brand.name}.com">
                                                    GoDaddy $${(brand.domains.com.providers.godaddy/1000000).toFixed(2)}
                                                </a></li>` : ''}
                                                ${brand.domains.com?.providers?.porkbun && !isNaN(brand.domains.com.providers.porkbun) ? `
                                                <li><a class="dropdown-item provider-option" href="#" data-provider="porkbun" data-domain="${brand.name}.com">
                                                    Porkbun $${(brand.domains.com.providers.porkbun/1000000).toFixed(2)}
                                                </a></li>` : ''}
                                                ${brand.domains.com?.providers?.namesilo && !isNaN(brand.domains.com.providers.namesilo) ? `
                                                <li><a class="dropdown-item provider-option" href="#" data-provider="namesilo" data-domain="${brand.name}.com">
                                                    Namesilo $${(brand.domains.com.providers.namesilo/1000000).toFixed(2)}
                                                </a></li>` : ''}
                                                ${brand.domains.com?.providers?.dynadot && !isNaN(brand.domains.com.providers.dynadot) ? `
                                                <li><a class="dropdown-item provider-option" href="#" data-provider="dynadot" data-domain="${brand.name}.com">
                                                    dynadot $${(brand.domains.com.providers.dynadot/1000000).toFixed(2)}
                                                </a></li>` : ''}
                                                ${brand.domains.com?.providers?.namecheap && !isNaN(brand.domains.com.providers.namecheap) ? `
                                                <li><a class="dropdown-item provider-option" href="#" data-provider="namecheap" data-domain="${brand.name}.com">
                                                    Namecheap $${(brand.domains.com.providers.namecheap/1000000).toFixed(2)}
                                                </a></li>` : ''}
                                            </ul>
                                        </div>
                                        <button class="btn btn-sm btn-outline-dark flex-grow-1"
                                                onclick="checkSocialMedia(event, '${brand.name}')">
                                            <i class="bi bi-at"></i> Check Social Media
                                        </button>
                                    </div>
                                    <button class="btn btn-sm btn-outline-success favorite-btn"
                                            onclick="addToFavorites(event, '${brand.name}', '${brand.name}.com', 'com', '${brand.domains.com.price}')">
                                        <span class="heart-icon">♥</span>
                                    </button>
                                </div>
                                <button class="toggle-score-details com-score-details" onclick="toggleComScoreDetails(this)">
                                    <span>View Score Details</span>
                                    <i class="bi bi-chevron-down"></i>
                                </button>
                            ` : `
                                <div class="d-flex gap-2 mb-3">
                                    <button class="btn btn-sm btn-outline-secondary flex-grow-1"
                                            onclick="addToWatchlist(event, '${brand.name}', 'com')">
                                        <i class="bi bi-eye"></i> Add to Watchlist
                                    </button>
                                    <button class="btn btn-sm btn-outline-dark flex-grow-1"
                                            onclick="checkSocialMedia(event, '${brand.name}')">
                                        <i class="bi bi-at"></i> Check Social Media
                                    </button>
                                </div>
                                <button class="toggle-score-details com-score-details" onclick="toggleComScoreDetails(this)">
                                    <span>View Score Details</span>
                                    <i class="bi bi-chevron-down"></i>
                                </button>
                            `}
                            ` : ''}
                            <div class="domains-container"></div>
                        </div>
                    `;
                    brandCardContainer.innerHTML = brandCard;
                    
                    // Get domain entries
                    const allDomainEntries = Object.entries(brand.domains || {})
                        .sort(([ext1], [ext2]) => ext2 === 'com' ? 1 : ext1 === 'com' ? -1 : 0);
                    console.log('Domain entries:', allDomainEntries);
                    
                    // Get the domains container
                    const domainsContainer = brandCardContainer.querySelector('.domains-container');
                    
                    // Filter out .com domains since they're in the header
                    const nonComDomains = allDomainEntries.filter(([ext]) => ext !== 'com');
                    
                    // Create container for all domains
                    if (nonComDomains.length > 0) {
                        const remainingContainer = document.createElement('div');
                        remainingContainer.className = 'remaining-domains';
                        remainingContainer.style.display = 'none';
                        
                        // Process all domains
                        nonComDomains.forEach(([ext, info]) => {
                            const domainCard = createDomainCard(brand.name, ext, info, false);
                            remainingContainer.appendChild(domainCard);
                        });

                        domainsContainer.appendChild(remainingContainer);
                        
                        // Add toggle button
                        const toggleButton = document.createElement('button');
                        toggleButton.className = 'btn btn-sm btn-outline-secondary w-100 mt-2 toggle-domains';
                        toggleButton.innerHTML = `
                            <span class="more-text">Show More Extensions (${nonComDomains.length})</span>
                            <span class="less-text" style="display: none;">Hide Extensions</span>
                            <i class="bi bi-chevron-down"></i>
                        `;
                        
                        toggleButton.addEventListener('click', function() {
                            const remainingDomains = this.previousElementSibling;
                            const moreText = this.querySelector('.more-text');
                            const lessText = this.querySelector('.less-text');
                            const icon = this.querySelector('i');
                            
                            if (remainingDomains.style.display === 'none') {
                                remainingDomains.style.display = 'block';
                                moreText.style.display = 'none';
                                lessText.style.display = 'inline';
                                icon.style.transform = 'rotate(180deg)';
                            } else {
                                remainingDomains.style.display = 'none';
                                moreText.style.display = 'inline';
                                lessText.style.display = 'none';
                                icon.style.transform = 'rotate(0)';
                            }
                        });
                        
                        domainsContainer.appendChild(toggleButton);
                        
                        // Add "Check More Extensions" button after the toggle button
                        const checkMoreButton = document.createElement('button');
                        checkMoreButton.className = 'btn btn-sm btn-outline-primary w-100 mt-2';
                        checkMoreButton.innerHTML = '<i class="bi bi-search"></i> Check More Extensions';
                        checkMoreButton.onclick = function(event) {
                            checkMoreExtensions(event, brand.name);
                        };
                        domainsContainer.appendChild(checkMoreButton);
                    } else {
                        // If there are no additional domains, just add the "Check More Extensions" button
                        const checkMoreButton = document.createElement('button');
                        checkMoreButton.className = 'btn btn-sm btn-outline-primary w-100 mt-2';
                        checkMoreButton.innerHTML = '<i class="bi bi-search"></i> Check More Extensions';
                        checkMoreButton.onclick = function(event) {
                            checkMoreExtensions(event, brand.name);
                        };
                        domainsContainer.appendChild(checkMoreButton);
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

                // Add the Generate More button only if this is not a "generating more" request
                let generateMoreBtn = document.getElementById('generateMoreBtn');
                if (!e.target.hasAttribute('data-generating-more')) {
                    generateMoreBtn = document.createElement('button');
                    generateMoreBtn.id = 'generateMoreBtn';
                    generateMoreBtn.className = 'btn btn-primary mt-4 w-100';
                    generateMoreBtn.innerHTML = 'Generate More Names';
                    generateMoreBtn.onclick = function(event) {
                        event.preventDefault();
                        const submitEvent = new Event('submit');
                        form.setAttribute('data-generating-more', 'true');
                        form.dispatchEvent(submitEvent);
                        // Remove the button after clicking
                        event.target.remove();
                    };
                    resultsContainer.appendChild(generateMoreBtn);
                } else {
                    // If this was a "generate more" request, remove the button if it exists
                    if (generateMoreBtn) {
                        generateMoreBtn.remove();
                    }
                }
                
                // Scroll to the new results if generating more
                if (e.target.hasAttribute('data-generating-more')) {
                    const newResults = Array.from(resultsDiv.children).slice(-data.length);
                    if (newResults.length > 0) {
                        newResults[0].scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                } else {
                    // Scroll to results container for new searches
                    resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
                
            } catch (error) {
                console.error('Error:', error);
                
                // Remove the additional loading indicator if it exists
                const moreLoading = document.getElementById('moreLoading');
                if (moreLoading) {
                    moreLoading.remove();
                }

                // Re-enable the Generate More button if it exists
                const generateMoreBtn = document.getElementById('generateMoreBtn');
                if (generateMoreBtn) {
                    generateMoreBtn.disabled = false;
                    generateMoreBtn.innerHTML = 'Generate More Names';
                }

                if (!e.target.hasAttribute('data-generating-more')) {
                    resultsDiv.innerHTML = `
                        <div class="col-12 text-center">
                            <div class="alert alert-danger">
                                An error occurred while generating brand names. Please try again.
                            </div>
                        </div>
                    `;
                } else {
                    // Show error toast for "Generate More" errors
                    showToast('Failed to generate more names. Please try again.', 'error');
                }
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

    // Initialize provider dropdown functionality
    initializeProviderDropdowns();
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
    const domainCard = event.target.closest('.domain-card') || event.target.closest('.brand-card');
    const totalScore = parseInt(domainCard.querySelector('.score-value').textContent);
    
    // Check if there's a selected provider and get its price
    let currentPrice = price;
    const registerBtn = domainCard.querySelector('.register-domain-btn');
    if (registerBtn) {
        const selectedProvider = registerBtn.getAttribute('data-provider');
        if (selectedProvider) {
            console.log(`Selected provider: ${selectedProvider}`);
            
            // Get the price from the domain badge
            const domainBadge = domainCard.querySelector('.domain-badge');
            if (domainBadge && domainBadge.classList.contains('domain-available')) {
                const priceMatch = domainBadge.textContent.match(/\$[\d.]+/);
                if (priceMatch) {
                    currentPrice = priceMatch[0];
                    console.log(`Using current price from selected provider: ${currentPrice}`);
                }
            }
        }
    }
    
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
                price: currentPrice,
                total_score: totalScore,
                length_score: scores.length_score,
                dictionary_score: scores.dictionary_score,
                pronounceability_score: scores.pronounceability_score,
                repetition_score: scores.repetition_score,
                tld_score: scores.tld_score
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
    // Remove any existing toasts
    const existingToasts = document.querySelectorAll('.toast-notification');
    existingToasts.forEach(toast => toast.remove());
    
    // Create a new toast
    const toast = document.createElement('div');
    toast.className = 'toast-notification';
    
    // Add class based on type
    toast.classList.add(type);
    
    // Add icon based on type
    let icon = '';
    if (type === 'error') {
        icon = '<i class="bi bi-x-circle me-2"></i>';
    } else if (type === 'warning') {
        icon = '<i class="bi bi-exclamation-triangle me-2"></i>';
    } else if (type === 'info') {
        icon = '<i class="bi bi-info-circle me-2"></i>';
    } else {
        icon = '<i class="bi bi-check-circle me-2"></i>';
    }
    
    // Set the toast content
    toast.innerHTML = `
        <div class="d-flex align-items-center">
            ${icon}
            <span>${message}</span>
        </div>
    `;
    
    // Add the toast to the document
    document.body.appendChild(toast);
    
    // Remove the toast after 3 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => {
            toast.remove();
        }, 300);
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


// Function to get the URL for a specific domain provider
function getDomainProviderUrl(provider, domain) {
    switch(provider.toLowerCase()) {
        case 'porkbun':
            return `https://porkbun.com/checkout/search?q=${domain}`;
        case 'namecheap':
            return `https://www.namecheap.com/domains/registration/results/?domain=${domain}`;
        case 'namespace':
            return `https://www.name.com/domain/search/${domain}`;
        case 'dynadot':
            return `https://www.dynadot.com/domain/search?domain=${domain}`;
        case 'namesilo':
            return `https://www.namesilo.com/domain/search-domains?rid=e5cc231ahquery=${domain}`;
        default:
            return `https://www.godaddy.com/domainsearch/find?domainToCheck=${domain}`;
    }
}

// Update the createDomainCard function to not show score details for non-.com domains
function createDomainCard(brandName, ext, info, isFirstVariant = true) {
    console.log(`Creating domain card for ${brandName}.${ext}:`, JSON.stringify(info, null, 2));
    
    const domainCard = document.createElement('div');
    domainCard.className = 'domain-card';
    
    const statusClass = info.available ? 'domain-available' : 'domain-unavailable';
    
    // Format the price properly
    let priceDisplay = 'N/A';
    if (info.available) {
        // Check if we have price_info
        if (info.price_info && info.price_info.purchase) {
            priceDisplay = `$${(info.price_info.purchase/1000000).toFixed(2)}`;
        } 
        // Check if we have a direct price field
        else if (info.price && info.price !== 'undefined') {
            // Try to parse if it's a string
            if (typeof info.price === 'string' && info.price.includes('$')) {
                priceDisplay = info.price;
            } else {
                // Otherwise format it properly
                priceDisplay = `$${parseFloat(info.price).toFixed(2)}`;
            }
        }
        // Check if we have providers data
        else if (info.providers) {
            // Find the first provider with a valid price
            const providers = info.providers;
            for (const provider of ['godaddy', 'porkbun', 'namesilo', 'dynadot']) {
                if (providers[provider] && !isNaN(providers[provider])) {
                    priceDisplay = `$${(providers[provider]/1000000).toFixed(2)}`;
                    break;
                }
            }
        }
    }
    
    const statusText = info.available ? `Available - ${priceDisplay}` : 'Taken';
    
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
    
    // Set score color based on value
    let scoreColor = '#dc3545'; // Default red for low scores
    if (score.total_score >= 80) {
        scoreColor = '#198754'; // Green for high scores
    } else if (score.total_score >= 60) {
        scoreColor = '#0d6efd'; // Blue for good scores
    } else if (score.total_score >= 40) {
        scoreColor = '#ffc107'; // Yellow for medium scores
    } else if (score.total_score >= 20) {
        scoreColor = '#fd7e14'; // Orange for low scores
    }
    
    // Get provider information if available
    const providers = info.providers || {};
    console.log(`Provider information for ${brandName}.${ext}:`, providers);
    console.log(`Provider keys for ${brandName}.${ext}:`, Object.keys(providers));
    
    // Format provider prices
    const formatPrice = (price) => {
        console.log(`Formatting price: ${price}, type: ${typeof price}`);
        if (price === undefined || price === null) return 'N/A';
        return `$${(price/1000000).toFixed(2)}`;
    };
    
    // Create provider dropdown items with prices
    let providerDropdownItems = '';
    
    // Default GoDaddy option (always show)
    const godaddyPrice = formatPrice(providers.godaddy);
    console.log(`GoDaddy price for ${brandName}.${ext}: ${godaddyPrice} (raw: ${providers.godaddy})`);
    providerDropdownItems += `<li><a class="dropdown-item provider-option" href="#" data-provider="godaddy" data-domain="${brandName}.${ext}">GoDaddy ${godaddyPrice}</a></li>`;
    
    // Porkbun option (if price available)
    console.log(`Checking Porkbun price for ${brandName}.${ext}: ${providers.porkbun}`);
    if (providers.porkbun !== undefined) {
        const porkbunPrice = formatPrice(providers.porkbun);
        console.log(`Porkbun price for ${brandName}.${ext}: ${porkbunPrice} (raw: ${providers.porkbun})`);
        providerDropdownItems += `<li><a class="dropdown-item provider-option" href="#" data-provider="porkbun" data-domain="${brandName}.${ext}">Porkbun ${porkbunPrice}</a></li>`;
    } else {
        console.log(`No Porkbun price available for ${brandName}.${ext}`);
        providerDropdownItems += `<li><a class="dropdown-item provider-option" href="#" data-provider="porkbun" data-domain="${brandName}.${ext}">Porkbun</a></li>`;
    }
    
    // Dynadot option (if price available)
    console.log(`Checking Dynadot price for ${brandName}.${ext}: ${providers.dynadot}`);
    if (providers.dynadot !== undefined) {
        const dynadotPrice = formatPrice(providers.dynadot);
        console.log(`Dynadot price for ${brandName}.${ext}: ${dynadotPrice} (raw: ${providers.dynadot})`);
        providerDropdownItems += `<li><a class="dropdown-item provider-option" href="#" data-provider="dynadot" data-domain="${brandName}.${ext}">Dynadot ${dynadotPrice}</a></li>`;
    } else {
        console.log(`No Dynadot price available for ${brandName}.${ext}`);
        providerDropdownItems += `<li><a class="dropdown-item provider-option" href="#" data-provider="dynadot" data-domain="${brandName}.${ext}">Dynadot</a></li>`;
    }
    
    // Namesilo option (if price available)
    console.log(`Checking Namesilo price for ${brandName}.${ext}: ${providers.namesilo}`);
    if (providers.namesilo !== undefined) {
        const namesiloPrice = formatPrice(providers.namesilo);
        console.log(`Namesilo price for ${brandName}.${ext}: ${namesiloPrice} (raw: ${providers.namesilo})`);
        providerDropdownItems += `<li><a class="dropdown-item provider-option" href="#" data-provider="namesilo" data-domain="${brandName}.${ext}">Namesilo ${namesiloPrice}</a></li>`;
    } else {
        console.log(`No Namesilo price available for ${brandName}.${ext}`);
        providerDropdownItems += `<li><a class="dropdown-item provider-option" href="#" data-provider="namesilo" data-domain="${brandName}.${ext}">Namesilo</a></li>`;
    }
    
    // Other providers (without pricing for now)
    providerDropdownItems += `<li><a class="dropdown-item provider-option" href="#" data-provider="namespace" data-domain="${brandName}.${ext}">Namespace</a></li>`;
    providerDropdownItems += `<li><a class="dropdown-item provider-option" href="#" data-provider="namecheap" data-domain="${brandName}.${ext}">Namecheap</a></li>`;
    
    // Create the base HTML structure with improved layout
    domainCard.innerHTML = `
        <div class="domain-info">
            <div class="domain-name-container">
                <span class="domain-name">${brandName}.${ext}</span>
                <div class="score-circle-small" style="--score-value: ${score.total_score}; --score-color: ${scoreColor}">
                    <div class="score-circle-inner">
                        <span class="score-value" style="color: ${scoreColor}">${score.total_score}</span>
                    </div>
                </div>
            </div>
            <span class="domain-badge ${statusClass}">${statusText}</span>
        </div>
        
        ${info.available ? `
            <div class="domain-actions">
                <div class="btn-group flex-grow-1">
                    <a href="https://www.godaddy.com/domainsearch/find?domainToCheck=${brandName}.${ext}" 
                       target="_blank" 
                       class="btn btn-sm register-domain-btn"
                       data-domain="${brandName}.${ext}"
                       data-provider="godaddy">
                        <img src="/static/css/images/godaddy.ico" class="provider-icon" width="14" height="14" alt="GoDaddy"> 
                        <span>Register Domain</span>
                    </a>
                    <button type="button" 
                            class="btn btn-sm btn-outline-primary dropdown-toggle dropdown-toggle-split" 
                            data-bs-toggle="dropdown" 
                            aria-expanded="false">
                        <span class="visually-hidden">Toggle Dropdown</span>
                    </button>
                    <ul class="dropdown-menu dropdown-menu-end provider-dropdown">
                        <li><h6 class="dropdown-header">Choose Provider</h6></li>
                        ${providerDropdownItems}
                    </ul>
                </div>
                <button class="btn btn-sm favorite-btn"
                        onclick="addToFavorites(event, '${brandName}', '${brandName}.${ext}', '${ext}', '${info.price}')">
                    <span class="heart-icon">♥</span>
                </button>
            </div>
        ` : `
            <div class="domain-actions">
                <button class="btn btn-sm watchlist-btn w-100"
                        onclick="addToWatchlist(event, '${brandName}', '${brandName}.${ext}', '${ext}')">
                    <i class="bi bi-eye"></i> Add to Watchlist
                </button>
            </div>
        `}
    `;
    
    return domainCard;
}

// Function to toggle score details visibility
function toggleScoreDetails(button) {
    const scoreDetails = button.nextElementSibling;
    if (!scoreDetails || !scoreDetails.classList.contains('domain-score')) {
        console.error('Score details element not found');
        return;
    }
    
    button.classList.toggle('active');
    
    if (scoreDetails.classList.contains('show')) {
        scoreDetails.classList.remove('show');
        button.querySelector('span').textContent = 'View Score Details';
    } else {
        scoreDetails.classList.add('show');
        button.querySelector('span').textContent = 'Hide Score Details';
    }
}

// Function to toggle score details visibility for .com domains
function toggleComScoreDetails(button) {
    const brandCard = button.closest('.brand-card');
    if (!brandCard) {
        console.error('Brand card not found');
        return;
    }
    
    const scoreDetails = brandCard.querySelector('.domain-score');
    if (!scoreDetails) {
        console.error('Score details element not found');
        return;
    }
    
    button.classList.toggle('active');
    
    if (scoreDetails.classList.contains('show-com-score')) {
        scoreDetails.classList.remove('show-com-score');
        button.querySelector('span').textContent = 'View Score Details';
    } else {
        scoreDetails.classList.add('show-com-score');
        button.querySelector('span').textContent = 'Hide Score Details';
    }
}

// Check social media availability for a username
async function checkSocialMedia(event, brandName) {
    event.preventDefault();
    
    // Get the button that was clicked
    const button = event.target.closest('button');
    if (!button) return;
    
    // Get the brand card
    const brandCard = button.closest('.brand-card');
    if (!brandCard) return;
    
    // Get or create the social media result container
    let socialMediaResult = brandCard.querySelector('.social-media-result');
    if (!socialMediaResult) {
        socialMediaResult = document.createElement('div');
        socialMediaResult.className = 'social-media-result mb-3';
        
        // Insert after the trademark-result div or at the beginning of the card
        const trademarkResult = brandCard.querySelector('.trademark-result');
        if (trademarkResult) {
            trademarkResult.after(socialMediaResult);
        } else {
            const firstChild = brandCard.querySelector('.d-flex.justify-content-between');
            if (firstChild && firstChild.nextElementSibling) {
                firstChild.nextElementSibling.after(socialMediaResult);
            } else {
                brandCard.prepend(socialMediaResult);
            }
        }
    }
    
    // Show loading indicator
    socialMediaResult.innerHTML = `
        <div class="alert alert-info">
            <div class="d-flex align-items-center">
                <div class="spinner-border spinner-border-sm me-2" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <span>Checking social media availability for "${brandName}"...</span>
            </div>
        </div>
    `;
    
    // Update button state
    button.disabled = true;
   
    
    try {
        // Call the API
        const response = await fetch(`/check-social-media/${brandName}`);
        
        if (!response.ok) {
            throw new Error(`Error: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Social media check result:', data);
        
        // Create the result HTML
        let resultHTML = `
            <div class="alert alert-light border">
                <h6 class="mb-2">Social Media Availability for "${data.username}"</h6>
                <div class="social-media-platforms">
        `;
        
        // Add platform results
        for (const [platform, info] of Object.entries(data.platforms)) {
            let statusIcon, statusClass;
            
            if (info.available === true) {
                statusIcon = '<i class="bi bi-check-circle-fill text-success"></i>';
                statusClass = 'text-success';
            } else if (info.available === false) {
                statusIcon = '<i class="bi bi-x-circle-fill text-danger"></i>';
                statusClass = 'text-danger';
            } else {
                statusIcon = '<i class="bi bi-question-circle-fill text-warning"></i>';
                statusClass = 'text-warning';
            }
            
            resultHTML += `
                <div class="platform-result d-flex justify-content-between align-items-center mb-1">
                    <span>${platform}</span>
                    <span class="${statusClass}">${statusIcon} ${info.status}</span>
                </div>
            `;
        }
        
        // Add summary
        resultHTML += `
                </div>
                <div class="mt-2 d-flex justify-content-between">
                    <small class="text-muted">Available: ${data.available_count} | Taken: ${data.taken_count}</small>
                    <button class="btn btn-sm btn-outline-secondary" onclick="this.closest('.social-media-result').remove()">
                        <i class="bi bi-x"></i> Close
                    </button>
                </div>
            </div>
        `;
        
        // Update the result container
        socialMediaResult.innerHTML = resultHTML;
        
    } catch (error) {
        console.error('Error checking social media:', error);
        
        // Show error message
        socialMediaResult.innerHTML = `
            <div class="alert alert-danger">
                <div class="d-flex justify-content-between align-items-center">
                    <span>Error checking social media availability: ${error.message}</span>
                    <button class="btn btn-sm btn-outline-danger" onclick="this.closest('.social-media-result').remove()">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
            </div>
        `;
    } finally {
        // Reset button state
        button.disabled = false;
        button.innerHTML = '<i class="bi bi-at"></i> Check Social Media';
    }
}

// Add sorting functionality for watchlist
function initializeWatchlistSorting() {
    const watchlistSortButtons = document.querySelectorAll('#watchlist .btn-group button[data-sort]');
    console.log('Found watchlist sort buttons:', watchlistSortButtons.length);
    
    // Create a more modern sorting control
    const sortingContainer = document.createElement('div');
    sortingContainer.className = 'sorting-controls';
    
    // Add sort buttons
    const sortOptions = [
        { value: 'name', label: 'Name' },
        { value: 'date', label: 'Date Added' },
        { value: 'score', label: 'Score' }
    ];
    
    sortOptions.forEach(option => {
        const button = document.createElement('button');
        button.className = 'sort-btn';
        button.setAttribute('data-sort', option.value);
        button.textContent = `Sort by ${option.label}`;
        
        button.addEventListener('click', (e) => {
            // Remove active class from all buttons
            document.querySelectorAll('.sort-btn').forEach(btn => btn.classList.remove('active'));
            // Add active class to clicked button
            e.target.classList.add('active');
            
            const sortBy = e.target.getAttribute('data-sort');
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
        
        sortingContainer.appendChild(button);
    });
    
    // Insert the sorting controls before the watchlist
    const watchlistContent = document.getElementById('watchlist');
    if (watchlistContent) {
        const watchlistList = watchlistContent.querySelector('.watchlist-list');
        if (watchlistList) {
            watchlistContent.insertBefore(sortingContainer, watchlistList);
        }
    }
}




// Initialize auth UI on page load
updateAuthUI();

// Initialize provider dropdown functionality
function initializeProviderDropdowns() {
    // Use event delegation to handle clicks on provider options
    document.addEventListener('click', function(e) {
        if (e.target && e.target.classList.contains('provider-option')) {
            e.preventDefault();
            const provider = e.target.getAttribute('data-provider');
            const domain = e.target.getAttribute('data-domain');
            
            // Find the closest register button
            const dropdown = e.target.closest('.dropdown-menu');
            const btnGroup = dropdown.closest('.btn-group');
            const registerBtn = btnGroup.querySelector('.register-domain-btn');
            
            // Update the main button's href and provider
            registerBtn.href = getDomainProviderUrl(provider, domain);
            registerBtn.setAttribute('data-provider', provider);
            
            // Update the button with the provider icon
            updateRegisterButtonIcon(registerBtn, provider);
            
            // Get the price from the dropdown item text
            let price = 'N/A';
            const priceMatch = e.target.textContent.match(/\$[\d.]+/);
            if (priceMatch) {
                price = priceMatch[0];
            }
            
            // Update the price display on the domain card
            updateDomainCardPrice(domain, price, provider);
            
            // Show a toast notification to inform the user
            const providerName = provider.charAt(0).toUpperCase() + provider.slice(1);
            showToast(`${providerName} selected for domain registration (${price})`, 'info');
            
            // Close the dropdown
            const dropdownToggle = btnGroup.querySelector('.dropdown-toggle');
            if (dropdownToggle) {
                const bsDropdown = bootstrap.Dropdown.getInstance(dropdownToggle);
                if (bsDropdown) {
                    bsDropdown.hide();
                }
            }
        }
    });
    
    console.log('Provider dropdowns initialized');
}

// Function to update the price display on the domain card
function updateDomainCardPrice(domain, price, provider) {
    console.log(`Updating price for ${domain} to ${price} (${provider})`);
    
    // Find all domain cards that match this domain
    const domainCards = document.querySelectorAll('.domain-card');
    
    domainCards.forEach(card => {
        const domainNameElement = card.querySelector('.domain-name');
        if (domainNameElement && domainNameElement.textContent === domain) {
            console.log(`Found domain card for ${domain}`);
            
            // Update the price in the domain badge
            const domainBadge = card.querySelector('.domain-badge');
            if (domainBadge && domainBadge.classList.contains('domain-available')) {
                // Extract the original "Available" text and replace the price
                const badgeText = domainBadge.textContent.trim();
                const newBadgeText = badgeText.replace(/\$[\d.]+/, price);
                
                // If there was no price before, add it
                if (newBadgeText === badgeText && !newBadgeText.includes(price)) {
                    domainBadge.textContent = `Available - ${price}`;
                } else {
                    domainBadge.textContent = newBadgeText;
                }
                
                console.log(`Updated price display to: ${domainBadge.textContent}`);
            }
            
            // Also update the provider icon and name in the register button
            const registerBtn = card.querySelector('.register-domain-btn');
            if (registerBtn) {
                registerBtn.setAttribute('data-provider', provider);
                updateRegisterButtonIcon(registerBtn, provider);
            }
        }
    });
    
    // Also check for brand cards (the main cards with the domain in the header)
    const brandCards = document.querySelectorAll('.brand-card');
    
    brandCards.forEach(card => {
        const domainNameElement = card.querySelector('h3');
        if (domainNameElement && domainNameElement.textContent === domain) {
            console.log(`Found brand card for ${domain}`);
            
            // Update the price in the domain badge
            const domainBadge = card.querySelector('.domain-badge');
            if (domainBadge && domainBadge.classList.contains('domain-available')) {
                // Extract the original "Available" text and replace the price
                const badgeText = domainBadge.textContent.trim();
                const newBadgeText = badgeText.replace(/\$[\d.]+/, price);
                
                // If there was no price before, add it
                if (newBadgeText === badgeText && !newBadgeText.includes(price)) {
                    domainBadge.textContent = `Available - ${price}`;
                } else {
                    domainBadge.textContent = newBadgeText;
                }
                
                console.log(`Updated price display to: ${domainBadge.textContent}`);
            }
            
            // Also update the provider icon and name in the register button
            const registerBtn = card.querySelector('.register-domain-btn');
            if (registerBtn) {
                registerBtn.setAttribute('data-provider', provider);
                updateRegisterButtonIcon(registerBtn, provider);
            }
        }
    });
}

// Function to update the register button with the provider icon
function updateRegisterButtonIcon(button, provider) {
    // Get the current icon if it exists
    const existingIcon = button.querySelector('.provider-icon');
    
    // Set the icon path based on the provider
    let iconPath;
    switch(provider.toLowerCase()) {
        case 'godaddy':
            iconPath = '/static/css/images/godaddy.ico';
            break;
        case 'porkbun':
            iconPath = '/static/css/images/porkbun.ico';
            break;
        case 'namecheap':
            iconPath = '/static/css/images/namecheap.ico';
            break;
        case 'namespace':
            iconPath = '/static/css/images/namespace.ico';
            break;
        case 'dynadot':
            iconPath = '/static/css/images/dynadot.ico';
            break;
        case 'namesilo':
            iconPath = '/static/css/images/namesilo.ico';
            break;
        default:
            iconPath = '/static/css/images/godaddy.ico';
    }
    
    // If there's already an icon, just update its src
    if (existingIcon) {
        existingIcon.src = iconPath;
        existingIcon.alt = provider.charAt(0).toUpperCase() + provider.slice(1);
    } else {
        // If no icon exists, create a new one
        const newIcon = document.createElement('img');
        newIcon.className = 'provider-icon';
        newIcon.width = 14;
        newIcon.height = 14;
        newIcon.src = iconPath;
        newIcon.alt = provider.charAt(0).toUpperCase() + provider.slice(1);
        
        // Add the icon at the beginning of the button
        button.prepend(newIcon);
        
        // Add a space after the icon
        button.insertBefore(document.createTextNode(' '), newIcon.nextSibling);
    }
} 


// Favorites Page JavaScript

// Make sure deleteFavorite is defined in the global scope
function deleteFavorite(favoriteId) {
    if (!confirm('Are you sure you want to remove this domain from your favorites?')) {
        return;
    }
    
    fetch(`/favorites/${favoriteId}`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        }
    })
    .then(response => {
        if (response.ok) {
            // Remove the card from the UI
            const card = document.querySelector(`[data-favorite-id="${favoriteId}"]`);
            if (card) {
                card.classList.add('fade-out');
                setTimeout(() => {
                    card.remove();
                    
                    // Update the count
                    const favoritesCount = document.getElementById('favoritesCount');
                    if (favoritesCount) {
                        const currentCount = parseInt(favoritesCount.textContent);
                        favoritesCount.textContent = Math.max(0, currentCount - 1);
                    }
                    
                    // Show message if no favorites left
                    const favoritesList = document.querySelector('.favorites-list');
                    if (favoritesList && favoritesList.children.length === 0) {
                        favoritesList.innerHTML = '<div class="col-12 text-center py-5"><p class="text-muted">You have no saved domains yet.</p></div>';
                    }
                }, 300);
            }
            
            showToast('Domain removed from favorites', 'success');
        } else {
            response.json().then(errorData => {
                showToast(errorData.detail || 'Failed to remove domain from favorites', 'error');
            }).catch(() => {
                showToast('Failed to remove domain from favorites', 'error');
            });
        }
    })
    .catch(error => {
        console.error('Error removing favorite:', error);
        showToast('Failed to remove domain from favorites', 'error');
    });
}

// Make removeFromWatchlist available in the global scope
function removeFromWatchlist(watchlistId) {
    if (!confirm('Are you sure you want to remove this domain from your watchlist?')) {
        return;
    }
    
    fetch(`/watchlist/${watchlistId}`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        }
    })
    .then(response => {
        if (response.ok) {
            // Remove the card from the UI
            const card = document.querySelector(`[data-watchlist-id="${watchlistId}"]`);
            if (card) {
                card.classList.add('fade-out');
                setTimeout(() => {
                    card.remove();
                    
                    // Update the count
                    const watchlistCount = document.getElementById('watchlistCount');
                    if (watchlistCount) {
                        const currentCount = parseInt(watchlistCount.textContent);
                        watchlistCount.textContent = Math.max(0, currentCount - 1);
                    }
                    
                    // Show message if no watchlist items left
                    const watchlistList = document.querySelector('.watchlist-list');
                    if (watchlistList && watchlistList.children.length === 0) {
                        watchlistList.innerHTML = '<div class="col-12 text-center py-5"><p class="text-muted">You have no domains in your watchlist yet.</p></div>';
                    }
                }, 300);
            }
            
            showToast('Domain removed from watchlist', 'success');
        } else {
            response.json().then(errorData => {
                showToast(errorData.detail || 'Failed to remove domain from watchlist', 'error');
            }).catch(() => {
                showToast('Failed to remove domain from watchlist', 'error');
            });
        }
    })
    .catch(error => {
        console.error('Error removing from watchlist:', error);
        showToast('Failed to remove domain from watchlist', 'error');
    });
}

// Function to update the loading step
function updateLoadingStep(step) {
    // Get all loading steps
    const steps = document.querySelectorAll('.loading-step');
    
    // Mark previous steps as completed
    for (let i = 0; i < step - 1; i++) {
        if (steps[i]) {
            steps[i].classList.remove('active');
            steps[i].classList.add('completed');
        }
    }
    
    // Set current step as active
    steps.forEach((stepEl, index) => {
        if (index + 1 === step) {
            stepEl.classList.add('active');
        } else if (index + 1 > step) {
            stepEl.classList.remove('active', 'completed');
        }
    });
}

// Function to simulate loading progress
function simulateLoadingProgress() {
    // Reset all steps first
    document.querySelectorAll('.loading-step').forEach(step => {
        step.classList.remove('active', 'completed');
    });
    
    // Start with step 1 (AI name generation)
    updateLoadingStep(1);
    
    // Step 2 after 1.2 seconds (Filtering names)
    setTimeout(() => updateLoadingStep(2), 1200);
    
    // Step 3 after another 1.5 seconds (GoDaddy domain checks)
    setTimeout(() => updateLoadingStep(3), 2700);
    
    // Step 4 after another 2 seconds (Dynadot and other provider pricing)
    setTimeout(() => updateLoadingStep(4), 4700);
    
    // Step 5 after another 1.5 seconds (Calculating scores)
    setTimeout(() => updateLoadingStep(5), 6200);
    
    // Step 6 after another 1 second (Preparing results)
    setTimeout(() => updateLoadingStep(6), 7200);
}

// Function to adjust loading progress based on actual response time
function adjustLoadingProgress(responseTime) {
    // Get all loading steps
    const steps = document.querySelectorAll('.loading-step');
    const totalSteps = steps.length;
    
    console.log(`Response received in ${responseTime}ms, adjusting loading steps`);
    
    // If response was very fast (< 3s), progress quickly through steps
    if (responseTime < 3000) {
        // Quickly complete all steps
        for (let i = 0; i < totalSteps; i++) {
            setTimeout(() => {
                updateLoadingStep(i + 1);
                // Add a small delay after the last step
                if (i === totalSteps - 1) {
                    setTimeout(() => {
                        steps.forEach(step => step.classList.add('completed'));
                    }, 200);
                }
            }, i * 200);
        }
    } 
    // If response was moderate (3-6s), jump to later steps
    else if (responseTime < 6000) {
        // Jump to step 4 now (Dynadot pricing)
        updateLoadingStep(4);
        // Then to step 5 after a short delay (Calculating scores)
        setTimeout(() => updateLoadingStep(5), 300);
        // Then to final step (Preparing results)
        setTimeout(() => updateLoadingStep(6), 600);
    }
    // If response was somewhat slow (6-10s), we're already at step 4-5
    else if (responseTime < 10000) {
        // Jump to step 5 (Calculating scores)
        updateLoadingStep(5);
        // Then to final step (Preparing results)
        setTimeout(() => updateLoadingStep(6), 400);
    }
    // If response was very slow (> 10s), jump to the final step
    else {
        updateLoadingStep(6);
    }
}

// Add function to check more extensions for a domain
async function checkMoreExtensions(event, brandName) {
    event.preventDefault();
    
    console.log(`Checking more extensions for: ${brandName}`);
    
    // Get the button that was clicked
    const button = event.target.closest('button');
    if (!button) return;
    
    // Get the brand card
    const brandCard = button.closest('.brand-card');
    if (!brandCard) return;
    
    // Get the domains container
    const domainsContainer = brandCard.querySelector('.domains-container');
    if (!domainsContainer) return;
    
    // Disable the button and show loading state
    button.disabled = true;
    const originalButtonText = button.innerHTML;
    button.innerHTML = '<i class="bi bi-hourglass-split"></i> Checking...';
    
    try {
        // Get all currently displayed extensions
        const displayedExtensions = [];
        
        // Check for the .com domain in the header
        const headerDomain = brandCard.querySelector('h3');
        if (headerDomain && headerDomain.textContent.includes('.')) {
            const ext = headerDomain.textContent.split('.')[1];
            displayedExtensions.push(ext);
        }
        
        // Check for all other displayed extensions
        brandCard.querySelectorAll('.domain-card .domain-name').forEach(domainEl => {
            if (domainEl.textContent.includes('.')) {
                const ext = domainEl.textContent.split('.')[1];
                displayedExtensions.push(ext);
            }
        });
        
        console.log(`Already displayed extensions: ${displayedExtensions.join(',')}`);
        
        // Call API to check more extensions
        const response = await fetch(`/api/check-more-extensions/${brandName}?checked_extensions=${displayedExtensions.join(',')}`);
        
        if (!response.ok) {
            throw new Error(`Error: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Additional extension results:', data);
        
        // If no results, show message and hide the button
        if (Object.keys(data).length === 0) {
            button.style.display = 'none';
            showToast('No additional extensions available', 'info');
            return;
        }
        
        // Get the remaining domains container or create it
        let remainingContainer = domainsContainer.querySelector('.remaining-domains');
        if (!remainingContainer) {
            remainingContainer = document.createElement('div');
            remainingContainer.className = 'remaining-domains';
            domainsContainer.appendChild(remainingContainer);
        }
        
        // Show the container if it was hidden
        remainingContainer.style.display = 'block';
        
        // Process the results and add domain cards
        for (const [fullDomain, info] of Object.entries(data)) {
            // Skip if this domain is already displayed
            const domainName = fullDomain.split('.')[0];
            const extension = fullDomain.split('.')[1];
            
            // Check if this extension is already displayed
            if (remainingContainer.querySelector(`.domain-name[data-extension="${extension}"]`)) {
                console.log(`Extension ${extension} already displayed, skipping`);
                continue;
            }
            
            // Process price info and ensure we have a valid format
            console.log(`Processing ${fullDomain} price info:`, info);
            const processedInfo = { ...info };
            
            // Add additional logging to see what's in the data
            if (processedInfo.price_info) {
                console.log(`Price info for ${fullDomain}:`, processedInfo.price_info);
            }
            
            if (processedInfo.providers) {
                console.log(`Provider info for ${fullDomain}:`, processedInfo.providers);
                
                // If we have provider prices but no price field, set a default price
                if (!processedInfo.price || processedInfo.price === 'undefined') {
                    // Find the first provider with a valid price
                    for (const provider of ['godaddy', 'porkbun', 'namesilo', 'dynadot']) {
                        if (processedInfo.providers[provider] && !isNaN(processedInfo.providers[provider])) {
                            processedInfo.price = `$${(processedInfo.providers[provider]/1000000).toFixed(2)}`;
                            console.log(`Set price for ${fullDomain} from ${provider}: ${processedInfo.price}`);
                            break;
                        }
                    }
                }
            }
            
            // Create the domain card with the processed info
            const domainCard = createDomainCard(domainName, extension, processedInfo, false);
            
            // Add the extension data attribute to the domain name
            const domainNameEl = domainCard.querySelector('.domain-name');
            if (domainNameEl) {
                domainNameEl.setAttribute('data-extension', extension);
            }
            
            // Add the card to the container
            remainingContainer.appendChild(domainCard);
        }
        
        // Get or create the toggle button
        let toggleButton = domainsContainer.querySelector('.toggle-domains');
        if (!toggleButton) {
            toggleButton = document.createElement('button');
            toggleButton.className = 'btn btn-sm btn-outline-secondary w-100 mt-2 toggle-domains';
            toggleButton.innerHTML = `
                <span class="more-text" style="display: none;">Show More Extensions</span>
                <span class="less-text">Hide Extensions</span>
                <i class="bi bi-chevron-up"></i>
            `;
            
            toggleButton.addEventListener('click', function() {
                const remainingDomains = this.previousElementSibling;
                const moreText = this.querySelector('.more-text');
                const lessText = this.querySelector('.less-text');
                const icon = this.querySelector('i');
                
                if (remainingDomains.style.display === 'none') {
                    remainingDomains.style.display = 'block';
                    moreText.style.display = 'none';
                    lessText.style.display = 'inline';
                    icon.classList.remove('bi-chevron-down');
                    icon.classList.add('bi-chevron-up');
                } else {
                    remainingDomains.style.display = 'none';
                    moreText.style.display = 'inline';
                    lessText.style.display = 'none';
                    icon.classList.remove('bi-chevron-up');
                    icon.classList.add('bi-chevron-down');
                }
            });
            
            domainsContainer.appendChild(toggleButton);
        } else {
            // Update the count on the existing button
            const moreText = toggleButton.querySelector('.more-text');
            if (moreText) {
                const extensionCount = remainingContainer.querySelectorAll('.domain-card').length;
                moreText.textContent = `Show More Extensions (${extensionCount})`;
            }
        }
        
        // Hide the check more button
        button.style.display = 'none';
        
        // Ensure the extensions are visible if they were hidden
        if (remainingContainer && remainingContainer.style.display === 'none') {
            remainingContainer.style.display = 'block';
            
            // Also update the toggle button if it exists
            const toggleButton = domainsContainer.querySelector('.toggle-domains');
            if (toggleButton) {
                const moreText = toggleButton.querySelector('.more-text');
                const lessText = toggleButton.querySelector('.less-text');
                const icon = toggleButton.querySelector('i');
                
                if (moreText) moreText.style.display = 'none';
                if (lessText) lessText.style.display = 'inline';
                if (icon) icon.style.transform = 'rotate(180deg)';
            }
        }
        
        // Show a toast notification
        const newExtensionsCount = Object.keys(data).length;
        showToast(`Found ${newExtensionsCount} additional extensions`, 'success');
        
    } catch (error) {
        console.error('Error checking more extensions:', error);
        
        // Reset the button
        button.innerHTML = originalButtonText;
        button.disabled = false;
        
        // Show error message
        showToast('Failed to check additional extensions', 'error');
    }
}

