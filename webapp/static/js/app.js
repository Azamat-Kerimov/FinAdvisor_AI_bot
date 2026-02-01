/* ============================================
   Main Application - Screens & Transaction Summary
   ============================================ */

(function() {
    if (typeof AppState === 'undefined' || typeof apiRequest === 'undefined' || typeof formatMoney === 'undefined') {
        console.error('app.js: AppState, apiRequest, formatMoney required');
        return;
    }

    function getTransactionQuery() {
        const month = document.getElementById('filter-month')?.value;
        const year = document.getElementById('filter-year')?.value;
        const category = document.getElementById('filter-category')?.value;
        const type = document.getElementById('filter-type')?.value;
        const params = new URLSearchParams();
        if (month) params.set('month', month);
        if (year) params.set('year', year);
        if (category) params.set('category', category);
        if (type) params.set('type', type);
        return params.toString();
    }

    function fillYearFilter() {
        const sel = document.getElementById('filter-year');
        if (!sel || sel.options.length > 0) return;
        const y = new Date().getFullYear();
        for (let i = y; i >= y - 5; i--) {
            const opt = document.createElement('option');
            opt.value = i;
            opt.textContent = i;
            sel.appendChild(opt);
        }
    }

    function loadCategories() {
        const expenseCats = AppState.expenseCategories || {};
        const incomeCats = AppState.incomeCategories || {};
        const allCats = { ...incomeCats, ...expenseCats };
        const select = document.getElementById('category-select');
        const filterCat = document.getElementById('filter-category');
        if (select) {
            select.innerHTML = '<option value="">Выберите категорию</option>';
            Object.keys(expenseCats).forEach(cat => {
                const opt = document.createElement('option');
                opt.value = cat;
                opt.textContent = (expenseCats[cat] || '') + ' ' + cat;
                select.appendChild(opt);
            });
            Object.keys(incomeCats).forEach(cat => {
                const opt = document.createElement('option');
                opt.value = cat;
                opt.textContent = (incomeCats[cat] || '') + ' ' + cat;
                select.appendChild(opt);
            });
        }
        if (filterCat) {
            filterCat.innerHTML = '<option value="">Категория</option>';
            Object.keys(allCats).forEach(cat => {
                const opt = document.createElement('option');
                opt.value = cat;
                opt.textContent = (allCats[cat] || '') + ' ' + cat;
                filterCat.appendChild(opt);
            });
        }
    }

    async function loadTransactions() {
        const list = document.getElementById('transactions-list');
        const summaryEl = document.getElementById('transactions-summary');
        if (!list) return;
        if (!document.getElementById('filter-year')?.options.length) fillYearFilter();
        const q = getTransactionQuery();
        if (typeof showSkeleton === 'function') showSkeleton('transactions-list', 5);
        try {
            const transactions = await apiRequest('/api/transactions?' + q);
            AppState.transactions = transactions || [];

            const incomeByCat = {};
            const expenseByCat = {};
            (transactions || []).forEach(tx => {
                const amount = parseFloat(tx.amount);
                const cat = tx.category || '—';
                if (amount >= 0) {
                    incomeByCat[cat] = (incomeByCat[cat] || 0) + amount;
                } else {
                    expenseByCat[cat] = (expenseByCat[cat] || 0) + Math.abs(amount);
                }
            });

            if (summaryEl) {
                const totalExp = Object.values(expenseByCat).reduce((a, b) => a + b, 0);
                const totalInc = Object.values(incomeByCat).reduce((a, b) => a + b, 0);
                const maxBar = Math.max(totalExp, totalInc, 1);
                const expWidth = (totalExp / maxBar) * 100;
                const incWidth = (totalInc / maxBar) * 100;

                // Исправление: в блоке «Расходы по категориям» показывать только категории расходов (не доходы)
                const expenseCategories = AppState.expenseCategories || {};
                const expenseOnlyEntries = Object.entries(expenseByCat)
                    .filter(([cat]) => expenseCategories.hasOwnProperty(cat))
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 8);
                const maxCat = Math.max(...expenseOnlyEntries.map(([, v]) => v), 1);
                const catRows = expenseOnlyEntries.map(([cat, sum]) => {
                    const pct = (sum / maxCat) * 100;
                    return '<div class="report-cat-row"><span class="report-cat-name">' + escapeHtml(cat) + '</span><span class="report-cat-bar"><span class="report-cat-fill" style="width:' + pct + '%"></span></span><span class="report-cat-value">' + formatMoney(sum) + ' ₽</span></div>';
                }).join('');

                const allCats = [...new Set([...Object.keys(expenseByCat), ...Object.keys(incomeByCat)])].sort((a, b) => {
                    const expA = expenseByCat[a] || 0, expB = expenseByCat[b] || 0;
                    const incA = incomeByCat[a] || 0, incB = incomeByCat[b] || 0;
                    return (expB + incB) - (expA + incA);
                });
                const tableRows = allCats.map(cat => {
                    const exp = expenseByCat[cat] || 0;
                    const inc = incomeByCat[cat] || 0;
                    return '<tr><td class="report-table-cat">' + escapeHtml(cat) + '</td><td class="report-table-expense">' + (exp ? formatMoney(exp) + ' ₽' : '—') + '</td><td class="report-table-income">' + (inc ? formatMoney(inc) + ' ₽' : '—') + '</td></tr>';
                }).join('');
                const tableHtml = allCats.length ? '<div class="report-by-category report-table-wrap"><h4>Суммы по категориям</h4><table class="report-cat-table"><thead><tr><th>Категория</th><th>Расходы</th><th>Доходы</th></tr></thead><tbody>' + tableRows + '</tbody></table></div>' : '';

                summaryEl.innerHTML =
                    '<div class="transactions-summary-cards">' +
                    '<div class="summary-card expense"><div class="summary-card-value">' + formatMoney(totalExp) + ' ₽</div><div class="summary-card-label">Траты</div><div class="summary-bar"><div class="summary-bar-fill expense" style="width: ' + expWidth + '%"></div></div></div>' +
                    '<div class="summary-card income"><div class="summary-card-value">' + formatMoney(totalInc) + ' ₽</div><div class="summary-card-label">Доходы</div><div class="summary-bar"><div class="summary-bar-fill income" style="width: ' + incWidth + '%"></div></div></div>' +
                    '</div>' +
                    (catRows ? '<div class="report-by-category"><h4>Расходы по категориям</h4><div class="report-cat-list">' + catRows + '</div></div>' : '') +
                    tableHtml;
            }

            if (!transactions || transactions.length === 0) {
                if (typeof showEmptyState === 'function') showEmptyState('transactions-list', '📝', 'Нет операций', 'Добавьте транзакцию или измените фильтры');
                return;
            }

            const byDate = {};
            transactions.forEach(tx => {
                const d = tx.created_at ? (tx.created_at.slice ? tx.created_at.slice(0, 10) : new Date(tx.created_at).toISOString().slice(0, 10)) : '';
                if (!byDate[d]) byDate[d] = [];
                byDate[d].push(tx);
            });
            const sortedDates = Object.keys(byDate).sort((a, b) => b.localeCompare(a));
            const categories = { ...(AppState.expenseCategories || {}), ...(AppState.incomeCategories || {}) };
            const today = new Date().toISOString().slice(0, 10);
            list.innerHTML = sortedDates.map(date => {
                const label = date === today ? 'Сегодня' : formatDate(date);
                const rows = byDate[date].map(tx => {
                    const amount = parseFloat(tx.amount);
                    const isPositive = amount >= 0;
                    const absAmount = Math.abs(amount);
                    const emoji = categories[tx.category] || '💰';
                    return '<div class="transaction-card" data-id="' + tx.id + '"><div class="transaction-icon ' + (isPositive ? 'income' : 'expense') + '">' + emoji + '</div><div class="transaction-content"><div class="transaction-title">' + escapeHtml(tx.description || tx.category || '—') + '</div><div class="transaction-meta">' + escapeHtml(tx.category || '—') + ' · ' + formatDate(tx.created_at) + '</div></div><div class="transaction-amount ' + (isPositive ? 'positive' : 'negative') + '">' + (isPositive ? '+' : '') + formatMoney(absAmount) + ' ₽</div><button class="btn-icon" onclick="editTransaction(' + tx.id + ')" title="Изменить">✏️</button><button class="btn-icon danger" onclick="deleteTransaction(' + tx.id + ')" title="Удалить">🗑️</button></div>';
                }).join('');
                return '<div class="transaction-group"><div class="transaction-group-date">' + label + '</div>' + rows + '</div>';
            }).join('');
        } catch (error) {
            console.error('Error loading transactions:', error);
            list.innerHTML = '<div class="empty-state"><div class="empty-state-icon">⚠️</div><div class="empty-state-title">Ошибка загрузки</div><div class="empty-state-text">' + escapeHtml(error.message) + '</div></div>';
        }
    }

    function showScreen(screenId) {
        document.querySelectorAll('.screen').forEach(s => { s.classList.remove('active'); });
        const el = document.getElementById(screenId);
        if (el) el.classList.add('active');
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.screen === screenId);
        });
        if (screenId === 'transactions') {
            loadCategories();
            loadTransactions();
        }
    }

    function applyTransactionFilters() {
        loadTransactions();
    }

    window.showScreen = showScreen;
    window.loadTransactions = loadTransactions;
    window.applyTransactionFilters = applyTransactionFilters;
    window.getTransactionQuery = getTransactionQuery;

    // Stubs for other handlers (чтобы не было ошибок при клике)
    window.addTransaction = function() { loadTransactions(); };
    window.editTransaction = function() {};
    window.deleteTransaction = function() {};
    /** Загрузка статистики на главный экран (с таймаутом и fallback — убирает вечную загрузку) */
    async function loadStats() {
        const container = document.getElementById('stats-card');
        if (!container) return;
        const timeoutMs = 8000;
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
        try {
            const data = await apiRequest('/api/stats', { signal: controller.signal });
            clearTimeout(timeoutId);
            const inc = (data && data.total_income) ? Number(data.total_income) : 0;
            const exp = (data && data.total_expense) ? Number(data.total_expense) : 0;
            const insight = (data && data.insight) ? String(data.insight) : '';
            const reserve = (data && data.reserve_recommended) ? Number(data.reserve_recommended) : 0;
            container.innerHTML =
                '<div class="balance-card">' +
                '<div class="balance-label">За текущий месяц</div>' +
                '<div class="balance-stats">' +
                '<div class="balance-stat-item"><div class="balance-stat-label">Доходы</div><div class="balance-stat-value">' + (typeof formatMoney !== 'undefined' ? formatMoney(inc) : inc) + ' ₽</div></div>' +
                '<div class="balance-stat-item"><div class="balance-stat-label">Расходы</div><div class="balance-stat-value">' + (typeof formatMoney !== 'undefined' ? formatMoney(exp) : exp) + ' ₽</div></div>' +
                '</div>' +
                (insight ? '<p class="balance-insight">' + escapeHtml(insight) + '</p>' : '') +
                (reserve > 0 ? '<p class="balance-reserve">Резервный фонд (рекоменд.): ' + (typeof formatMoney !== 'undefined' ? formatMoney(reserve) : reserve) + ' ₽</p>' : '') +
                '</div>';
        } catch (e) {
            clearTimeout(timeoutId);
            container.innerHTML =
                '<div class="welcome-card">' +
                '<div class="welcome-title">Добро пожаловать</div>' +
                '<p class="welcome-text">Добавьте операции или загрузите выписку из Сбера или Т‑Банка — статистика появится здесь.</p>' +
                '</div>';
        }
    }
    window.loadStats = loadStats;

    document.addEventListener('DOMContentLoaded', function() {
        loadStats();
    });
    window.loadBudgets = function() {};
    window.loadCapital = function() {};
    window.loadConsultation = function() {};
    window.switchCapitalTab = function() {};
    window.sendConsultationMessage = function() {};
    window.deleteMyAccount = function() {};
    window.closeEditTransactionModal = function() {};
    window.saveEditTransaction = function() {};
    window.closeImportModal = function() {};
    window.applyImport = function() {};
})();
