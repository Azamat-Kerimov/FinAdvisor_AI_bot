/* ============================================
   Main Application - Screen Management & Data Loading
   ============================================ */

// Import modules (in browser, they're loaded via script tags)
// In production, use a bundler or load them in order

/**
 * Show screen with animation
 */
function showScreen(screenId) {
    AppState.hapticFeedback('light');
    
    // Hide all screens
    document.querySelectorAll('.screen').forEach(screen => {
        screen.classList.remove('active');
    });
    
    // Show target screen
    const targetScreen = document.getElementById(screenId);
    if (targetScreen) {
        targetScreen.classList.add('active');
        AppState.currentScreen = screenId;
        
        // Load data when screen is shown
        loadScreenData(screenId);
    }
    
    // Update bottom navigation
    updateBottomNav(screenId);
    
    // Show/hide FAB button
    const fab = document.getElementById('fab-add-transaction');
    if (fab) {
        fab.style.display = screenId === 'transactions' ? 'flex' : 'none';
    }
}
// Export immediately
window.showScreen = showScreen;

/**
 * Load data for specific screen
 */
function loadScreenData(screenId) {
    switch (screenId) {
        case 'main-menu':
            loadStats();
            break;
        case 'transactions':
            loadTransactions();
            loadCategories();
            break;
        case 'goals':
            loadGoals();
            break;
        case 'capital':
            loadCapital();
            break;
        case 'consultation':
            loadConsultation();
            break;
        case 'reports':
            loadReports();
            break;
    }
}

/**
 * Update bottom navigation active state
 */
function updateBottomNav(screenId) {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.screen === screenId) {
            item.classList.add('active');
        }
    });
}

/**
 * Switch tab (income/expense, assets/liabilities)
 */
function switchTab(type) {
    AppState.currentTab = type;
    AppState.hapticFeedback('light');
    
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
        if (tab.dataset.tab === type) {
            tab.classList.add('active');
        }
    });
    
    loadCategories();
    loadTransactions();
}
// Export immediately
window.switchTab = switchTab;

function switchCapitalTab(tab) {
    AppState.currentCapitalTab = tab;
    AppState.hapticFeedback('light');
    
    document.querySelectorAll('#capital .tab').forEach(t => {
        t.classList.remove('active');
        if (t.dataset.tab === tab) {
            t.classList.add('active');
        }
    });
    
    loadCapital();
}
// Export immediately
window.switchCapitalTab = switchCapitalTab;

// ========== Stats / Main Menu ==========

