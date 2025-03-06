// Trademark check functionality
async function checkTrademark(event, brandName) {
    event.preventDefault();
    
    const button = event.target.closest('.trademark-btn');
    const resultContainer = event.target.closest('.brand-card').querySelector('.trademark-result');
    
    try {
        // Show loading state
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
        
        const response = await fetch(`/check-trademark/${brandName}`);
        const data = await response.json();
        
        if (response.ok) {
            // Create result HTML
            let resultHTML = '';
            if (data.has_trademark) {
                resultHTML = `
                    <div class="alert alert-warning mt-2">
                        <h6 class="mb-1"><i class="bi bi-exclamation-triangle"></i> Potential Trademark Matches Found</h6>
                        <p class="small mb-1">Found ${data.total_matches} potential trademark match(es).</p>
                        <div class="trademark-details small">
                            ${data.matches.map(match => `
                                <div class="trademark-match mt-2 p-2 border rounded">
                                    <div><strong>Mark:</strong> ${match.mark_text}</div>
                                    <div><strong>Owner:</strong> ${match.owner || 'N/A'}</div>
                                    <div><strong>Status:</strong> ${match.status}</div>
                                    <div><strong>Registration:</strong> ${match.registration_number || 'Pending'}</div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `;
            } else {
                resultHTML = `
                    <div class="alert alert-success mt-2">
                        <i class="bi bi-check-circle"></i> No exact trademark matches found.
                        <p class="small mb-0">Note: This is not legal advice. Consult a trademark attorney for comprehensive analysis.</p>
                    </div>
                `;
            }
            
            resultContainer.innerHTML = resultHTML;
        } else {
            throw new Error(data.detail || 'Failed to check trademark');
        }
    } catch (error) {
        console.error('Error checking trademark:', error);
        resultContainer.innerHTML = `
            <div class="alert alert-danger mt-2">
                <i class="bi bi-x-circle"></i> Error checking trademark status.
                <p class="small mb-0">Please try again later.</p>
            </div>
        `;
    } finally {
        // Restore button state
        button.disabled = false;
        button.innerHTML = '<i class="bi bi-bank"></i> Check Trademark';
    }
}

// Make the function available globally
window.checkTrademark = checkTrademark; 