// Telegram Web App инициализация с fallback для браузера
let tg = null;
let isTelegram = false;

if (window.Telegram && window.Telegram.WebApp) {
    tg = window.Telegram.WebApp;
    isTelegram = true;
    tg.ready();
    tg.expand();
} else {
    // Fallback для работы в обычном браузере
    tg = {
        ready: () => {},
        expand: () => {},
        showAlert: (message) => alert(message),
        initData: ''
    };
    isTelegram = false;
}

// API базовый URL
const API_URL = window.location.origin;

// Получить initData для аутентификации
function getInitData() {
    if (isTelegram && tg.initData) {
        return tg.initData;
    }
    // Для тестирования в браузере - можно использовать mock данные
    // В продакшене это должно быть только через Telegram
    return '';
}

// Показ уведомлений
function showNotification(message, type = 'info') {
    if (isTelegram && tg.showAlert) {
        tg.showAlert(message);
    } else {
        alert(message);
    }
}

// API запросы с обработкой ошибок
async function apiRequest(endpoint, options = {}) {
    const initData = getInitData();
    
    // Если нет initData и это не публичный endpoint, возвращаем ошибку
    if (!initData && !endpoint.includes('/api/stats')) {
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

// Категории
const INCOME_CATEGORIES = {
    'Заработная плата': '💼',
    'Дивиденды и купоны': '📈',
    'Прочие доходы': '💰'
};

const EXPENSE_CATEGORIES = {
    'Супермаркеты': '🛒',
    'Рестораны и кафе': '🍽️',
    'Транспорт': '🚗',
    'Аренда жилья': '🏠',
    'Коммунальные платежи': '💡',
    'Здоровье и красота': '💊',
    'Развлечения': '🎬',
    'Прочие расходы': '📦'
};

let currentTab = 'income';

// Индикатор загрузки
function showLoading(elementId, message = 'Загрузка...') {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = `
            <div style="text-align: center; padding: 20px;">
                <div class="spinner"></div>
                <p style="margin-top: 12px; color: var(--tg-theme-hint-color);">${message}</p>
            </div>
        `;
    }
}

function hideLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element && element.innerHTML.includes('spinner')) {
        // Loading будет заменен контентом
    }
}

// Навигация
function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(screen => {
        screen.classList.remove('active');
    });
    const targetScreen = document.getElementById(screenId);
    if (targetScreen) {
        targetScreen.classList.add('active');
    }
    
    // Загружаем данные при открытии экрана
    if (screenId === 'main-menu') {
        loadStats();
    } else if (screenId === 'transactions') {
        loadTransactions();
        loadCategories();
    } else if (screenId === 'goals') {
        loadGoals();
    } else if (screenId === 'capital') {
        loadCapital();
    } else if (screenId === 'consultation') {
        loadConsultation();
    } else if (screenId === 'reports') {
        loadReports();
    }
}

