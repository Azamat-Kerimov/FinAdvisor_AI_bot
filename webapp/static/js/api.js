/* ============================================
   API Module - HTTP Requests
   ============================================ */

const API_URL = window.location.origin;

/**
 * Get Telegram initData for authentication
 */
function getInitData() {
    if (window.Telegram?.WebApp?.initData) {
        return window.Telegram.WebApp.initData;
    }
    return '';
}

/**
 * Make API request with authentication
 */
async function apiRequest(endpoint, options = {}) {
    const initData = getInitData();
    
    // Public endpoints don't require auth
    const publicEndpoints = ['/api/stats'];
    const isPublic = publicEndpoints.some(ep => endpoint.includes(ep));
    
    if (!initData && !isPublic) {
        throw new Error('Требуется авторизация. Откройте приложение через Telegram.');
    }
    
    const headers = {
        'Content-Type': 'application/json',
        ...(initData && { 'init-data': initData }),
        ...options.headers
    };
    
    try {
        const response = await fetch(`${API_URL}${endpoint}`, {
            ...options,
            headers
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`API error: ${response.status} - ${errorText}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API Request Error:', error);
        throw error;
    }
}

// Make functions globally available
window.apiRequest = apiRequest;
window.getInitData = getInitData;

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { apiRequest, getInitData };
}
