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
        case 'capital':
            loadCapital();
            break;
        case 'consultation':
            loadConsultation();
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

// ========== Stats / Main Menu (ТЗ: только агрегаты, без форм) ==========

async function loadStats() {
    const statsCard = document.getElementById('stats-card');
    if (!statsCard) return;
    
    showSkeleton('stats-card', 3);
    
    try {
        const [stats, assets, liabilities] = await Promise.all([
            apiRequest('/api/stats'),
            apiRequest('/api/assets'),
            apiRequest('/api/liabilities')
        ]);
        
        AppState.stats = stats;
        AppState.assets = assets;
        AppState.liabilities = liabilities;
        
        // Блок 1 — Капитал (активы, долги, чистая стоимость)
        const totalAssets = assets.reduce((sum, a) => sum + (parseFloat(a.amount) || 0), 0);
        const totalLiabs = liabilities.reduce((sum, l) => sum + (parseFloat(l.amount) || 0), 0);
        const netWorth = totalAssets - totalLiabs;
        
        // Блок 2 — Баланс по транзакциям (текущий месяц)
        const income = stats.total_income || 0;
        const expense = stats.total_expense || 0;
        const balance = income + expense; // expense уже отрицательный в данных
        if (typeof expense === 'number' && expense > 0) {
            const balanceCorrect = income - expense;
        }
        const balanceMonth = income - Math.abs(expense);
        
        statsCard.innerHTML = `
            <!-- Блок 1: Капитал -->
            <div class="card stat-card home-block">
                <div class="card-header"><h3>💼 Капитал</h3></div>
                <div class="capital-summary three-rows">
                    <div class="capital-item">
                        <div class="capital-label">Активы</div>
                        <div class="capital-value" style="color: #10B981;">${formatMoney(totalAssets)} ₽</div>
                    </div>
                    <div class="capital-item">
                        <div class="capital-label">Долги</div>
                        <div class="capital-value" style="color: #EF4444;">${formatMoney(totalLiabs)} ₽</div>
                    </div>
                    <div class="capital-item highlight">
                        <div class="capital-label">Чистая стоимость</div>
                        <div class="capital-value" style="font-weight: 600; color: ${netWorth >= 0 ? '#10B981' : '#EF4444'};">${formatMoney(netWorth)} ₽</div>
                    </div>
                </div>
            </div>
            
            <!-- Блок 2: Баланс по транзакциям (текущий месяц) -->
            <div class="card stat-card home-block">
                <div class="card-header"><h3>📊 Баланс за месяц</h3></div>
                <div class="capital-summary three-rows">
                    <div class="capital-item">
                        <div class="capital-label">Начисления</div>
                        <div class="capital-value" style="color: #10B981;">+${formatMoney(income)} ₽</div>
                    </div>
                    <div class="capital-item">
                        <div class="capital-label">Расходы</div>
                        <div class="capital-value" style="color: #EF4444;">-${formatMoney(expense)} ₽</div>
                    </div>
                    <div class="capital-item highlight">
                        <div class="capital-label">Баланс месяца</div>
                        <div class="capital-value" style="font-weight: 600; color: ${balanceMonth >= 0 ? '#10B981' : '#EF4444'};">${formatMoney(balanceMonth)} ₽</div>
                    </div>
                </div>
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

AppState.transactionFilters = { month: null, year: null, category: '', type: '' };

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
    
    const filterCat = document.getElementById('filter-category');
    if (filterCat && filterCat.options.length <= 1) {
        filterCat.innerHTML = '<option value="">Категория</option>';
        for (const [cat, emoji] of Object.entries(categories)) {
            const option = document.createElement('option');
            option.value = cat;
            option.textContent = `${emoji} ${cat}`;
            filterCat.appendChild(option);
        }
    }
}

function fillYearFilter() {
    const sel = document.getElementById('filter-year');
    if (!sel) return;
    const now = new Date();
    const currentYear = now.getFullYear();
    sel.innerHTML = '<option value="">Год</option>';
    for (let y = currentYear; y >= currentYear - 5; y--) {
        const opt = document.createElement('option');
        opt.value = y;
        opt.textContent = y;
        if (y === currentYear) opt.selected = true;
        sel.appendChild(opt);
    }
}

// Предпросмотр импорта транзакций (храним между открытием модалки и apply)
let importPreviewData = { transactions: [], errors: [] };

function getTransactionQuery() {
    const month = document.getElementById('filter-month')?.value;
    const year = document.getElementById('filter-year')?.value;
    const category = document.getElementById('filter-category')?.value;
    const type = document.getElementById('filter-type')?.value;
    const params = new URLSearchParams();
    params.set('limit', '200');
    if (month) params.set('month', month);
    if (year) params.set('year', year);
    if (category) params.set('category', category);
    if (type) params.set('type', type);
    return params.toString();
}

document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('import-file-input');
    if (fileInput) {
        fileInput.addEventListener('change', async function() {
            const file = this.files && this.files[0];
            if (!file) return;
            const list = document.getElementById('import-preview-list');
            const errEl = document.getElementById('import-errors');
            const modal = document.getElementById('import-modal');
            if (!list || !modal) return;
            list.innerHTML = '<div class="loading"><div class="spinner"></div><p>Распознавание файла...</p></div>';
            errEl.innerHTML = '';
            modal.style.display = 'flex';
            try {
                const result = await uploadFile('/api/transactions/import', file);
                importPreviewData = { transactions: result.transactions || [], errors: result.errors || [] };
                if (importPreviewData.transactions.length === 0) {
                    list.innerHTML = '<div class="empty-state-text">Транзакций не распознано</div>';
                } else {
                    list.innerHTML = importPreviewData.transactions.slice(0, 50).map(t => `
                        <div class="import-preview-item">
                            <span>${escapeHtml(t.date)}</span>
                            <span>${t.amount >= 0 ? '+' : ''}${formatMoney(t.amount)} ₽</span>
                            <span>${escapeHtml(t.category)}</span>
                            <span>${escapeHtml((t.description || '').slice(0, 30))}</span>
                        </div>
                    `).join('') + (importPreviewData.transactions.length > 50 ? `<p class="import-more">... и ещё ${importPreviewData.transactions.length - 50}</p>` : '');
                }
                if (importPreviewData.errors.length > 0) {
                    errEl.innerHTML = '<strong>Предупреждения:</strong><ul>' + importPreviewData.errors.map(e => '<li>' + escapeHtml(e) + '</li>').join('') + '</ul>';
                }
            } catch (e) {
                list.innerHTML = '<div class="empty-state-text">Ошибка: ' + escapeHtml(e.message) + '</div>';
            }
            this.value = '';
        });
    }
});

function closeImportModal() {
    const modal = document.getElementById('import-modal');
    if (modal) modal.style.display = 'none';
}
window.closeImportModal = closeImportModal;

async function applyImport(mode) {
    if (importPreviewData.transactions.length === 0) {
        showNotification('Нет транзакций для применения', 'error');
        return;
    }
    try {
        const result = await apiRequest('/api/transactions/import/apply', {
            method: 'POST',
            body: JSON.stringify({ mode, transactions: importPreviewData.transactions })
        });
        showNotification('Добавлено транзакций: ' + (result.applied || 0));
        closeImportModal();
        loadTransactions();
        loadStats();
    } catch (e) {
        showNotification('Ошибка: ' + e.message, 'error');
    }
}
window.applyImport = applyImport;

function applyTransactionFilters() {
    AppState.hapticFeedback('light');
    loadTransactions();
}
window.applyTransactionFilters = applyTransactionFilters;

async function loadTransactions() {
    const list = document.getElementById('transactions-list');
    const summaryEl = document.getElementById('transactions-summary');
    if (!list) return;
    
    if (!document.getElementById('filter-year')?.options.length) fillYearFilter();
    
    const q = getTransactionQuery();
    showSkeleton('transactions-list', 5);
    
    try {
        const transactions = await apiRequest('/api/transactions?' + q);
        AppState.transactions = transactions;
        
        const incomeByCat = {};
        const expenseByCat = {};
        let totalIncome = 0;
        let totalExpense = 0;
        transactions.forEach(tx => {
            const amount = parseFloat(tx.amount);
            const cat = tx.category || '—';
            if (amount >= 0) {
                incomeByCat[cat] = (incomeByCat[cat] || 0) + amount;
                totalIncome += amount;
            } else {
                expenseByCat[cat] = (expenseByCat[cat] || 0) + Math.abs(amount);
                totalExpense += Math.abs(amount);
            }
        });
        
        if (summaryEl) {
            const totalExp = Object.values(expenseByCat).reduce((a, b) => a + b, 0);
            const totalInc = Object.values(incomeByCat).reduce((a, b) => a + b, 0);
            const maxBar = Math.max(totalExp, totalInc, 1);
            const expWidth = (totalExp / maxBar) * 100;
            const incWidth = (totalInc / maxBar) * 100;
            const catEntries = Object.entries(expenseByCat).sort((a, b) => b[1] - a[1]).slice(0, 8);
            const maxCat = Math.max(...catEntries.map(([, v]) => v), 1);
            const catRows = catEntries.map(([cat, sum]) => {
                const pct = (sum / maxCat) * 100;
                return `<div class="report-cat-row"><span class="report-cat-name">${escapeHtml(cat)}</span><span class="report-cat-bar"><span class="report-cat-fill" style="width:${pct}%"></span></span><span class="report-cat-value">${formatMoney(sum)} ₽</span></div>`;
            }).join('');
            summaryEl.innerHTML = `
                <div class="transactions-summary-cards">
                    <div class="summary-card expense">
                        <div class="summary-card-value">${formatMoney(totalExp)} ₽</div>
                        <div class="summary-card-label">Траты</div>
                        <div class="summary-bar"><div class="summary-bar-fill expense" style="width: ${expWidth}%"></div></div>
                    </div>
                    <div class="summary-card income">
                        <div class="summary-card-value">${formatMoney(totalInc)} ₽</div>
                        <div class="summary-card-label">Доходы</div>
                        <div class="summary-bar"><div class="summary-bar-fill income" style="width: ${incWidth}%"></div></div>
                    </div>
                </div>
                ${catRows ? `<div class="report-by-category"><h4>Расходы по категориям</h4><div class="report-cat-list">${catRows}</div></div>` : ''}
            `;
        }
        
        if (transactions.length === 0) {
            showEmptyState(
                'transactions-list',
                '📝',
                'Нет операций',
                'Добавьте транзакцию или измените фильтры'
            );
            return;
        }
        
        const byDate = {};
        transactions.forEach(tx => {
            const d = tx.created_at ? (tx.created_at.slice ? tx.created_at.slice(0, 10) : new Date(tx.created_at).toISOString().slice(0, 10)) : '';
            if (!byDate[d]) byDate[d] = [];
            byDate[d].push(tx);
        });
        const sortedDates = Object.keys(byDate).sort((a, b) => b.localeCompare(a));
        const categories = AppState.getCategories();
        const today = new Date().toISOString().slice(0, 10);
        
        list.innerHTML = sortedDates.map(date => {
            const label = date === today ? 'Сегодня' : formatDate(date);
            const rows = byDate[date].map(tx => {
                const amount = parseFloat(tx.amount);
                const isPositive = amount >= 0;
                const absAmount = Math.abs(amount);
                const emoji = categories[tx.category] || '💰';
                return `
                    <div class="transaction-card slide-up" data-id="${tx.id}">
                        <div class="transaction-icon ${isPositive ? 'income' : 'expense'}">${emoji}</div>
                        <div class="transaction-content">
                            <div class="transaction-title">${escapeHtml(tx.description || tx.category || '—')}</div>
                            <div class="transaction-meta">${escapeHtml(tx.category || '—')} · ${formatDate(tx.created_at)}</div>
                        </div>
                        <div class="transaction-amount ${isPositive ? 'positive' : 'negative'}">
                            ${isPositive ? '+' : ''}${formatMoney(absAmount)} ₽
                        </div>
                        <button class="btn-icon" onclick="editTransaction(${tx.id})" title="Изменить">✏️</button>
                        <button class="btn-icon danger" onclick="deleteTransaction(${tx.id})" title="Удалить">🗑️</button>
                    </div>
                `;
            }).join('');
            return `<div class="transaction-group"><div class="transaction-group-date">${label}</div>${rows}</div>`;
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

function editTransaction(id) {
    AppState.hapticFeedback('light');
    showNotification('Редактирование: откройте форму и измените данные, затем сохраните', 'info');
}

function deleteTransaction(id) {
    if (!confirm('Удалить эту транзакцию?')) return;
    AppState.hapticFeedback('medium');
    apiRequest('/api/transactions/' + id, { method: 'DELETE' })
        .then(() => { showNotification('Удалено'); loadTransactions(); loadStats(); })
        .catch(e => showNotification('Ошибка удаления', 'error'));
}
window.deleteTransaction = deleteTransaction;
window.editTransaction = editTransaction;

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
                            <div class="transaction-card slide-up" data-asset-id="${asset.asset_id}">
                                <div class="transaction-icon income">💼</div>
                                <div class="transaction-content">
                                    <div class="transaction-title">${escapeHtml(asset.title)}</div>
                                    <div class="transaction-meta">${escapeHtml(asset.type || '—')}</div>
                                </div>
                                <div class="transaction-amount positive">${formatMoney(asset.amount || 0)} ₽</div>
                                <button class="btn-icon" onclick="editAsset(${asset.asset_id})" title="Изменить">✏️</button>
                                <button class="btn-icon danger" onclick="deleteAsset(${asset.asset_id})" title="Удалить">🗑️</button>
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
                            <div class="transaction-card slide-up" data-liability-id="${liab.liability_id}">
                                <div class="transaction-icon expense">📋</div>
                                <div class="transaction-content">
                                    <div class="transaction-title">${escapeHtml(liab.title)}</div>
                                    <div class="transaction-meta">${escapeHtml(liab.type || '—')} | Платеж: ${formatMoney(liab.monthly_payment || 0)} ₽/мес</div>
                                </div>
                                <div class="transaction-amount negative">${formatMoney(liab.amount || 0)} ₽</div>
                                <button class="btn-icon" onclick="editLiability(${liab.liability_id})" title="Изменить">✏️</button>
                                <button class="btn-icon danger" onclick="deleteLiability(${liab.liability_id})" title="Удалить">🗑️</button>
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

async function deleteAsset(id) {
    if (!confirm('Удалить этот актив?')) return;
    AppState.hapticFeedback('medium');
    try {
        await apiRequest('/api/assets/' + id, { method: 'DELETE' });
        showNotification('Актив удалён');
        loadCapital();
        loadStats();
    } catch (e) {
        showNotification('Ошибка удаления: ' + e.message, 'error');
    }
}
window.deleteAsset = deleteAsset;

async function editAsset(id) {
    const asset = (AppState.assets || []).find(a => a.asset_id === id);
    if (!asset) return;
    const title = prompt('Название', asset.title || '');
    if (title === null) return;
    const type = prompt('Тип (например: депозит, недвижимость)', asset.type || '');
    if (type === null) return;
    const amount = parseFloat(prompt('Сумма (₽)', (asset.amount || 0).toString()));
    if (isNaN(amount) || amount < 0) {
        showNotification('Введите корректную сумму', 'error');
        return;
    }
    try {
        await apiRequest('/api/assets/' + id, {
            method: 'PUT',
            body: JSON.stringify({ title: title.trim(), type: type.trim(), amount })
        });
        showNotification('Актив обновлён');
        loadCapital();
        loadStats();
    } catch (e) {
        showNotification('Ошибка: ' + e.message, 'error');
    }
}
window.editAsset = editAsset;

async function deleteLiability(id) {
    if (!confirm('Удалить этот долг?')) return;
    AppState.hapticFeedback('medium');
    try {
        await apiRequest('/api/liabilities/' + id, { method: 'DELETE' });
        showNotification('Долг удалён');
        loadCapital();
        loadStats();
    } catch (e) {
        showNotification('Ошибка удаления: ' + e.message, 'error');
    }
}
window.deleteLiability = deleteLiability;

async function editLiability(id) {
    const liab = (AppState.liabilities || []).find(l => l.liability_id === id);
    if (!liab) return;
    const title = prompt('Название', liab.title || '');
    if (title === null) return;
    const type = prompt('Тип (например: кредит, займ)', liab.type || '');
    if (type === null) return;
    const amount = parseFloat(prompt('Сумма долга (₽)', (liab.amount || 0).toString()));
    if (isNaN(amount) || amount < 0) {
        showNotification('Введите корректную сумму', 'error');
        return;
    }
    const monthly = parseFloat(prompt('Ежемесячный платёж (₽)', (liab.monthly_payment || 0).toString()));
    if (isNaN(monthly) || monthly < 0) {
        showNotification('Введите корректный платёж', 'error');
        return;
    }
    try {
        await apiRequest('/api/liabilities/' + id, {
            method: 'PUT',
            body: JSON.stringify({ title: title.trim(), type: type.trim(), amount, monthly_payment: monthly })
        });
        showNotification('Долг обновлён');
        loadCapital();
        loadStats();
    } catch (e) {
        showNotification('Ошибка: ' + e.message, 'error');
    }
}
window.editLiability = editLiability;

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

async function sendConsultationMessage() {
    const input = document.getElementById('consultation-message-input');
    const msg = (input && input.value || '').trim();
    if (!msg) {
        showNotification('Введите сообщение', 'error');
        return;
    }
    const btn = document.getElementById('consultation-send-btn');
    if (btn) btn.disabled = true;
    try {
        const result = await apiRequest('/api/consultation/message', {
            method: 'POST',
            body: JSON.stringify({ message: msg })
        });
        if (input) input.value = '';
        showNotification(result.reply || 'Сообщение принято');
        if (result.goals_added && result.goals_added.length > 0) {
            showNotification('Цели добавлены: ' + result.goals_added.map(g => g.title).join(', '), 'info');
        }
        AppState.hapticFeedback('light');
    } catch (e) {
        showNotification('Ошибка: ' + (e.message || 'Не удалось отправить'), 'error');
    } finally {
        if (btn) btn.disabled = false;
    }
}
window.sendConsultationMessage = sendConsultationMessage;

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
