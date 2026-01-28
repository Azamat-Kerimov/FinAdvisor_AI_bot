/* ============================================
   UI Module - UI Helpers & Components
   ============================================ */

/**
 * Show notification (Telegram or fallback)
 */
function showNotification(message, type = 'info') {
    const tg = window.Telegram?.WebApp;
    if (tg?.showAlert) {
        tg.showAlert(message);
    } else {
        alert(message);
    }
    
    // Haptic feedback for Telegram
    if (tg?.HapticFeedback) {
        tg.HapticFeedback.impactOccurred('light');
    }
}

/**
 * Show loading indicator
 */
function showLoading(elementId, message = 'Загрузка...') {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    element.innerHTML = `
        <div class="loading">
            <div class="spinner"></div>
            <p>${escapeHtml(message)}</p>
        </div>
    `;
}

/**
 * Show skeleton loader
 */
function showSkeleton(elementId, count = 3) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    const skeletons = Array(count).fill(0).map(() => `
        <div class="skeleton skeleton-card"></div>
    `).join('');
    
    element.innerHTML = skeletons;
}

/**
 * Format money with spaces
 */
function formatMoney(amount) {
    return new Intl.NumberFormat('ru-RU').format(Math.round(amount));
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (text == null) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

/**
 * Convert Markdown to HTML (simple version)
 */
function markdownToHtml(markdown) {
    if (!markdown) return '';
    
    return markdown
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        .replace(/^• (.*$)/gim, '<li>$1</li>')
        .replace(/^(\d+)️⃣ (.*$)/gim, '<h3>$1. $2</h3>')
        .replace(/\n/g, '<br>');
}

/**
 * Format date
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
    });
}

/**
 * Button loading state
 */
function setButtonLoading(button, loading = true) {
    if (!button) return;
    
    if (loading) {
        button.classList.add('btn-loading');
        button.disabled = true;
        button.dataset.originalText = button.textContent;
        button.textContent = 'Загрузка...';
    } else {
        button.classList.remove('btn-loading');
        button.disabled = false;
        if (button.dataset.originalText) {
            button.textContent = button.dataset.originalText;
        }
    }
}

/**
 * Show empty state
 */
function showEmptyState(elementId, icon, title, text) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    element.innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon">${icon}</div>
            <div class="empty-state-title">${escapeHtml(title)}</div>
            <div class="empty-state-text">${escapeHtml(text)}</div>
        </div>
    `;
}

// Make functions globally available for inline handlers
window.showNotification = showNotification;
window.showLoading = showLoading;
window.showSkeleton = showSkeleton;
window.formatMoney = formatMoney;
window.escapeHtml = escapeHtml;
window.markdownToHtml = markdownToHtml;
window.formatDate = formatDate;
window.setButtonLoading = setButtonLoading;
window.showEmptyState = showEmptyState;

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        showNotification,
        showLoading,
        showSkeleton,
        formatMoney,
        escapeHtml,
        markdownToHtml,
        formatDate,
        setButtonLoading,
        showEmptyState
    };
}
