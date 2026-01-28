/* ============================================
   State Module - Application State
   ============================================ */

const AppState = {
    // Current screen
    currentScreen: 'main-menu',
    
    // Current tab (for transactions, capital)
    currentTab: 'income',
    currentCapitalTab: 'assets',
    
    // Data cache
    stats: null,
    transactions: [],
    goals: [],
    assets: [],
    liabilities: [],
    
    // Telegram Web App instance
    tg: null,
    isTelegram: false,
    
    // Categories
    incomeCategories: {
        'Заработная плата': '💼',
        'Дивиденды и купоны': '📈',
        'Прочие доходы': '💰'
    },
    
    expenseCategories: {
        'Супермаркеты': '🛒',
        'Рестораны и кафе': '🍽️',
        'Транспорт': '🚗',
        'Аренда жилья': '🏠',
        'Коммунальные платежи': '💡',
        'Здоровье и красота': '💊',
        'Развлечения': '🎬',
        'Прочие расходы': '📦'
    },
    
    /**
     * Initialize Telegram Web App
     */
    initTelegram() {
        if (window.Telegram?.WebApp) {
            this.tg = window.Telegram.WebApp;
            this.isTelegram = true;
            this.tg.ready();
            this.tg.expand();
        } else {
            // Fallback for browser
            this.tg = {
                ready: () => {},
                expand: () => {},
                showAlert: (msg) => alert(msg),
                initData: '',
                HapticFeedback: {
                    impactOccurred: () => {}
                }
            };
            this.isTelegram = false;
        }
    },
    
    /**
     * Get categories for current tab
     */
    getCategories() {
        return this.currentTab === 'income' 
            ? this.incomeCategories 
            : this.expenseCategories;
    },
    
    /**
     * Haptic feedback
     */
    hapticFeedback(style = 'light') {
        if (this.tg?.HapticFeedback) {
            this.tg.HapticFeedback.impactOccurred(style);
        }
    }
};

// Initialize Telegram on load
AppState.initTelegram();

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AppState;
}
