// Telegram Web App инициализация
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

// API базовый URL
const API_URL = window.location.origin;

// Получить initData для аутентификации
function getInitData() {
    return tg.initData;
}

// API запросы
async function apiRequest(endpoint, options = {}) {
    const initData = getInitData();
    const headers = {
        'Content-Type': 'application/json',
        'init-data': initData,
        ...options.headers
    };
    
    const response = await fetch(`${API_URL}${endpoint}`, {
        ...options,
        headers
    });
    
    if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
    }
    
    return response.json();
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

// Навигация
function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(screen => {
        screen.classList.remove('active');
    });
    document.getElementById(screenId).classList.add('active');
    
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
    }
}

// Статистика
async function loadStats() {
    try {
        const stats = await apiRequest('/api/stats');
        const statsCard = document.getElementById('stats-card');
        
        const income = stats.total_income || 0;
        const expense = stats.total_expense || 0;
        const balance = income - expense;
        
        statsCard.innerHTML = `
            <div style="margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <span>Доходы:</span>
                    <strong style="color: #2ecc71;">${formatMoney(income)} ₽</strong>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <span>Расходы:</span>
                    <strong style="color: #e74c3c;">${formatMoney(expense)} ₽</strong>
                </div>
                <div style="display: flex; justify-content: space-between; margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(0,0,0,0.1);">
                    <span><strong>Остаток:</strong></span>
                    <strong style="color: ${balance >= 0 ? '#2ecc71' : '#e74c3c'};">${formatMoney(balance)} ₽</strong>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Error loading stats:', error);
        document.getElementById('stats-card').innerHTML = '<div style="color: #e74c3c;">Ошибка загрузки статистики</div>';
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
    try {
        const transactions = await apiRequest('/api/transactions?limit=20');
        const list = document.getElementById('transactions-list');
        
        if (transactions.length === 0) {
            list.innerHTML = '<div style="text-align: center; color: #999; padding: 20px;">Нет транзакций</div>';
            return;
        }
        
        list.innerHTML = transactions.map(tx => {
            const amount = parseFloat(tx.amount);
            const isPositive = amount >= 0;
            const date = new Date(tx.created_at).toLocaleDateString('ru-RU');
            
            return `
                <div class="list-item">
                    <div class="list-item-header">
                        <span class="list-item-title">${tx.category || '—'}</span>
                        <span class="list-item-amount ${isPositive ? 'positive' : 'negative'}">
                            ${isPositive ? '+' : ''}${formatMoney(amount)} ₽
                        </span>
                    </div>
                    ${tx.description ? `<div style="margin-top: 4px; color: #666;">${tx.description}</div>` : ''}
                    <div class="list-item-meta">${date}</div>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Error loading transactions:', error);
    }
}

async function addTransaction() {
    const category = document.getElementById('category-select').value;
    const amount = parseFloat(document.getElementById('amount-input').value);
    const description = document.getElementById('description-input').value;
    
    if (!category || !amount || amount <= 0) {
        tg.showAlert('Заполните все поля');
        return;
    }
    
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
        
        tg.showAlert('Транзакция добавлена!');
        document.getElementById('amount-input').value = '';
        document.getElementById('description-input').value = '';
        loadTransactions();
        loadStats();
    } catch (error) {
        tg.showAlert('Ошибка при добавлении транзакции');
        console.error(error);
    }
}

