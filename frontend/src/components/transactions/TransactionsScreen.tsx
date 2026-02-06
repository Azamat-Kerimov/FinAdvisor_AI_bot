import React, { useState, useEffect, useMemo } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { apiRequest, getApiHeaders } from '@/lib/api';

interface Transaction {
  id: number;
  amount: number;
  category: string;
  description: string | null;
  created_at: string;
}

interface Category {
  id: number;
  name: string;
  type: string;
}

/** Ссылка на видеоинструкцию по загрузке Excel (Сбер/Т‑Банк). Замените на свой URL. */
const VIDEO_INSTRUCTION_URL = 'https://vk.com/video_ext.php?oid=-221650337&id=456239017&hd=2';

export function TransactionsScreen() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoriesLoading, setCategoriesLoading] = useState(true);
  const [loading, setLoading] = useState(true);
  
  // Фильтры
  const [selectedMonth, setSelectedMonth] = useState<number | null>(null);
  const [selectedYear, setSelectedYear] = useState<number>(new Date().getFullYear());
  const [selectedType, setSelectedType] = useState<'all' | 'income' | 'expense'>('all');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Модальные окна
  const [showAddModal, setShowAddModal] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  /** После парсинга файла — превью для подтверждения (null = не показывать превью) */
  const [pendingImportTransactions, setPendingImportTransactions] = useState<Array<{ date: string; amount: number; category_id: number; category?: string; description?: string | null }> | null>(null);
  const [uploadImportErrors, setUploadImportErrors] = useState<string[]>([]);
  const [importPreviewPage, setImportPreviewPage] = useState(1);
  const IMPORT_PAGE_SIZE = 20;
  
  // Форма
  const [formAmount, setFormAmount] = useState('');
  const [formCategoryId, setFormCategoryId] = useState<number | null>(null);
  const [formType, setFormType] = useState<'income' | 'expense'>('expense');
  const [formDescription, setFormDescription] = useState('');

  useEffect(() => {
    loadTransactions();
    loadCategories();
  }, [selectedMonth, selectedYear, selectedType, selectedCategory]);

  async function loadTransactions() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.append('limit', '1000');
      if (selectedMonth !== null) {
        params.append('month', selectedMonth.toString());
        params.append('year', selectedYear.toString());
      }
      if (selectedType !== 'all') {
        params.append('type', selectedType);
      }
      if (selectedCategory) {
        params.append('category', selectedCategory);
      }
      
      const data = await apiRequest<Transaction[]>(`/api/transactions?${params}`);
      setTransactions(data);
    } catch (e) {
      console.error('Ошибка загрузки транзакций:', e);
    } finally {
      setLoading(false);
    }
  }

  async function loadCategories() {
    setCategoriesLoading(true);
    try {
      const data = await apiRequest<Category[]>('/api/categories');
      setCategories(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error('Ошибка загрузки категорий:', e);
      setCategories([]);
    } finally {
      setCategoriesLoading(false);
    }
  }

  const filteredTransactions = useMemo(() => {
    let filtered = [...transactions];
    
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        tx =>
          tx.description?.toLowerCase().includes(query) ||
          tx.category.toLowerCase().includes(query) ||
          tx.amount.toString().includes(query)
      );
    }
    
    return filtered;
  }, [transactions, searchQuery]);


  const expenseTotal = useMemo(() => {
    return filteredTransactions
      .filter(tx => tx.amount < 0)
      .reduce((sum, tx) => sum + Math.abs(tx.amount), 0);
  }, [filteredTransactions]);

  const incomeTotal = useMemo(() => {
    return filteredTransactions
      .filter(tx => tx.amount > 0)
      .reduce((sum, tx) => sum + tx.amount, 0);
  }, [filteredTransactions]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const amount = parseFloat(formAmount);
      if (isNaN(amount) || !formCategoryId) {
        if (!formCategoryId && (expenseCategories.length === 0 && incomeCategories.length === 0)) {
          alert('Категории не загружены. Проверьте подключение и обновите страницу.');
        }
        return;
      }

      const finalAmount = formType === 'expense' ? -Math.abs(amount) : Math.abs(amount);

      if (editingId) {
        await apiRequest(`/api/transactions/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify({
            amount: finalAmount,
            category_id: formCategoryId,
            description: formDescription || null,
          }),
        });
      } else {
        await apiRequest('/api/transactions', {
          method: 'POST',
          body: JSON.stringify({
            amount: finalAmount,
            category_id: formCategoryId,
            description: formDescription || null,
          }),
        });
      }
      
      resetForm();
      loadTransactions();
    } catch (e) {
      alert('Ошибка: ' + (e instanceof Error ? e.message : String(e)));
    }
  }

  async function handleDelete(id: number) {
    if (!confirm('Удалить транзакцию?')) return;
    try {
      await apiRequest(`/api/transactions/${id}`, { method: 'DELETE' });
      loadTransactions();
    } catch (e) {
      alert('Ошибка: ' + (e instanceof Error ? e.message : String(e)));
    }
  }

  function startEdit(tx: Transaction) {
    setEditingId(tx.id);
    setFormAmount(Math.abs(tx.amount).toString());
    setFormType(tx.amount >= 0 ? 'income' : 'expense');
    const cat = categories.find(c => c.name === tx.category);
    setFormCategoryId(cat?.id || null);
    setFormDescription(tx.description || '');
    setShowAddModal(true);
  }

  function resetForm() {
    setShowAddModal(false);
    setShowUploadModal(false);
    setEditingId(null);
    setFormAmount('');
    setFormCategoryId(null);
    setFormDescription('');
    setFormType('expense');
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.match(/\.(xlsx|xls)$/i)) {
      alert('Разрешены только файлы Excel (.xlsx, .xls)');
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);

      const headers = await getApiHeaders();

      const API_BASE = import.meta.env.VITE_API_URL ?? '';
      const res = await fetch(`${API_BASE}/api/transactions/import`, {
        method: 'POST',
        headers,
        body: formData,
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Ошибка: ${res.status}`);
      }

      const result = await res.json();
      setUploadImportErrors(result.errors || []);

      if (result.transactions && result.transactions.length > 0) {
        setPendingImportTransactions(result.transactions);
        setImportPreviewPage(1);
      } else {
        alert('Транзакции не найдены в файле');
      }
    } catch (e) {
      alert('Ошибка загрузки: ' + (e instanceof Error ? e.message : String(e)));
    } finally {
      setUploading(false);
      if (e.target) e.target.value = '';
    }
  }

  async function handleImportApply(mode: 'add' | 'replace') {
    if (!pendingImportTransactions?.length) return;
    setUploading(true);
    try {
      await apiRequest('/api/transactions/import/apply', {
        method: 'POST',
        body: JSON.stringify({ mode, transactions: pendingImportTransactions }),
      });
      setPendingImportTransactions(null);
      setUploadImportErrors([]);
      setShowUploadModal(false);
      setUploading(false);
      loadTransactions().catch(() => {});
      alert(mode === 'add' ? 'Транзакции добавлены' : 'Транзакции за период заменены');
    } catch (e) {
      setUploading(false);
      alert('Ошибка: ' + (e instanceof Error ? e.message : String(e)));
    }
  }

  function handleImportCancel() {
    setPendingImportTransactions(null);
    setUploadImportErrors([]);
    setImportPreviewPage(1);
  }

  function formatMoney(value: number): string {
    return new Intl.NumberFormat('ru-RU').format(Math.round(value));
  }


  const monthNames = [
    'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
  ];

  // Периоды: последние 24 месяца, от нового к старым (для выбора месяца+года)
  const periodOptions = useMemo(() => {
    const now = new Date();
    const options: { value: string; label: string }[] = [];
    for (let i = 0; i < 24; i++) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      const y = d.getFullYear();
      const m = d.getMonth() + 1;
      options.push({
        value: `${y}-${m}`,
        label: `${monthNames[d.getMonth()]} ${y}`,
      });
    }
    return options;
  }, []);

  const expenseCategories = categories.filter(c => c.type === 'Расход');
  const incomeCategories = categories.filter(c => c.type === 'Доход');

  /** Фильтр списка по типу: all | expense | income (карточки Расходы/Доходы) */
  const [listFilter, setListFilter] = useState<'all' | 'expense' | 'income'>('all');
  /** Раскрытые месяцы в списке (ключ "YYYY-MM") */
  const [expandedMonths, setExpandedMonths] = useState<Set<string>>(new Set());
  /** Раскрытые категории: ключ "monthKey|catName" */
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());

  const filteredByType = useMemo(() => {
    if (listFilter === 'all') return filteredTransactions;
    if (listFilter === 'expense') return filteredTransactions.filter(tx => tx.amount < 0);
    return filteredTransactions.filter(tx => tx.amount > 0);
  }, [filteredTransactions, listFilter]);

  /** Группировка по месяцу (ключ YYYY-MM), внутри по категории (по убыванию суммы) */
  const byMonthThenCategory = useMemo(() => {
    const byMonth: Record<string, Transaction[]> = {};
    filteredByType.forEach(tx => {
      const d = new Date(tx.created_at);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      if (!byMonth[key]) byMonth[key] = [];
      byMonth[key].push(tx);
    });
    const result: { monthKey: string; monthLabel: string; byCategory: Record<string, Transaction[]> }[] = [];
    const sortedKeys = Object.keys(byMonth).sort().reverse();
    sortedKeys.forEach(monthKey => {
      const txs = byMonth[monthKey];
      const [y, m] = monthKey.split('-').map(Number);
      const monthLabel = `${monthNames[m - 1]} ${y}`;
      const byCategory: Record<string, Transaction[]> = {};
      txs.forEach(tx => {
        const cat = tx.category || '—';
        if (!byCategory[cat]) byCategory[cat] = [];
        byCategory[cat].push(tx);
      });
      const categoriesSorted = Object.entries(byCategory)
        .map(([name, items]) => ({
          name,
          total: items.reduce((s, i) => s + i.amount, 0),
          items,
        }))
        .sort((a, b) => b.total - a.total);
      const byCategorySorted: Record<string, Transaction[]> = {};
      categoriesSorted.forEach(({ name, items }) => { byCategorySorted[name] = items; });
      result.push({ monthKey, monthLabel, byCategory: byCategorySorted });
    });
    return result;
  }, [filteredByType]);

  function toggleMonth(monthKey: string) {
    setExpandedMonths(prev => {
      const next = new Set(prev);
      if (next.has(monthKey)) next.delete(monthKey);
      else next.add(monthKey);
      return next;
    });
  }

  function toggleCategory(monthKey: string, catName: string) {
    const key = `${monthKey}|${catName}`;
    setExpandedCategories(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <>
      {/* Хедер */}
      <div className="mb-4">
        <h1 className="text-lg font-bold text-slate-900">Транзакции</h1>
      </div>

      {/* Поиск */}
      <div className="mb-4">
        <div className="relative">
          <input
            type="text"
            placeholder="Поиск"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border border-slate-300 bg-white px-10 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          />
          <svg
            className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
      </div>

      {/* Кнопки загрузки/добавления — выше фильтров */}
      <div className="mb-4 grid grid-cols-2 gap-3">
        <button
          type="button"
          onClick={() => setShowUploadModal(true)}
          className="flex flex-col items-center gap-2 rounded-xl border-2 border-blue-500 bg-gradient-to-r from-purple-500 to-blue-500 p-3 text-left text-white transition-shadow hover:shadow-lg"
        >
          <svg className="h-[1.725rem] w-[1.725rem]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <div>
            <div className="font-semibold text-[0.7875rem]">Загрузить данные из Банка &gt;</div>
            <div className="mt-0.5 text-[0.675rem] opacity-90">
              Импортируйте операции из Excel-файла из приложения СберОнлайн и Т‑Банк
            </div>
          </div>
        </button>

        <button
          type="button"
          onClick={() => setShowAddModal(true)}
          className="flex flex-col items-center gap-2 rounded-xl border border-slate-300 bg-white p-3 text-left transition-shadow hover:shadow-lg"
        >
          <svg className="h-[1.725rem] w-[1.725rem] text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
          </svg>
          <div>
            <div className="font-semibold text-[0.7875rem] text-slate-900">Добавить транзакции вручную &gt;</div>
            <div className="mt-0.5 text-[0.675rem] text-slate-600">
              Введите данные транзакции вручную
            </div>
          </div>
        </button>
      </div>

      {/* Фильтры: уже, в одну линию, ниже кнопок */}
      <div className="mb-4 flex flex-wrap gap-1.5">
        <div className="relative min-w-0 flex-1 basis-24">
          <select
            value={selectedMonth !== null ? `${selectedYear}-${selectedMonth}` : ''}
            onChange={(e) => {
              if (e.target.value) {
                const [y, m] = e.target.value.split('-').map(Number);
                setSelectedYear(y);
                setSelectedMonth(m);
              } else {
                setSelectedMonth(null);
              }
            }}
            className="w-full appearance-none rounded-full border border-slate-300 bg-white px-3 py-1.5 pr-7 text-xs focus:border-blue-500 focus:outline-none"
          >
            <option value="">Все периоды</option>
            {periodOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <svg
            className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
        <div className="relative min-w-0 flex-1 basis-24">
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value as 'all' | 'income' | 'expense')}
            className="w-full appearance-none rounded-full border border-slate-300 bg-white px-3 py-1.5 pr-7 text-xs focus:border-blue-500 focus:outline-none"
          >
            <option value="all">Все типы</option>
            <option value="expense">Расходы</option>
            <option value="income">Доходы</option>
          </select>
          <svg
            className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
        <div className="relative min-w-0 flex-1 basis-28">
          <select
            value={selectedCategory || ''}
            onChange={(e) => setSelectedCategory(e.target.value || null)}
            className="w-full appearance-none rounded-full border border-slate-300 bg-white px-3 py-1.5 pr-7 text-xs focus:border-blue-500 focus:outline-none"
          >
            <option value="">Все категории</option>
            {categoriesLoading ? (
              <option value="" disabled>Загрузка...</option>
            ) : categories.length === 0 ? (
              <option value="" disabled>Нет категорий</option>
            ) : (
              categories.map(cat => (
                <option key={cat.id} value={cat.name}>{cat.name}</option>
              ))
            )}
          </select>
          <svg
            className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {/* Карточки Расходы/Доходы — подпись сверху, сумма слева, ring при выборе */}
      <div className="mb-4 grid grid-cols-2 gap-3">
        <Card
          className={`cursor-pointer p-4 transition-shadow hover:shadow-lg ${listFilter === 'expense' ? 'ring-2 ring-red-500' : ''}`}
          onClick={() => setListFilter(listFilter === 'expense' ? 'all' : 'expense')}
        >
          <div className="text-sm text-slate-600">Расходы</div>
          <div className="mt-1 text-2xl font-bold text-slate-900">{formatMoney(expenseTotal)} ₽</div>
          <div className="mt-1 text-xs text-slate-500">{filteredTransactions.filter(tx => tx.amount < 0).length} записей</div>
        </Card>

        <Card
          className={`cursor-pointer p-4 transition-shadow hover:shadow-lg ${listFilter === 'income' ? 'ring-2 ring-green-500' : ''}`}
          onClick={() => setListFilter(listFilter === 'income' ? 'all' : 'income')}
        >
          <div className="text-sm text-slate-600">Доходы</div>
          <div className="mt-1 text-2xl font-bold text-slate-900">{formatMoney(incomeTotal)} ₽</div>
          <div className="mt-1 text-xs text-slate-500">{filteredTransactions.filter(tx => tx.amount > 0).length} записей</div>
        </Card>
      </div>

      {/* Модальное окно загрузки */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => { setShowUploadModal(false); handleImportCancel(); }}>
          <div className="max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col" onClick={(e: React.MouseEvent<HTMLDivElement>) => e.stopPropagation()}>
            <Card className="p-6 overflow-hidden flex flex-col max-h-[90vh]">
              {pendingImportTransactions && pendingImportTransactions.length > 0 ? (
                <div className="flex flex-col min-h-0 pb-6 relative">
                  {uploading && (
                    <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-white/90 rounded-lg">
                      <div className="w-10 h-10 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mb-3" />
                      <p className="text-sm font-medium text-slate-700">Применяем импорт...</p>
                    </div>
                  )}
                  <div className="flex items-center justify-between mb-3 flex-shrink-0">
                    <h2 className="text-lg font-bold text-slate-900">Подтверждение импорта</h2>
                    <button type="button" onClick={() => { setShowUploadModal(false); handleImportCancel(); }} className="text-slate-400 hover:text-slate-600" disabled={uploading}>✕</button>
                  </div>
                  <p className="text-sm text-slate-600 mb-3">
                    <strong>Добавить</strong> — добавить транзакции из файла к уже имеющимся.
                    <br />
                    <strong>Заменить</strong> — удалить ваши транзакции за период с минимальной по максимальную дату из файла и вставить транзакции из файла.
                  </p>
                  {uploadImportErrors.length > 0 && (
                    <div className="mb-3 p-2 bg-amber-50 text-amber-800 text-xs rounded">{uploadImportErrors.join(' ')}</div>
                  )}
                  <div className="flex gap-2 mb-3">
                    <Button variant="primary" onClick={() => handleImportApply('add')} disabled={uploading} className="flex-1 py-2">Добавить</Button>
                    <Button variant="primary" onClick={() => handleImportApply('replace')} disabled={uploading} className="flex-1 py-2">Заменить</Button>
                    <Button variant="secondary" onClick={handleImportCancel} disabled={uploading} className="flex-1 py-2">Отменить</Button>
                  </div>
                  <div className="overflow-auto flex-1 min-h-0 max-h-[40vh] border border-slate-200 rounded-lg">
                    <table className="w-full text-sm">
                      <thead className="bg-slate-100 sticky top-0">
                        <tr>
                          <th className="text-left p-2">Тип</th>
                          <th className="text-left p-2">Категория</th>
                          <th className="text-right p-2">Сумма</th>
                          <th className="text-left p-2">Комментарий</th>
                          <th className="text-left p-2">Дата</th>
                        </tr>
                      </thead>
                      <tbody>
                        {pendingImportTransactions
                          .slice((importPreviewPage - 1) * IMPORT_PAGE_SIZE, importPreviewPage * IMPORT_PAGE_SIZE)
                          .map((tx, i) => (
                            <tr key={i} className="border-t border-slate-100">
                              <td className="p-2">{tx.amount >= 0 ? 'Доход' : 'Расход'}</td>
                              <td className="p-2">{tx.category ?? '—'}</td>
                              <td className={`p-2 text-right ${tx.amount >= 0 ? 'text-green-600' : 'text-red-600'}`}>{tx.amount >= 0 ? '+' : ''}{formatMoney(tx.amount)} ₽</td>
                              <td className="p-2 max-w-[120px] truncate" title={tx.description ?? ''}>{tx.description || '—'}</td>
                              <td className="p-2 whitespace-nowrap">{tx.date?.slice(0, 10) ?? '—'}</td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="flex items-center justify-between mt-3 mb-1 text-sm text-slate-500 flex-shrink-0">
                    <span>
                      {(importPreviewPage - 1) * IMPORT_PAGE_SIZE + 1}–{Math.min(importPreviewPage * IMPORT_PAGE_SIZE, pendingImportTransactions.length)} из {pendingImportTransactions.length}
                    </span>
                    <div className="flex gap-1">
                      <button
                        type="button"
                        disabled={importPreviewPage <= 1}
                        onClick={() => setImportPreviewPage(p => Math.max(1, p - 1))}
                        className="px-2 py-1 rounded border border-slate-300 disabled:opacity-50"
                      >
                        Назад
                      </button>
                      <button
                        type="button"
                        disabled={importPreviewPage >= Math.ceil(pendingImportTransactions.length / IMPORT_PAGE_SIZE)}
                        onClick={() => setImportPreviewPage(p => p + 1)}
                        className="px-2 py-1 rounded border border-slate-300 disabled:opacity-50"
                      >
                        Вперёд
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  <div className="mb-4 flex items-center justify-between">
                    <h2 className="text-lg font-bold text-slate-900">Загрузить данные из Банка</h2>
                    <button type="button" onClick={() => setShowUploadModal(false)} className="text-slate-400 hover:text-slate-600">✕</button>
                  </div>
                  <label className="block">
                    <input type="file" accept=".xlsx,.xls" onChange={handleFileUpload} disabled={uploading} className="hidden" />
                    <div className="cursor-pointer rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 p-8 text-center transition-colors hover:border-blue-500 hover:bg-blue-50">
                      {uploading ? (
                        <div className="text-slate-600">Загрузка...</div>
                      ) : (
                        <>
                          <svg className="mx-auto h-12 w-12 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                          </svg>
                          <p className="mt-2 text-sm text-slate-600">Нажмите для выбора файла Excel</p>
                          <p className="mt-1 text-xs text-slate-400">.xlsx или .xls из Сбера и Т‑Банка без изменений.</p>
                        </>
                      )}
                    </div>
                  </label>
                  <p className="mt-3 text-center">
                    <a href={VIDEO_INSTRUCTION_URL} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-blue-600 hover:underline">Видеоинструкция</a>
                  </p>
                </>
              )}
            </Card>
          </div>
        </div>
      )}

      {/* Модальное окно добавления */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => resetForm()}>
          <div className="max-w-md w-full" onClick={(e: React.MouseEvent<HTMLDivElement>) => e.stopPropagation()}>
            <Card className="p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-900">
                {editingId ? 'Редактировать транзакцию' : 'Добавить транзакцию'}
              </h2>
              <button
                type="button"
                onClick={() => resetForm()}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Тип транзакции
                </label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setFormType('expense')}
                    className={`flex-1 rounded-lg border-2 px-4 py-2.5 font-medium transition-colors ${
                      formType === 'expense'
                        ? 'border-red-500 bg-red-50 text-red-700'
                        : 'border-slate-300 bg-white text-slate-700'
                    }`}
                  >
                    Расход
                  </button>
                  <button
                    type="button"
                    onClick={() => setFormType('income')}
                    className={`flex-1 rounded-lg border-2 px-4 py-2.5 font-medium transition-colors ${
                      formType === 'income'
                        ? 'border-green-500 bg-green-50 text-green-700'
                        : 'border-slate-300 bg-white text-slate-700'
                    }`}
                  >
                    Доход
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Категория *
                </label>
                <select
                  value={formCategoryId || ''}
                  onChange={(e) => setFormCategoryId(Number(e.target.value) || null)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  required
                >
                  <option value="">
                    {categoriesLoading ? 'Загрузка категорий...' : (formType === 'expense' ? expenseCategories.length === 0 ? 'Нет категорий расходов' : 'Выберите категорию' : incomeCategories.length === 0 ? 'Нет категорий доходов' : 'Выберите категорию')}
                  </option>
                  {formType === 'expense' ? (
                    expenseCategories.map(cat => (
                      <option key={cat.id} value={cat.id}>{cat.name}</option>
                    ))
                  ) : (
                    incomeCategories.map(cat => (
                      <option key={cat.id} value={cat.id}>{cat.name}</option>
                    ))
                  )}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Сумма *
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={formAmount}
                  onChange={(e) => setFormAmount(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  placeholder="0.00"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Комментарий <span className="text-slate-400">(необязательно)</span>
                </label>
                <textarea
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  placeholder="Введите комментарий"
                  rows={3}
                />
              </div>

              <div className="flex gap-2">
                <Button type="submit" variant="primary" className="flex-[65_1_0] py-3">
                  {editingId ? 'Сохранить' : 'Добавить'}
                </Button>
                <Button type="button" variant="secondary" onClick={() => resetForm()} className="flex-[35_1_0] py-3">
                  Отмена
                </Button>
              </div>
            </form>
            </Card>
          </div>
        </div>
      )}

      {/* Список: по месяцам (раскрытие), внутри по категориям (по убыванию), записи с Редактировать/Удалить */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-12 text-slate-500">
          <div className="w-10 h-10 border-2 border-slate-500 border-t-transparent rounded-full animate-spin mb-3" />
          <p className="text-sm">Загрузка...</p>
        </div>
      ) : byMonthThenCategory.length === 0 ? (
        <Card className="p-8 text-center text-slate-500">
          <p className="mb-4">Нет транзакций</p>
          <Button variant="primary" onClick={() => setShowAddModal(true)} className="min-w-[200px] py-3.5 px-6">
            Добавить первую транзакцию
          </Button>
        </Card>
      ) : (
        <div className="space-y-4">
          {byMonthThenCategory.map(({ monthKey, monthLabel, byCategory }) => {
            const isExpanded = expandedMonths.has(monthKey);
            const monthTotal = Object.values(byCategory).flat().reduce((s, tx) => s + tx.amount, 0);
            const monthCount = Object.values(byCategory).flat().length;
            return (
              <div key={monthKey}>
                <button
                  type="button"
                  onClick={() => toggleMonth(monthKey)}
                  className="w-full flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-left hover:bg-slate-100"
                >
                  <span className="font-medium text-slate-900">{monthLabel}</span>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className={`text-sm whitespace-nowrap ${monthTotal >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {monthTotal >= 0 ? '+' : ''}{formatMoney(monthTotal)} ₽ · {monthCount} {monthCount === 1 ? 'запись' : 'записей'}
                    </span>
                    <svg
                      className={`h-5 w-5 text-slate-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </button>
                {isExpanded && (
                  <div className="mt-2 space-y-2 pl-2 border-l-2 border-slate-200">
                    {Object.entries(byCategory)
                      .map(([catName, items]) => ({
                        catName,
                        total: items.reduce((s, i) => s + i.amount, 0),
                        items,
                      }))
                      .sort((a, b) => b.total - a.total)
                      .map(({ catName, total, items }) => {
                        const categoryKey = `${monthKey}|${catName}`;
                        const isCatExpanded = expandedCategories.has(categoryKey);
                        return (
                          <div key={catName}>
                            <button
                              type="button"
                              onClick={() => toggleCategory(monthKey, catName)}
                              className="w-full flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50/80 px-3 py-2.5 text-left hover:bg-slate-100"
                            >
                              <span className="font-medium text-slate-700">{catName}</span>
                              <div className="flex items-center gap-2 flex-shrink-0">
                                <span className={`text-sm whitespace-nowrap ${total >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                  {total >= 0 ? '+' : ''}{formatMoney(total)} ₽ · {items.length}
                                </span>
                                <svg
                                  className={`h-4 w-4 text-slate-400 transition-transform ${isCatExpanded ? 'rotate-180' : ''}`}
                                  fill="none"
                                  stroke="currentColor"
                                  viewBox="0 0 24 24"
                                >
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                </svg>
                              </div>
                            </button>
                            {isCatExpanded && (
                              <div className="mt-2 space-y-2 pl-2 border-l-2 border-slate-200">
                                {items.map((tx) => (
                                  <Card key={tx.id} className="p-3">
                                    <div className="flex items-center justify-between gap-3">
                                      <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-slate-900">{tx.description || 'Без описания'}</p>
                                        <p className="text-xs text-slate-500">{tx.category}</p>
                                      </div>
                                      <div className="flex items-center gap-1.5 flex-shrink-0 text-right">
                                        <span className={`text-base font-semibold ${tx.amount >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                          {tx.amount >= 0 ? '+' : ''}{formatMoney(tx.amount)} ₽
                                        </span>
                                        <button
                                          type="button"
                                          onClick={() => startEdit(tx)}
                                          className="rounded-lg bg-slate-100 p-2.5 text-slate-600 transition-colors hover:bg-slate-200 inline-flex items-center justify-center"
                                          title="Редактировать"
                                        >
                                          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                          </svg>
                                        </button>
                                        <button
                                          type="button"
                                          onClick={() => handleDelete(tx.id)}
                                          className="rounded-lg bg-red-50 p-2.5 text-red-600 transition-colors hover:bg-red-100 inline-flex items-center justify-center"
                                          title="Удалить"
                                        >
                                          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                          </svg>
                                        </button>
                                      </div>
                                    </div>
                                  </Card>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