// Статистика
async function loadStats() {
    const statsCard = document.getElementById('stats-card');
    showLoading('stats-card', 'Загрузка статистики...');
    
    try {
        const stats = await apiRequest('/api/stats');
        
        const income = stats.total_income || 0;
        const expense = stats.total_expense || 0;
        const balance = income - expense;
        
        statsCard.innerHTML = `
            <div style="margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px; align-items: center;">
                    <span style="font-size: 14px;">Доходы:</span>
                    <strong style="color: #2ecc71; font-size: 16px;">${formatMoney(income)} ₽</strong>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px; align-items: center;">
                    <span style="font-size: 14px;">Расходы:</span>
                    <strong style="color: #e74c3c; font-size: 16px;">${formatMoney(expense)} ₽</strong>
                </div>
                <div style="display: flex; justify-content: space-between; margin-top: 12px; padding-top: 12px; border-top: 2px solid rgba(0,0,0,0.1); align-items: center;">
                    <span style="font-weight: 600; font-size: 16px;">Остаток:</span>
                    <strong style="color: ${balance >= 0 ? '#2ecc71' : '#e74c3c'}; font-size: 18px;">${formatMoney(balance)} ₽</strong>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Error loading stats:', error);
        statsCard.innerHTML = `
            <div style="text-align: center; padding: 20px; color: #e74c3c;">
                <p>⚠️ Ошибка загрузки статистики</p>
                <p style="font-size: 12px; margin-top: 8px; color: var(--tg-theme-hint-color);">
                    ${!isTelegram ? 'Откройте приложение через Telegram для доступа к данным' : 'Попробуйте обновить страницу'}
                </p>
            </div>
        `;
    }
}

// Транзакции
function switchTab(type) {
    currentTab = type;
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    event.target.classList.add('active');
    loadCategories();
}

function loadCategories() {
    const select = document.getElementById('category-select');
    if (!select) return;
    
    const categories = currentTab === 'income' ? INCOME_CATEGORIES : EXPENSE_CATEGORIES;
    
    select.innerHTML = '<option value="">Выберите категорию</option>';
    for (const [cat, emoji] of Object.entries(categories)) {
        const option = document.createElement('option');
        option.value = cat;
        option.textContent = `${emoji} ${cat}`;
        select.appendChild(option);
    }
}

async function loadTransactions() {
    const list = document.getElementById('transactions-list');
    if (!list) return;
    
    showLoading('transactions-list', 'Загрузка транзакций...');
    
    try {
        const transactions = await apiRequest('/api/transactions?limit=20');
        
        if (transactions.length === 0) {
            list.innerHTML = '<div style="text-align: center; color: var(--tg-theme-hint-color); padding: 40px 20px;">📝 Нет транзакций</div>';
            return;
        }
        
        list.innerHTML = transactions.map(tx => {
            const amount = parseFloat(tx.amount);
            const isPositive = amount >= 0;
            const date = new Date(tx.created_at).toLocaleDateString('ru-RU', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric'
            });
            
            return `
                <div class="list-item">
                    <div class="list-item-header">
                        <span class="list-item-title">${tx.category || '—'}</span>
                        <span class="list-item-amount ${isPositive ? 'positive' : 'negative'}">
                            ${isPositive ? '+' : ''}${formatMoney(Math.abs(amount))} ₽
                        </span>
                    </div>
                    ${tx.description ? `<div style="margin-top: 6px; color: var(--tg-theme-hint-color); font-size: 14px;">${escapeHtml(tx.description)}</div>` : ''}
                    <div class="list-item-meta">📅 ${date}</div>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Error loading transactions:', error);
        list.innerHTML = `
            <div style="text-align: center; padding: 20px; color: #e74c3c;">
                <p>⚠️ Ошибка загрузки транзакций</p>
                <p style="font-size: 12px; margin-top: 8px; color: var(--tg-theme-hint-color);">${error.message}</p>
            </div>
        `;
    }
}

