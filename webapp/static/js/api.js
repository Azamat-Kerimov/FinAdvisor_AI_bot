/* ============================================
   API Module - HTTP Requests
   ============================================ */

const API_URL = window.location.origin;

/**
 * Get Telegram initData for authentication
 */
function getInitData() {
    // Проверяем несколько способов получения initData
    if (window.Telegram?.WebApp?.initData) {
        const initData = window.Telegram.WebApp.initData;
        console.log('initData получен из window.Telegram.WebApp.initData, длина:', initData.length);
        return initData;
    }
    
    // Альтернативный способ через initDataUnsafe (для отладки)
    if (window.Telegram?.WebApp?.initDataUnsafe) {
        console.warn('initData не найден, но initDataUnsafe доступен');
    }
    
    console.warn('initData не найден. Проверьте, что приложение открыто через Telegram.');
    return '';
}

/**
 * Make API request with authentication
 */
async function apiRequest(endpoint, options = {}) {
    const initData = getInitData();
    
    // Note: /api/stats requires auth, but we'll handle 401 gracefully
    // Public endpoints (if any) would be listed here
    const publicEndpoints = [];
    const isPublic = publicEndpoints.some(ep => endpoint.includes(ep));
    
    // Логируем для отладки
    if (!initData && !isPublic) {
        if (AppState?.isTelegram) {
            console.warn('Telegram Web App открыт, но initData отсутствует. Проверьте, что приложение открыто через Telegram.');
        } else {
            console.warn('Открыто в браузере. Некоторые функции могут не работать.');
        }
    } else if (initData) {
        console.log('initData найден, длина:', initData.length);
    }
    
    const headers = {
        'Content-Type': 'application/json',
        ...(initData && { 'init-data': initData }),
        ...options.headers
    };
    
    // Логируем заголовки для отладки (без самого initData для безопасности)
    if (initData) {
        console.log('Отправка запроса с init-data заголовком');
    } else {
        console.log('Отправка запроса БЕЗ init-data заголовка');
    }
    
    try {
        const response = await fetch(`${API_URL}${endpoint}`, {
            ...options,
            headers
        });
        
        if (!response.ok) {
            // Handle 401 (Unauthorized) gracefully
            if (response.status === 401) {
                const errorText = await response.text();
                console.error('401 Unauthorized:', errorText);
                throw new Error('Требуется авторизация. Откройте приложение через Telegram.');
            }
            const errorText = await response.text();
            throw new Error(`API error: ${response.status} - ${errorText}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API Request Error:', error);
        throw error;
    }
}

/**
 * Upload file (multipart/form-data). Не устанавливает Content-Type — браузер задаст boundary.
 */
async function uploadFile(endpoint, file) {
    const initData = getInitData();
    const formData = new FormData();
    formData.append('file', file);
    const headers = { ...(initData && { 'init-data': initData }) };
    const response = await fetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers,
        body: formData
    });
    if (!response.ok) {
        const text = await response.text();
        throw new Error(`API error: ${response.status} - ${text}`);
    }
    return await response.json();
}

// Make functions globally available
window.apiRequest = apiRequest;
window.uploadFile = uploadFile;
window.getInitData = getInitData;

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { apiRequest, getInitData };
}