async function loadStats() {
    const statsCard = document.getElementById('stats-card');
    if (!statsCard) return;
    
    showSkeleton('stats-card', 3);
    
    try {
        const [stats, goals, assets, liabilities] = await Promise.all([
            apiRequest('/api/stats'),
            apiRequest('/api/goals'),
            apiRequest('/api/assets'),
            apiRequest('/api/liabilities')
        ]);
        
        AppState.stats = stats;
        AppState.goals = goals;
        AppState.assets = assets;
        AppState.liabilities = liabilities;
        
        const income = stats.total_income || 0;
        const expense = stats.total_expense || 0;
        const balance = income - expense;
        
        // Капитал
        const totalAssets = assets.reduce((sum, a) => sum + (parseFloat(a.amount) || 0), 0);
        const totalLiabs = liabilities.reduce((sum, l) => sum + (parseFloat(l.amount) || 0), 0);
        const netCapital = totalAssets - totalLiabs;
        
        // Цели (первые 3)
        const goalsHtml = goals.slice(0, 3).map(g => {
            const progress = g.target > 0 ? Math.min(100, (g.current / g.target) * 100) : 0;
            return `
                <div class="goal-item">
                    <div class="goal-title">${escapeHtml(g.title)}</div>
                    <div class="goal-progress">
                        <div class="goal-progress-bar">
                            <div class="goal-progress-fill" style="width: ${progress}%"></div>
                        </div>
                        <div class="goal-progress-text">${formatMoney(g.current)} / ${formatMoney(g.target)} ₽</div>
                    </div>
                </div>
            `;
        }).join('');
        
        statsCard.innerHTML = `
            <div class="balance-card">
                <div class="balance-label">Баланс за месяц</div>
                <div class="balance-value">${formatMoney(balance)} ₽</div>
                <div class="balance-stats">
                    <div class="balance-stat-item">
                        <div class="balance-stat-label">Доходы</div>
                        <div class="balance-stat-value" style="color: #10B981;">+${formatMoney(income)} ₽</div>
                    </div>
                    <div class="balance-stat-item">
                        <div class="balance-stat-label">Расходы</div>
                        <div class="balance-stat-value" style="color: #EF4444;">-${formatMoney(expense)} ₽</div>
                    </div>
                </div>
            </div>
            
            ${goals.length > 0 ? `
            <div class="card stat-card">
                <div class="card-header">
                    <h3>🎯 Цели</h3>
                    ${goals.length > 3 ? `<a href="#" onclick="showScreen('goals'); return false;" style="color: #4F46E5; text-decoration: none; font-size: 14px;">Все цели</a>` : ''}
                </div>
                <div class="goals-preview">
                    ${goalsHtml}
                </div>
            </div>
            ` : ''}
            
            <div class="card stat-card">
                <div class="card-header">
                    <h3>💼 Капитал</h3>
                </div>
                <div class="capital-summary">
                    <div class="capital-item">
                        <div class="capital-label">Активы</div>
                        <div class="capital-value" style="color: #10B981;">${formatMoney(totalAssets)} ₽</div>
                    </div>
                    <div class="capital-item">
                        <div class="capital-label">Долги</div>
                        <div class="capital-value" style="color: #EF4444;">${formatMoney(totalLiabs)} ₽</div>
                    </div>
                    <div class="capital-item" style="border-top: 1px solid #E5E7EB; padding-top: 12px; margin-top: 12px;">
                        <div class="capital-label" style="font-weight: 600;">Чистый капитал</div>
                        <div class="capital-value" style="font-weight: 600; color: ${netCapital >= 0 ? '#10B981' : '#EF4444'};">${formatMoney(netCapital)} ₽</div>
                    </div>
                </div>
            </div>
            
            <div class="quick-actions">
                <button class="quick-action-btn" onclick="showAddTransactionForm('income')">
                    <span class="quick-action-icon">💰</span>
                    <span class="quick-action-label">Добавить доход</span>
                </button>
                <button class="quick-action-btn" onclick="showAddTransactionForm('expense')">
                    <span class="quick-action-icon">💸</span>
                    <span class="quick-action-label">Добавить расход</span>
                </button>
            </div>
        `;
    } catch (error) {
        console.error('Error loading stats:', error);
        
        // Если ошибка авторизации и открыто через Telegram, показываем более понятное сообщение
        if (error.message && error.message.includes('авторизация')) {
            statsCard.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">🔐</div>
                    <div class="empty-state-title">Требуется авторизация</div>
                    <div class="empty-state-text">Откройте приложение через Telegram для доступа к вашей статистике</div>
                </div>
            `;
        } else {
            statsCard.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">⚠️</div>
                    <div class="empty-state-title">Ошибка загрузки</div>
                    <div class="empty-state-text">${AppState.isTelegram ? 'Попробуйте обновить страницу' : 'Откройте приложение через Telegram'}</div>
                </div>
            `;
        }
    }
}

// ========== Transactions ==========