async function addTransaction() {
    const category = document.getElementById('category-select')?.value;
    const amountInput = document.getElementById('amount-input');
    const descriptionInput = document.getElementById('description-input');
    const amount = parseFloat(amountInput?.value);
    const description = descriptionInput?.value || '';
    
    if (!category || !amount || amount <= 0) {
        showNotification('Заполните все обязательные поля', 'error');
        return;
    }
    
    const btn = event.target;
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Добавление...';
    
    try {
        const finalAmount = currentTab === 'expense' ? -amount : amount;
        await apiRequest('/api/transactions', {
            method: 'POST',
            body: JSON.stringify({
                amount: finalAmount,
                category,
                description: description || null
            })
        });
        
        showNotification('✅ Транзакция добавлена!');
        amountInput.value = '';
        descriptionInput.value = '';
        loadTransactions();
        loadStats();
    } catch (error) {
        showNotification('❌ Ошибка при добавлении транзакции', 'error');
        console.error(error);
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

// Цели
async function loadGoals() {
    const list = document.getElementById('goals-list');
    if (!list) return;
    
    showLoading('goals-list', 'Загрузка целей...');
    
    try {
        const goals = await apiRequest('/api/goals');
        
        if (goals.length === 0) {
            list.innerHTML = '<div style="text-align: center; color: var(--tg-theme-hint-color); padding: 40px 20px;">🎯 Нет целей<br><small style="font-size: 12px;">Создайте первую цель</small></div>';
            return;
        }
        
        list.innerHTML = goals.map(goal => {
            const progress = goal.target > 0 ? (goal.current / goal.target) * 100 : 0;
            const progressPercent = Math.min(progress, 100);
            
            return `
                <div class="goal-item">
                    <div class="list-item-header">
                        <span class="list-item-title">${escapeHtml(goal.title)}</span>
                        <span class="list-item-amount">${formatMoney(goal.current)} / ${formatMoney(goal.target)} ₽</span>
                    </div>
                    <div style="margin-top: 8px; font-size: 12px; color: var(--tg-theme-hint-color);">
                        Прогресс: ${Math.round(progressPercent)}%
                    </div>
                    <div class="goal-progress">
                        <div class="goal-progress-bar" style="width: ${progressPercent}%"></div>
                    </div>
                    ${goal.description ? `<div style="margin-top: 8px; color: var(--tg-theme-hint-color); font-size: 14px;">${escapeHtml(goal.description)}</div>` : ''}
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Error loading goals:', error);
        list.innerHTML = `
            <div style="text-align: center; padding: 20px; color: #e74c3c;">
                <p>⚠️ Ошибка загрузки целей</p>
            </div>
        `;
    }
}

function showAddGoalForm() {
    const form = document.getElementById('add-goal-form');
    if (form) {
        form.style.display = 'block';
        form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

function hideAddGoalForm() {
    const form = document.getElementById('add-goal-form');
    if (form) {
        form.style.display = 'none';
        // Очищаем поля
        document.getElementById('goal-title').value = '';
        document.getElementById('goal-target').value = '';
        document.getElementById('goal-description').value = '';
    }
}

async function addGoal() {
    const title = document.getElementById('goal-title')?.value;
    const target = parseFloat(document.getElementById('goal-target')?.value);
    const description = document.getElementById('goal-description')?.value || '';
    
    if (!title || !target || target <= 0) {
        showNotification('Заполните все обязательные поля', 'error');
        return;
    }
    
    const btn = event.target;
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Создание...';
    
    try {
        await apiRequest('/api/goals', {
            method: 'POST',
            body: JSON.stringify({
                title,
                target,
                description: description || null
            })
        });
        
        showNotification('✅ Цель создана!');
        hideAddGoalForm();
        loadGoals();
    } catch (error) {
        showNotification('❌ Ошибка при создании цели', 'error');
        console.error(error);
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

// Капитал
let currentCapitalTab = 'assets';

function switchCapitalTab(tab) {
    currentCapitalTab = tab;
    const tabs = document.querySelectorAll('#capital .tab');
    tabs.forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');
    loadCapital();
}

async function loadCapital() {
    const content = document.getElementById('capital-content');
    if (!content) return;
    
    showLoading('capital-content', 'Загрузка данных...');
    
    try {
        if (currentCapitalTab === 'assets') {
            const assets = await apiRequest('/api/assets');
            
            const total = assets.reduce((sum, a) => sum + (parseFloat(a.amount) || 0), 0);
            
            content.innerHTML = `
                <div class="capital-summary">
                    <div class="capital-summary-item">
                        <span>Всего активов:</span>
                        <strong style="color: #2ecc71; font-size: 18px;">${formatMoney(total)} ₽</strong>
                    </div>
                </div>
                <div class="list">
                    ${assets.length > 0 ? assets.map(asset => `
                        <div class="list-item">
                            <div class="list-item-header">
                                <span class="list-item-title">${escapeHtml(asset.title)}</span>
                                <span class="list-item-amount positive">${formatMoney(asset.amount || 0)} ₽</span>
                            </div>
                            <div class="list-item-meta">${asset.type || '—'}</div>
                        </div>
                    `).join('') : '<div style="text-align: center; padding: 20px; color: var(--tg-theme-hint-color);">Нет активов</div>'}
                </div>
            `;
        } else {
            const liabilities = await apiRequest('/api/liabilities');
            
            const total = liabilities.reduce((sum, l) => sum + (parseFloat(l.amount) || 0), 0);
            
            content.innerHTML = `
                <div class="capital-summary">
                    <div class="capital-summary-item">
                        <span>Всего долгов:</span>
                        <strong style="color: #e74c3c; font-size: 18px;">${formatMoney(total)} ₽</strong>
                    </div>
                </div>
                <div class="list">
                    ${liabilities.length > 0 ? liabilities.map(liab => `
                        <div class="list-item">
                            <div class="list-item-header">
                                <span class="list-item-title">${escapeHtml(liab.title)}</span>
                                <span class="list-item-amount negative">${formatMoney(liab.amount || 0)} ₽</span>
                            </div>
                            <div class="list-item-meta">${liab.type || '—'} | Платеж: ${formatMoney(liab.monthly_payment || 0)} ₽/мес</div>
                        </div>
                    `).join('') : '<div style="text-align: center; padding: 20px; color: var(--tg-theme-hint-color);">Нет долгов</div>'}
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading capital:', error);
        content.innerHTML = `
            <div style="text-align: center; padding: 20px; color: #e74c3c;">
                <p>⚠️ Ошибка загрузки данных</p>
            </div>
        `;
    }
}

// Отчеты
async function loadReports() {
    const content = document.getElementById('reports-content');
    if (!content) return;
    
    content.innerHTML = `
        <div style="text-align: center; padding: 40px 20px;">
            <p style="font-size: 18px; margin-bottom: 12px;">📊 Отчеты</p>
            <p style="color: var(--tg-theme-hint-color); font-size: 14px;">
                Функция отчетов доступна в Telegram боте
            </p>
            <p style="margin-top: 20px; font-size: 12px; color: var(--tg-theme-hint-color);">
                Используйте команду /reports в боте для получения детальных отчетов
            </p>
        </div>
    `;
}

// Консультация
async function loadConsultation() {
    const content = document.getElementById('consultation-content');
    if (!content) return;
    
    showLoading('consultation-content', '🤔 Анализирую ваши финансы...');
    
    try {
        const result = await apiRequest('/api/consultation');
        const consultation = result.consultation || 'Консультация недоступна';
        
        // Конвертируем Markdown в HTML (простая версия)
        const html = consultation
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/^### (.*$)/gim, '<h3>$1</h3>')
            .replace(/^## (.*$)/gim, '<h2>$1</h2>')
            .replace(/^# (.*$)/gim, '<h1>$1</h1>')
            .replace(/^• (.*$)/gim, '<li>$1</li>')
            .replace(/^(\d+)️⃣ (.*$)/gim, '<h3>$1. $2</h3>')
            .replace(/\n/g, '<br>');
        
        content.innerHTML = `
            <div style="white-space: pre-wrap; line-height: 1.8; font-size: 15px;">
                ${html}
            </div>
        `;
    } catch (error) {
        console.error('Error loading consultation:', error);
        content.innerHTML = `
            <div style="text-align: center; padding: 20px; color: #e74c3c;">
                <p>⚠️ Ошибка при загрузке консультации</p>
                <p style="font-size: 12px; margin-top: 8px; color: var(--tg-theme-hint-color);">
                    ${!isTelegram ? 'Откройте приложение через Telegram' : 'Попробуйте позже'}
                </p>
            </div>
        `;
    }
}

// Утилиты
function formatMoney(amount) {
    return new Intl.NumberFormat('ru-RU').format(Math.round(amount));
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    // Загружаем статистику при загрузке главной страницы
    if (document.getElementById('main-menu')?.classList.contains('active')) {
        loadStats();
    }
    
    // Предупреждение для пользователей, открывших в браузере
    if (!isTelegram) {
        console.warn('Приложение открыто в браузере. Для полного функционала откройте через Telegram.');
    }
});

// Инициализация Telegram Web App
if (tg && tg.ready) {
    tg.ready();
}