// Цели
async function loadGoals() {
    try {
        const goals = await apiRequest('/api/goals');
        const list = document.getElementById('goals-list');
        
        if (goals.length === 0) {
            list.innerHTML = '<div style="text-align: center; color: #999; padding: 20px;">Нет целей</div>';
            return;
        }
        
        list.innerHTML = goals.map(goal => {
            const progress = goal.target > 0 ? (goal.current / goal.target) * 100 : 0;
            const progressPercent = Math.min(progress, 100);
            
            return `
                <div class="goal-item">
                    <div class="list-item-header">
                        <span class="list-item-title">${goal.title}</span>
                        <span class="list-item-amount">${formatMoney(goal.current)} / ${formatMoney(goal.target)} ₽</span>
                    </div>
                    <div class="goal-progress">
                        <div class="goal-progress-bar" style="width: ${progressPercent}%"></div>
                    </div>
                    ${goal.description ? `<div style="margin-top: 8px; color: #666; font-size: 14px;">${goal.description}</div>` : ''}
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Error loading goals:', error);
    }
}

function showAddGoalForm() {
    document.getElementById('add-goal-form').style.display = 'block';
}

function hideAddGoalForm() {
    document.getElementById('add-goal-form').style.display = 'none';
}

async function addGoal() {
    const title = document.getElementById('goal-title').value;
    const target = parseFloat(document.getElementById('goal-target').value);
    const description = document.getElementById('goal-description').value;
    
    if (!title || !target || target <= 0) {
        tg.showAlert('Заполните все обязательные поля');
        return;
    }
    
    try {
        await apiRequest('/api/goals', {
            method: 'POST',
            body: JSON.stringify({
                title,
                target,
                description: description || null
            })
        });
        
        tg.showAlert('Цель создана!');
        document.getElementById('goal-title').value = '';
        document.getElementById('goal-target').value = '';
        document.getElementById('goal-description').value = '';
        hideAddGoalForm();
        loadGoals();
    } catch (error) {
        tg.showAlert('Ошибка при создании цели');
        console.error(error);
    }
}

// Капитал
let currentCapitalTab = 'assets';

function switchCapitalTab(tab) {
    currentCapitalTab = tab;
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');
    loadCapital();
}

async function loadCapital() {
    try {
        if (currentCapitalTab === 'assets') {
            const assets = await apiRequest('/api/assets');
            const content = document.getElementById('capital-content');
            
            const total = assets.reduce((sum, a) => sum + (parseFloat(a.amount) || 0), 0);
            
            content.innerHTML = `
                <div class="capital-summary">
                    <div class="capital-summary-item">
                        <span>Всего активов:</span>
                        <strong style="color: #2ecc71;">${formatMoney(total)} ₽</strong>
                    </div>
                </div>
                <div class="list">
                    ${assets.map(asset => `
                        <div class="list-item">
                            <div class="list-item-header">
                                <span class="list-item-title">${asset.title}</span>
                                <span class="list-item-amount positive">${formatMoney(asset.amount || 0)} ₽</span>
                            </div>
                            <div class="list-item-meta">${asset.type}</div>
                        </div>
                    `).join('')}
                </div>
            `;
        } else {
            const liabilities = await apiRequest('/api/liabilities');
            const content = document.getElementById('capital-content');
            
            const total = liabilities.reduce((sum, l) => sum + (parseFloat(l.amount) || 0), 0);
            
            content.innerHTML = `
                <div class="capital-summary">
                    <div class="capital-summary-item">
                        <span>Всего долгов:</span>
                        <strong style="color: #e74c3c;">${formatMoney(total)} ₽</strong>
                    </div>
                </div>
                <div class="list">
                    ${liabilities.map(liab => `
                        <div class="list-item">
                            <div class="list-item-header">
                                <span class="list-item-title">${liab.title}</span>
                                <span class="list-item-amount negative">${formatMoney(liab.amount || 0)} ₽</span>
                            </div>
                            <div class="list-item-meta">${liab.type} | Платеж: ${formatMoney(liab.monthly_payment || 0)} ₽/мес</div>
                        </div>
                    `).join('')}
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading capital:', error);
    }
}

// Консультация
async function loadConsultation() {
    const content = document.getElementById('consultation-content');
    content.innerHTML = '<p>Анализирую ваши финансы...</p>';
    
    try {
        const result = await apiRequest('/api/consultation');
        content.innerHTML = `<div style="white-space: pre-wrap; line-height: 1.6;">${result.consultation}</div>`;
    } catch (error) {
        content.innerHTML = '<p style="color: #e74c3c;">Ошибка при загрузке консультации</p>';
        console.error(error);
    }
}

// Утилиты
function formatMoney(amount) {
    return new Intl.NumberFormat('ru-RU').format(Math.round(amount));
}

// Инициализация
tg.ready();
loadStats();