function loadCategories() {
    const select = document.getElementById('category-select');
    if (!select) return;
    
    const categories = AppState.getCategories();
    
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
    
    showSkeleton('transactions-list', 5);
    
    try {
        const transactions = await apiRequest('/api/transactions?limit=50');
        AppState.transactions = transactions;
        
        // Filter by current tab
        const filtered = transactions.filter(tx => {
            const amount = parseFloat(tx.amount);
            if (AppState.currentTab === 'income') {
                return amount >= 0;
            } else {
                return amount < 0;
            }
        });
        
        if (filtered.length === 0) {
            showEmptyState(
                'transactions-list',
                '📝',
                'Нет транзакций',
                `Добавьте первую ${AppState.currentTab === 'income' ? 'доход' : 'расход'}`
            );
            return;
        }
        
        list.innerHTML = filtered.map(tx => {
            const amount = parseFloat(tx.amount);
            const isPositive = amount >= 0;
            const absAmount = Math.abs(amount);
            const categories = AppState.getCategories();
            const emoji = categories[tx.category] || '💰';
            
            return `
                <div class="transaction-card slide-up">
                    <div class="transaction-icon ${isPositive ? 'income' : 'expense'}">
                        ${emoji}
                    </div>
                    <div class="transaction-content">
                        <div class="transaction-title">${escapeHtml(tx.category || '—')}</div>
                        <div class="transaction-meta">${formatDate(tx.created_at)}</div>
                        ${tx.description ? `<div class="transaction-meta" style="margin-top: 4px;">${escapeHtml(tx.description)}</div>` : ''}
                    </div>
                    <div class="transaction-amount ${isPositive ? 'positive' : 'negative'}">
                        ${isPositive ? '+' : ''}${formatMoney(absAmount)} ₽
                    </div>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Error loading transactions:', error);
        list.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">⚠️</div>
                <div class="empty-state-title">Ошибка загрузки</div>
                <div class="empty-state-text">${error.message}</div>
            </div>
        `;
    }
}

function showAddTransactionForm(type) {
    AppState.currentTab = type;
    showScreen('transactions');
    
    // Switch to correct tab
    setTimeout(() => {
        const tab = document.querySelector(`.tab[data-tab="${type}"]`);
        if (tab) {
            tab.click();
        }
        
        // Scroll to form
        const form = document.getElementById('transaction-form');
        if (form) {
            form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }, 100);
}
// Export immediately
window.showAddTransactionForm = showAddTransactionForm;

async function addTransaction() {
    const category = document.getElementById('category-select')?.value;
    const amountInput = document.getElementById('amount-input');
    const descriptionInput = document.getElementById('description-input');
    const amount = parseFloat(amountInput?.value);
    const description = descriptionInput?.value?.trim() || '';
    
    if (!category || !amount || amount <= 0) {
        showNotification('Заполните все обязательные поля', 'error');
        AppState.hapticFeedback('medium');
        return;
    }
    
    const btn = event.target;
    setButtonLoading(btn, true);
    AppState.hapticFeedback('light');
    
    try {
        const finalAmount = AppState.currentTab === 'expense' ? -amount : amount;
        await apiRequest('/api/transactions', {
            method: 'POST',
            body: JSON.stringify({
                amount: finalAmount,
                category,
                description: description || null
            })
        });
        
        showNotification('✅ Транзакция добавлена!');
        AppState.hapticFeedback('medium');
        
        amountInput.value = '';
        descriptionInput.value = '';
        
        loadTransactions();
        loadStats();
    } catch (error) {
        showNotification('❌ Ошибка при добавлении транзакции', 'error');
        AppState.hapticFeedback('heavy');
        console.error(error);
    } finally {
        setButtonLoading(btn, false);
    }
}
// Export immediately
window.addTransaction = addTransaction;

// ========== Goals ==========

async function loadGoals() {
    const list = document.getElementById('goals-list');
    if (!list) return;
    
    showSkeleton('goals-list', 3);
    
    try {
        const goals = await apiRequest('/api/goals');
        AppState.goals = goals;
        
        if (goals.length === 0) {
            showEmptyState(
                'goals-list',
                '🎯',
                'Нет целей',
                'Создайте первую финансовую цель'
            );
            return;
        }
        
        list.innerHTML = goals.map(goal => {
            const progress = goal.target > 0 ? (goal.current / goal.target) * 100 : 0;
            const progressPercent = Math.min(progress, 100);
            
            return `
                <div class="goal-card slide-up">
                    <div class="goal-header">
                        <div class="goal-title">${escapeHtml(goal.title)}</div>
                        <div class="goal-amount">${formatMoney(goal.current)} / ${formatMoney(goal.target)} ₽</div>
                    </div>
                    <div class="goal-progress">
                        <div class="goal-progress-bar" style="width: ${progressPercent}%"></div>
                    </div>
                    <div class="goal-progress-text">Прогресс: ${Math.round(progressPercent)}%</div>
                    ${goal.description ? `<div style="margin-top: 12px; color: var(--text-secondary); font-size: 14px;">${escapeHtml(goal.description)}</div>` : ''}
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Error loading goals:', error);
        showEmptyState(
            'goals-list',
            '⚠️',
            'Ошибка загрузки',
            error.message
        );
    }
}

function showAddGoalForm() {
    const form = document.getElementById('add-goal-form');
    if (form) {
        form.style.display = 'block';
        form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        AppState.hapticFeedback('light');
    }
}
// Export immediately
window.showAddGoalForm = showAddGoalForm;

function hideAddGoalForm() {
    const form = document.getElementById('add-goal-form');
    if (form) {
        form.style.display = 'none';
        document.getElementById('goal-title').value = '';
        document.getElementById('goal-target').value = '';
        document.getElementById('goal-description').value = '';
    }
}
// Export immediately
window.hideAddGoalForm = hideAddGoalForm;

async function addGoal() {
    const title = document.getElementById('goal-title')?.value?.trim();
    const target = parseFloat(document.getElementById('goal-target')?.value);
    const description = document.getElementById('goal-description')?.value?.trim() || '';
    
    if (!title || !target || target <= 0) {
        showNotification('Заполните все обязательные поля', 'error');
        AppState.hapticFeedback('medium');
        return;
    }
    
    const btn = event.target;
    setButtonLoading(btn, true);
    AppState.hapticFeedback('light');
    
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
        AppState.hapticFeedback('medium');
        
        hideAddGoalForm();
        loadGoals();
    } catch (error) {
        showNotification('❌ Ошибка при создании цели', 'error');
        AppState.hapticFeedback('heavy');
        console.error(error);
    } finally {
        setButtonLoading(btn, false);
    }
}
// Export immediately
window.addGoal = addGoal;

// ========== Capital ==========

async function loadCapital() {
    const content = document.getElementById('capital-content');
    if (!content) return;
    
    showSkeleton('capital-content', 3);
    
    try {
        if (AppState.currentCapitalTab === 'assets') {
            const assets = await apiRequest('/api/assets');
            AppState.assets = assets;
            
            const total = assets.reduce((sum, a) => sum + (parseFloat(a.amount) || 0), 0);
            
            if (assets.length === 0) {
                content.innerHTML = `
                    <div class="capital-summary">
                        <div class="capital-summary-item">
                            <span>Всего активов:</span>
                            <strong style="color: var(--accent); font-size: 18px;">${formatMoney(total)} ₽</strong>
                        </div>
                    </div>
                    <div class="list">
                        <div class="empty-state">
                            <div class="empty-state-icon">💼</div>
                            <div class="empty-state-title">Нет активов</div>
                            <div class="empty-state-text">Добавьте информацию о ваших активах</div>
                        </div>
                    </div>
                `;
            } else {
                content.innerHTML = `
                    <div class="capital-summary">
                        <div class="capital-summary-item">
                            <span>Всего активов:</span>
                            <strong style="color: var(--accent); font-size: 18px;">${formatMoney(total)} ₽</strong>
                        </div>
                    </div>
                    <div class="list">
                        ${assets.map(asset => `
                            <div class="transaction-card slide-up">
                                <div class="transaction-icon income">💼</div>
                                <div class="transaction-content">
                                    <div class="transaction-title">${escapeHtml(asset.title)}</div>
                                    <div class="transaction-meta">${escapeHtml(asset.type || '—')}</div>
                                </div>
                                <div class="transaction-amount positive">${formatMoney(asset.amount || 0)} ₽</div>
                            </div>
                        `).join('')}
                    </div>
                `;
            }
        } else {
            const liabilities = await apiRequest('/api/liabilities');
            AppState.liabilities = liabilities;
            
            const total = liabilities.reduce((sum, l) => sum + (parseFloat(l.amount) || 0), 0);
            
            if (liabilities.length === 0) {
                content.innerHTML = `
                    <div class="capital-summary">
                        <div class="capital-summary-item">
                            <span>Всего долгов:</span>
                            <strong style="color: var(--danger); font-size: 18px;">${formatMoney(total)} ₽</strong>
                        </div>
                    </div>
                    <div class="list">
                        <div class="empty-state">
                            <div class="empty-state-icon">📋</div>
                            <div class="empty-state-title">Нет долгов</div>
                            <div class="empty-state-text">Отлично! У вас нет задолженностей</div>
                        </div>
                    </div>
                `;
            } else {
                content.innerHTML = `
                    <div class="capital-summary">
                        <div class="capital-summary-item">
                            <span>Всего долгов:</span>
                            <strong style="color: var(--danger); font-size: 18px;">${formatMoney(total)} ₽</strong>
                        </div>
                    </div>
                    <div class="list">
                        ${liabilities.map(liab => `
                            <div class="transaction-card slide-up">
                                <div class="transaction-icon expense">📋</div>
                                <div class="transaction-content">
                                    <div class="transaction-title">${escapeHtml(liab.title)}</div>
                                    <div class="transaction-meta">${escapeHtml(liab.type || '—')} | Платеж: ${formatMoney(liab.monthly_payment || 0)} ₽/мес</div>
                                </div>
                                <div class="transaction-amount negative">${formatMoney(liab.amount || 0)} ₽</div>
                            </div>
                        `).join('')}
                    </div>
                `;
            }
        }
    } catch (error) {
        console.error('Error loading capital:', error);
        showEmptyState(
            'capital-content',
            '⚠️',
            'Ошибка загрузки',
            error.message
        );
    }
}

// ========== Reports ==========

async function loadReports() {
    const content = document.getElementById('reports-content');
    if (!content) return;
    
    showSkeleton('reports-content', 3);
    
    try {
        const reports = await apiRequest('/api/reports');
        
        // График 1: Расходы по категориям
        const chart1Data = reports.chart1.data;
        const chart1Items = Object.entries(chart1Data)
            .sort((a, b) => b[1] - a[1])
            .map(([cat, amount]) => `
                <div class="report-item">
                    <div class="report-item-label">${escapeHtml(cat)}</div>
                    <div class="report-item-value">${formatMoney(amount)} ₽</div>
                </div>
            `).join('');
        
        // График 2: Прогресс по целям
        const chart2Items = reports.chart2.data.map(g => {
            const progress = Math.round(g.progress);
            return `
                <div class="goal-item">
                    <div class="goal-title">${escapeHtml(g.title)}</div>
                    <div class="goal-progress">
                        <div class="goal-progress-bar">
                            <div class="goal-progress-fill" style="width: ${progress}%"></div>
                        </div>
                        <div class="goal-progress-text">${formatMoney(g.current)} / ${formatMoney(g.target)} ₽ (${progress}%)</div>
                    </div>
                </div>
            `;
        }).join('');
        
        // График 3: Динамика капитала
        const chart3Data = reports.chart3.data;
        const maxCapital = Math.max(...chart3Data.map(d => Math.max(d.assets, d.liabilities, Math.abs(d.net_capital))));
        const chart3Items = chart3Data.map(d => {
            const assetsPercent = (d.assets / maxCapital) * 100;
            const liabsPercent = (d.liabilities / maxCapital) * 100;
            return `
                <div class="capital-history-item">
                    <div class="capital-history-week">${d.week}</div>
                    <div class="capital-history-bars">
                        <div class="capital-bar" style="width: ${assetsPercent}%; background: #10B981;" title="Активы: ${formatMoney(d.assets)} ₽"></div>
                        <div class="capital-bar" style="width: ${liabsPercent}%; background: #EF4444; margin-left: 4px;" title="Долги: ${formatMoney(d.liabilities)} ₽"></div>
                    </div>
                    <div class="capital-history-value" style="color: ${d.net_capital >= 0 ? '#10B981' : '#EF4444'}">
                        ${formatMoney(d.net_capital)} ₽
                    </div>
                </div>
            `;
        }).join('');
        
        content.innerHTML = `
            <div class="report-section">
                <div class="report-header">
                    <h3>${reports.chart1.title}</h3>
                    <p class="report-description">${reports.chart1.description}</p>
                </div>
                <div class="report-chart">
                    ${chart1Items || '<div class="empty-state-text">Нет данных</div>'}
                </div>
            </div>
            
            <div class="report-section">
                <div class="report-header">
                    <h3>${reports.chart2.title}</h3>
                    <p class="report-description">${reports.chart2.description}</p>
                </div>
                <div class="report-chart">
                    ${chart2Items || '<div class="empty-state-text">Нет целей</div>'}
                </div>
            </div>
            
            <div class="report-section">
                <div class="report-header">
                    <h3>${reports.chart3.title}</h3>
                    <p class="report-description">${reports.chart3.description}</p>
                </div>
                <div class="report-chart">
                    ${chart3Items || '<div class="empty-state-text">Нет данных</div>'}
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Error loading reports:', error);
        content.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">⚠️</div>
                <div class="empty-state-title">Ошибка загрузки</div>
                <div class="empty-state-text">${error.message}</div>
            </div>
        `;
    }
}

// ========== Consultation ==========

let consultationHistory = [];
let consultationLimit = { used: 0, limit: 5 };

async function loadConsultation() {
    const content = document.getElementById('consultation-content');
    if (!content) return;
    
    // Загружаем историю и лимит
    try {
        const [history, currentConsultation] = await Promise.all([
            apiRequest('/api/consultation/history').catch(() => []),
            apiRequest('/api/consultation').catch(() => null)
        ]);
        
        consultationHistory = history || [];
        
        // Если есть текущая консультация, показываем её
        if (currentConsultation && currentConsultation.consultation) {
            consultationLimit.used = currentConsultation.requests_used || 0;
            consultationLimit.limit = 5;
            
            content.innerHTML = `
                <div class="consultation-controls">
                    <button class="btn btn-primary" onclick="requestNewConsultation()">
                        💡 Новая консультация
                    </button>
                    <div class="consultation-limit">
                        Использовано: ${consultationLimit.used}/${consultationLimit.limit} в этом месяце
                    </div>
                </div>
                <div class="consultation-card">
                    <div class="consultation-content">
                        ${markdownToHtml(currentConsultation.consultation)}
                    </div>
                </div>
                ${consultationHistory.length > 0 ? `
                <div class="consultation-history">
                    <h3>📜 История консультаций</h3>
                    ${consultationHistory.map((item, idx) => `
                        <div class="consultation-history-item">
                            <div class="consultation-history-date">${formatDate(item.date)}</div>
                            <div class="consultation-history-content">${markdownToHtml(item.content.substring(0, 200))}${item.content.length > 200 ? '...' : ''}</div>
                        </div>
                    `).join('')}
                </div>
                ` : ''}
            `;
        } else if (currentConsultation && currentConsultation.limit_reached) {
            consultationLimit.used = currentConsultation.requests_used || 5;
            consultationLimit.limit = 5;
            
            content.innerHTML = `
                <div class="consultation-controls">
                    <button class="btn btn-primary" disabled>
                        💡 Новая консультация
                    </button>
                    <div class="consultation-limit" style="color: #EF4444;">
                        Лимит исчерпан: ${consultationLimit.used}/${consultationLimit.limit}
                    </div>
                </div>
                <div class="empty-state">
                    <div class="empty-state-icon">⏰</div>
                    <div class="empty-state-title">Лимит консультаций</div>
                    <div class="empty-state-text">${currentConsultation.error || 'Вы использовали все консультации в этом месяце'}</div>
                </div>
                ${consultationHistory.length > 0 ? `
                <div class="consultation-history">
                    <h3>📜 История консультаций</h3>
                    ${consultationHistory.map((item, idx) => `
                        <div class="consultation-history-item">
                            <div class="consultation-history-date">${formatDate(item.date)}</div>
                            <div class="consultation-history-content">${markdownToHtml(item.content.substring(0, 200))}${item.content.length > 200 ? '...' : ''}</div>
                        </div>
                    `).join('')}
                </div>
                ` : ''}
            `;
        } else {
            // Нет текущей консультации, показываем форму запроса
            content.innerHTML = `
                <div class="consultation-controls">
                    <button class="btn btn-primary" onclick="requestNewConsultation()">
                        💡 Получить консультацию
                    </button>
                    <div class="consultation-limit">
                        Использовано: ${consultationLimit.used}/${consultationLimit.limit} в этом месяце
                    </div>
                </div>
                ${consultationHistory.length > 0 ? `
                <div class="consultation-history">
                    <h3>📜 История консультаций</h3>
                    ${consultationHistory.map((item, idx) => `
                        <div class="consultation-history-item">
                            <div class="consultation-history-date">${formatDate(item.date)}</div>
                            <div class="consultation-history-content">${markdownToHtml(item.content.substring(0, 200))}${item.content.length > 200 ? '...' : ''}</div>
                        </div>
                    `).join('')}
                </div>
                ` : '<div class="empty-state"><div class="empty-state-icon">💡</div><div class="empty-state-title">Нет консультаций</div><div class="empty-state-text">Нажмите кнопку выше, чтобы получить первую консультацию</div></div>'}
            `;
        }
    } catch (error) {
        console.error('Error loading consultation:', error);
        content.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">⚠️</div>
                <div class="empty-state-title">Ошибка загрузки</div>
                <div class="empty-state-text">${error.message}</div>
            </div>
        `;
    }
}

async function requestNewConsultation() {
    const content = document.getElementById('consultation-content');
    if (!content) return;
    
    showLoading('consultation-content', '🤔 Анализирую ваши финансы... (это займет несколько секунд)');
    AppState.hapticFeedback('light');
    
    try {
        const timeoutPromise = new Promise((_, reject) => {
            setTimeout(() => reject(new Error('Таймаут запроса')), 90000);
        });
        
        const result = await Promise.race([
            apiRequest('/api/consultation'),
            timeoutPromise
        ]);
        
        if (result.limit_reached) {
            consultationLimit.used = result.requests_used || 5;
            await loadConsultation(); // Перезагружаем для показа истории
            showNotification('Лимит консультаций исчерпан', 'error');
            return;
        }
        
        consultationLimit.used = result.requests_used || 0;
        await loadConsultation(); // Перезагружаем для показа новой консультации и истории
        showNotification('✅ Консультация получена!');
        AppState.hapticFeedback('medium');
    } catch (error) {
        console.error('Error requesting consultation:', error);
        showNotification('❌ Ошибка при получении консультации', 'error');
        AppState.hapticFeedback('heavy');
        await loadConsultation(); // Перезагружаем для показа ошибки
    }
}
// Export immediately
window.requestNewConsultation = requestNewConsultation;

// Functions are exported immediately after definition above
// This ensures they're available as soon as the script loads

// ========== Initialization ==========

// Ensure AppState is initialized
if (typeof AppState === 'undefined') {
    console.error('AppState не загружен! Проверьте порядок загрузки скриптов.');
}

document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM загружен, инициализация приложения...');
    
    // Ждем загрузки Telegram Web App скрипта
    const checkTelegram = () => {
        if (window.Telegram?.WebApp) {
            console.log('Telegram Web App обнаружен');
            console.log('initData доступен:', !!window.Telegram.WebApp.initData);
            console.log('initData длина:', window.Telegram.WebApp.initData?.length || 0);
            
            // Re-initialize Telegram Web App to ensure it's ready
            if (typeof AppState !== 'undefined' && AppState.initTelegram) {
                AppState.initTelegram();
            }
            
            // Initialize Telegram Web App
            if (AppState?.tg?.ready) {
                AppState.tg.ready();
                AppState.tg.expand();
            }
            
            // Load initial data
            const mainMenu = document.getElementById('main-menu');
            if (mainMenu && mainMenu.classList.contains('active')) {
                console.log('Загрузка статистики...');
                loadStats();
            }
        } else {
            console.warn('Telegram Web App не обнаружен. Приложение открыто в браузере.');
            // Для тестирования в браузере можно добавить тестовые данные
            const mainMenu = document.getElementById('main-menu');
            if (mainMenu && mainMenu.classList.contains('active')) {
                console.log('Попытка загрузки статистики (может не работать без Telegram)...');
                loadStats();
            }
        }
        
        // Hide FAB initially
        const fab = document.getElementById('fab-add-transaction');
        if (fab) {
            fab.style.display = 'none';
        }
        
        console.log('Инициализация завершена. Текущий экран:', AppState?.currentScreen || 'main-menu');
        console.log('isTelegram:', AppState?.isTelegram || false);
    };
    
    // Проверяем сразу и через небольшую задержку (на случай, если скрипт еще загружается)
    checkTelegram();
    setTimeout(checkTelegram, 100);
});
