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
            const errorText = await response.text();
            if (response.status === 401) {
                console.error('401 Unauthorized:', errorText);
                throw new Error('Требуется авторизация. Откройте приложение через Telegram.');
            }
            if (response.status === 403 && (errorText.includes('PREMIUM') || errorText.includes('premium'))) {
                throw new Error('Требуется подписка. Оформите подписку в боте.');
            }
            throw new Error(errorText || `Ошибка: ${response.status}`);
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
        if (response.status === 403 && (text.includes('PREMIUM') || text.includes('premium'))) {
            throw new Error('Требуется подписка. Оформите подписку в боте.');
        }
        try {
            const json = JSON.parse(text);
            const msg = Array.isArray(json.detail) ? json.detail.map(d => d.msg || d).join(', ') : (json.detail || text);
            throw new Error(msg || `Ошибка: ${response.status}`);
        } catch (e) {
            if (e instanceof SyntaxError) throw new Error(text || `Ошибка: ${response.status}`);
            throw e;
        }
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
