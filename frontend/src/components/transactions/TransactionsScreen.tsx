import React, { useState, useEffect, useMemo, type MouseEvent } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { apiRequest } from '@/lib/api';
import { PieChart } from './PieChart';

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

const TRANSACTIONS_PER_PAGE = 50;

export function TransactionsScreen() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  
  // Фильтры
  const [selectedMonth, setSelectedMonth] = useState<number | null>(null);
  const [selectedYear, setSelectedYear] = useState<number>(new Date().getFullYear());
  const [selectedType, setSelectedType] = useState<'all' | 'income' | 'expense'>('all');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Модальные окна
  const [showAddModal, setShowAddModal] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showPieChart, setShowPieChart] = useState<'expense' | 'income' | null>(null);
  const [uploading, setUploading] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  
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
      setCurrentPage(1);
    } catch (e) {
      console.error('Ошибка загрузки транзакций:', e);
    } finally {
      setLoading(false);
    }
  }

  async function loadCategories() {
    try {
      const data = await apiRequest<Category[]>('/api/categories');
      setCategories(data);
    } catch (e) {
      console.error('Ошибка загрузки категорий:', e);
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

  const paginatedTransactions = useMemo(() => {
    const start = (currentPage - 1) * TRANSACTIONS_PER_PAGE;
    return filteredTransactions.slice(start, start + TRANSACTIONS_PER_PAGE);
  }, [filteredTransactions, currentPage]);

  const totalPages = Math.ceil(filteredTransactions.length / TRANSACTIONS_PER_PAGE);

  const groupedTransactions = useMemo(() => {
    const groups: Record<string, Transaction[]> = {};
    paginatedTransactions.forEach(tx => {
      const date = new Date(tx.created_at).toLocaleDateString('ru-RU', {
        day: 'numeric',
        month: 'long',
        year: 'numeric',
      });
      if (!groups[date]) groups[date] = [];
      groups[date].push(tx);
    });
    return groups;
  }, [paginatedTransactions]);

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

  const expenseByCategory = useMemo(() => {
    const map: Record<string, number> = {};
    filteredTransactions
      .filter(tx => tx.amount < 0)
      .forEach(tx => {
        map[tx.category] = (map[tx.category] || 0) + Math.abs(tx.amount);
      });
    return map;
  }, [filteredTransactions]);

  const incomeByCategory = useMemo(() => {
    const map: Record<string, number> = {};
    filteredTransactions
      .filter(tx => tx.amount > 0)
      .forEach(tx => {
        map[tx.category] = (map[tx.category] || 0) + tx.amount;
      });
    return map;
  }, [filteredTransactions]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const amount = parseFloat(formAmount);
      if (isNaN(amount) || !formCategoryId) return;

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

      const initData = typeof window !== 'undefined' && (window as any).Telegram?.WebApp?.initData;
      const headers: HeadersInit = {};
      if (initData) headers['init-data'] = initData;

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
      
      if (result.errors && result.errors.length > 0) {
        alert('Ошибки при импорте:\n' + result.errors.join('\n'));
      }

      if (result.transactions && result.transactions.length > 0) {
        const apply = confirm(
          `Найдено ${result.transactions.length} транзакций. Применить импорт?`
        );
        if (apply) {
          await apiRequest('/api/transactions/import/apply', {
            method: 'POST',
            body: JSON.stringify({
              mode: 'add',
              transactions: result.transactions,
            }),
          });
          loadTransactions();
          setShowUploadModal(false);
          alert('Транзакции добавлены');
        }
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

  function formatMoney(value: number): string {
    return new Intl.NumberFormat('ru-RU').format(Math.round(value));
  }


  function getDayTotal(date: string): number {
    return groupedTransactions[date]?.reduce((sum, tx) => sum + tx.amount, 0) || 0;
  }

  const months = [
    'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
  ];

  const expenseCategories = categories.filter(c => c.type === 'Расход');
  const incomeCategories = categories.filter(c => c.type === 'Доход');

  return (
    <>
      {/* Хедер */}
      <div className="mb-4 flex items-center justify-between">
        <button
          type="button"
          onClick={() => {}}
          className="text-blue-600 text-sm font-medium"
        >
          Закрыть
        </button>
        <h1 className="text-lg font-bold text-slate-900">Операции</h1>
        <button type="button" className="text-blue-600">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        </button>
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

      {/* Фильтры */}
      <div className="mb-4 flex flex-wrap gap-2">
        <div className="relative">
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
            className="appearance-none rounded-full border border-slate-300 bg-white px-4 py-2 pr-8 text-sm focus:border-blue-500 focus:outline-none"
          >
            <option value="">Все месяцы</option>
            {months.map((m, i) => (
              <option key={i} value={`${selectedYear}-${i + 1}`}>
                {m}
              </option>
            ))}
          </select>
          <svg
            className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
        
        <div className="relative">
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value as 'all' | 'income' | 'expense')}
            className="appearance-none rounded-full border border-slate-300 bg-white px-4 py-2 pr-8 text-sm focus:border-blue-500 focus:outline-none"
          >
            <option value="all">Все типы</option>
            <option value="expense">Расходы</option>
            <option value="income">Доходы</option>
          </select>
          <svg
            className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>

        <div className="relative">
          <select
            value={selectedCategory || ''}
            onChange={(e) => setSelectedCategory(e.target.value || null)}
            className="appearance-none rounded-full border border-slate-300 bg-white px-4 py-2 pr-8 text-sm focus:border-blue-500 focus:outline-none"
          >
            <option value="">Все категории</option>
            {categories.map(cat => (
              <option key={cat.id} value={cat.name}>{cat.name}</option>
            ))}
          </select>
          <svg
            className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {/* Карточки Расходы/Доходы */}
      <div className="mb-4 grid grid-cols-2 gap-3">
        <Card
          className="cursor-pointer p-4 transition-shadow hover:shadow-lg"
          onClick={() => setShowPieChart(showPieChart === 'expense' ? null : 'expense')}
        >
          <div className="text-2xl font-bold text-slate-900">{formatMoney(expenseTotal)} ₽</div>
          <div className="mt-1 text-sm text-slate-600">Расходы</div>
          <div className="mt-2 flex h-1.5 gap-0.5 overflow-hidden rounded">
            {Object.entries(expenseByCategory)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 6)
              .map(([_, amount], i) => {
                const percent = (amount / expenseTotal) * 100;
                const colors = ['#8B5CF6', '#10B981', '#F59E0B', '#3B82F6', '#EC4899', '#06B6D4'];
                return (
                  <div
                    key={i}
                    className="flex-1"
                    style={{
                      backgroundColor: colors[i % colors.length],
                      width: `${percent}%`,
                    }}
                  />
                );
              })}
          </div>
        </Card>

        <Card
          className="cursor-pointer p-4 transition-shadow hover:shadow-lg"
          onClick={() => setShowPieChart(showPieChart === 'income' ? null : 'income')}
        >
          <div className="text-2xl font-bold text-slate-900">{formatMoney(incomeTotal)} ₽</div>
          <div className="mt-1 text-sm text-slate-600">Доходы</div>
          <div className="mt-2 flex h-1.5 gap-0.5 overflow-hidden rounded">
            {Object.entries(incomeByCategory)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 6)
              .map(([_, amount], i) => {
                const percent = (amount / incomeTotal) * 100;
                const colors = ['#3B82F6', '#10B981'];
                return (
                  <div
                    key={i}
                    className="flex-1"
                    style={{
                      backgroundColor: colors[i % colors.length],
                      width: `${percent}%`,
                    }}
                  />
                );
              })}
          </div>
        </Card>
      </div>

      {/* Pie Chart Modal */}
      {showPieChart && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => setShowPieChart(null)}>
          <div className="max-w-md w-full" onClick={(e: React.MouseEvent<HTMLDivElement>) => e.stopPropagation()}>
            <Card className="p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-900">
                {showPieChart === 'expense' ? 'Расходы по категориям' : 'Доходы по категориям'}
              </h2>
              <button
                type="button"
                onClick={() => setShowPieChart(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>
            <PieChart
              data={showPieChart === 'expense' ? expenseByCategory : incomeByCategory}
              total={showPieChart === 'expense' ? expenseTotal : incomeTotal}
              title={showPieChart === 'expense' ? 'Расходы' : 'Доходы'}
            />
            </Card>
          </div>
        </div>
      )}

      {/* Кнопки загрузки/добавления */}
      <div className="mb-4 grid grid-cols-2 gap-3">
        <button
          type="button"
          onClick={() => setShowUploadModal(true)}
          className="flex flex-col items-center gap-3 rounded-xl border-2 border-blue-500 bg-gradient-to-r from-purple-500 to-blue-500 p-4 text-left text-white transition-shadow hover:shadow-lg"
        >
          <svg className="h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <div>
            <div className="font-semibold">Загрузить данные из Банка &gt;</div>
            <div className="mt-1 text-xs opacity-90">
              Импортируйте операции из Excel-файла банка
            </div>
          </div>
        </button>

        <button
          type="button"
          onClick={() => setShowAddModal(true)}
          className="flex flex-col items-center gap-3 rounded-xl border border-slate-300 bg-white p-4 text-left transition-shadow hover:shadow-lg"
        >
          <svg className="h-8 w-8 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
          </svg>
          <div>
            <div className="font-semibold text-slate-900">Добавить транзакции вручную &gt;</div>
            <div className="mt-1 text-xs text-slate-600">
              Введите данные транзакции вручную
            </div>
          </div>
        </button>
      </div>

      {/* Модальное окно загрузки */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => setShowUploadModal(false)}>
          <div className="max-w-md w-full" onClick={(e: React.MouseEvent<HTMLDivElement>) => e.stopPropagation()}>
            <Card className="p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-900">Загрузить данные из Банка</h2>
              <button
                type="button"
                onClick={() => setShowUploadModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>
            <label className="block">
              <input
                type="file"
                accept=".xlsx,.xls"
                onChange={handleFileUpload}
                disabled={uploading}
                className="hidden"
              />
              <div className="cursor-pointer rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 p-8 text-center transition-colors hover:border-blue-500 hover:bg-blue-50">
                {uploading ? (
                  <div className="text-slate-600">Загрузка...</div>
                ) : (
                  <>
                    <svg className="mx-auto h-12 w-12 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                    <p className="mt-2 text-sm text-slate-600">Нажмите для выбора файла Excel</p>
                    <p className="mt-1 text-xs text-slate-400">.xlsx или .xls</p>
                  </>
                )}
              </div>
            </label>
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
                  <option value="">Выберите категорию</option>
                  {formType === 'expense' ? (
                    <>
                      {expenseCategories.map(cat => (
                        <option key={cat.id} value={cat.id}>{cat.name}</option>
                      ))}
                    </>
                  ) : (
                    <>
                      {incomeCategories.map(cat => (
                        <option key={cat.id} value={cat.id}>{cat.name}</option>
                      ))}
                    </>
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
                <Button type="submit" variant="primary" className="flex-1">
                  {editingId ? 'Сохранить' : 'Добавить'}
                </Button>
                <Button type="button" variant="secondary" onClick={() => resetForm()}>
                  Отмена
                </Button>
              </div>
            </form>
            </Card>
          </div>
        </div>
      )}

      {/* Список транзакций */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-12 text-slate-500">
          <div className="w-10 h-10 border-2 border-slate-500 border-t-transparent rounded-full animate-spin mb-3" />
          <p className="text-sm">Загрузка...</p>
        </div>
      ) : Object.keys(groupedTransactions).length === 0 ? (
        <Card className="p-8 text-center text-slate-500">
          <p className="mb-4">Нет транзакций</p>
          <Button variant="primary" onClick={() => setShowAddModal(true)}>
            Добавить первую транзакцию
          </Button>
        </Card>
      ) : (
        <>
          {Object.entries(groupedTransactions).map(([date, txs]) => {
            const dayTotal = getDayTotal(date);
            return (
              <div key={date} className="mb-6">
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="font-bold text-slate-900">{date}</h3>
                  <span className={`text-sm ${dayTotal >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {dayTotal >= 0 ? '+' : ''}{formatMoney(dayTotal)} ₽
                  </span>
                </div>
                <div className="space-y-2">
                  {txs.map((tx) => (
                    <Card key={tx.id} className="p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="mb-1 flex items-center gap-2">
                            <span className={`text-base font-semibold ${tx.amount >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                              {tx.amount >= 0 ? '+' : ''}{formatMoney(tx.amount)} ₽
                            </span>
                          </div>
                          <p className="text-sm font-medium text-slate-900">{tx.description || 'Без описания'}</p>
                          <p className="text-xs text-slate-500">{tx.category}</p>
                        </div>
                        <div className="flex gap-1">
                          <button
                            type="button"
                            onClick={() => startEdit(tx)}
                            className="rounded-lg bg-slate-100 p-2 text-slate-600 transition-colors hover:bg-slate-200"
                          >
                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDelete(tx.id)}
                            className="rounded-lg bg-red-50 p-2 text-red-600 transition-colors hover:bg-red-100"
                          >
                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              </div>
            );
          })}

          {/* Пагинация */}
          {totalPages > 1 && (
            <div className="mt-6 flex items-center justify-center gap-2">
              <button
                type="button"
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm disabled:opacity-50"
              >
                Назад
              </button>
              <span className="text-sm text-slate-600">
                Страница {currentPage} из {totalPages}
              </span>
              <button
                type="button"
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm disabled:opacity-50"
              >
                Вперёд
              </button>
            </div>
          )}
        </>
      )}
    </>
  );
}
