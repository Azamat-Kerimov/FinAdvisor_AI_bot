import { useState, useEffect } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { apiRequest } from '@/lib/api';

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

export function TransactionsScreen() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);
  
  const [formAmount, setFormAmount] = useState('');
  const [formCategoryId, setFormCategoryId] = useState<number | null>(null);
  const [formDescription, setFormDescription] = useState('');

  useEffect(() => {
    loadTransactions();
    loadCategories();
  }, []);

  async function loadTransactions() {
    try {
      const data = await apiRequest<Transaction[]>('/api/transactions?limit=100');
      setTransactions(data);
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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const amount = parseFloat(formAmount);
      if (isNaN(amount) || !formCategoryId) return;

      if (editingId) {
        await apiRequest(`/api/transactions/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify({
            amount,
            category_id: formCategoryId,
            description: formDescription || null,
          }),
        });
      } else {
        await apiRequest('/api/transactions', {
          method: 'POST',
          body: JSON.stringify({
            amount,
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
    setFormAmount(tx.amount.toString());
    const cat = categories.find(c => c.name === tx.category);
    setFormCategoryId(cat?.id || null);
    setFormDescription(tx.description || '');
    setShowAddForm(true);
  }

  function resetForm() {
    setShowAddForm(false);
    setEditingId(null);
    setFormAmount('');
    setFormCategoryId(null);
    setFormDescription('');
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
          alert('Транзакции добавлены');
        }
      } else {
        alert('Транзакции не найдены в файле');
      }
    } catch (e) {
      alert('Ошибка загрузки: ' + (e instanceof Error ? e.message : String(e)));
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  }

  function formatMoney(value: number): string {
    return new Intl.NumberFormat('ru-RU', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  }

  const expenseCategories = categories.filter(c => c.type === 'Расход');
  const incomeCategories = categories.filter(c => c.type === 'Доход');

  return (
    <>
      <PageHeader
        title="Транзакции"
        rightAction={
          <div className="flex gap-2">
            <label className="cursor-pointer">
              <input
                type="file"
                accept=".xlsx,.xls"
                onChange={handleFileUpload}
                disabled={uploading}
                className="hidden"
              />
              <Button variant="secondary" disabled={uploading} className="text-xs px-3 py-1.5">
                {uploading ? '⏳' : '📁'}
              </Button>
            </label>
            <Button
              variant="primary"
              onClick={() => setShowAddForm(!showAddForm)}
              className="text-xs px-3 py-1.5"
            >
              {showAddForm ? '✕' : '+'}
            </Button>
          </div>
        }
      />

      {showAddForm && (
        <Card className="p-4 mb-4">
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Сумма
              </label>
              <input
                type="number"
                step="0.01"
                value={formAmount}
                onChange={(e) => setFormAmount(e.target.value)}
                className="w-full px-3 py-2 border border-border rounded-button focus:outline-none focus:ring-2 focus:ring-slate-400"
                placeholder="0.00"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Категория
              </label>
              <select
                value={formCategoryId || ''}
                onChange={(e) => setFormCategoryId(Number(e.target.value) || null)}
                className="w-full px-3 py-2 border border-border rounded-button focus:outline-none focus:ring-2 focus:ring-slate-400"
                required
              >
                <option value="">Выберите категорию</option>
                <optgroup label="Расходы">
                  {expenseCategories.map(cat => (
                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                  ))}
                </optgroup>
                <optgroup label="Доходы">
                  {incomeCategories.map(cat => (
                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                  ))}
                </optgroup>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Описание
              </label>
              <input
                type="text"
                value={formDescription}
                onChange={(e) => setFormDescription(e.target.value)}
                className="w-full px-3 py-2 border border-border rounded-button focus:outline-none focus:ring-2 focus:ring-slate-400"
                placeholder="Необязательно"
              />
            </div>
            <div className="flex gap-2">
              <Button type="submit" variant="primary" className="flex-1">
                {editingId ? 'Сохранить' : 'Добавить'}
              </Button>
              <Button type="button" variant="secondary" onClick={resetForm}>
                Отмена
              </Button>
            </div>
          </form>
        </Card>
      )}

      {loading ? (
        <div className="flex flex-col items-center justify-center py-12 text-muted">
          <div className="w-10 h-10 border-2 border-border border-t-slate-500 rounded-full animate-spin mb-3" />
          <p className="text-sm">Загрузка...</p>
        </div>
      ) : transactions.length === 0 ? (
        <Card className="p-8 text-center text-muted">
          <p className="mb-4">Нет транзакций</p>
          <Button variant="primary" onClick={() => setShowAddForm(true)}>
            Добавить первую транзакцию
          </Button>
        </Card>
      ) : (
        <div className="space-y-2">
          {transactions.map((tx) => (
            <Card key={tx.id} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-lg font-bold ${tx.amount >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {tx.amount >= 0 ? '+' : ''}{formatMoney(tx.amount)} ₽
                    </span>
                    <span className="text-xs px-2 py-0.5 bg-slate-100 rounded-full text-slate-600">
                      {tx.category}
                    </span>
                  </div>
                  {tx.description && (
                    <p className="text-sm text-slate-600 mb-1">{tx.description}</p>
                  )}
                  <p className="text-xs text-muted">{formatDate(tx.created_at)}</p>
                </div>
                <div className="flex gap-1">
                  <Button
                    variant="ghost"
                    onClick={() => startEdit(tx)}
                    className="text-xs px-2 py-1"
                  >
                    ✏️
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => handleDelete(tx.id)}
                    className="text-xs px-2 py-1 text-red-600"
                  >
                    🗑️
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
