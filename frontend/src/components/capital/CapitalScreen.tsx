import React, { useState, useEffect, useMemo } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { apiRequest } from '@/lib/api';

interface Asset {
  asset_id: number;
  title: string;
  type: string;
  amount: number;
  updated_at: string | null;
}

interface Liability {
  liability_id: number;
  title: string;
  type: string;
  amount: number;
  monthly_payment: number;
  updated_at: string | null;
}

const ASSET_TYPES = [
  'Депозит',
  'Акции',
  'Облигации',
  'Недвижимость',
  'Наличные',
  'Банковский счёт',
  'Криптовалюта',
  'Драгоценные металлы',
  'Прочее',
];

const LIABILITY_TYPES = [
  'Кредит',
  'Ипотека',
  'Займ',
  'Кредитная карта',
  'Рассрочка',
  'Прочее',
];

export function CapitalScreen() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [liabilities, setLiabilities] = useState<Liability[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  /** Фильтр списка: all | assets | liabilities — по клику на карточку Активы/Пассивы */
  const [listFilter, setListFilter] = useState<'all' | 'assets' | 'liabilities'>('all');
  const [expandedTypes, setExpandedTypes] = useState<Set<string>>(new Set());
  
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingIsAsset, setEditingIsAsset] = useState<boolean>(true);
  
  const [formTitle, setFormTitle] = useState('');
  const [formType, setFormType] = useState('');
  const [formAmount, setFormAmount] = useState('');
  const [formMonthlyPayment, setFormMonthlyPayment] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const [assetsData, liabilitiesData] = await Promise.all([
        apiRequest<Asset[]>('/api/assets'),
        apiRequest<Liability[]>('/api/liabilities'),
      ]);
      setAssets(assetsData);
      setLiabilities(liabilitiesData);
    } catch (e) {
      console.error('Ошибка загрузки:', e);
    } finally {
      setLoading(false);
    }
  }

  const allItems = useMemo(() => {
    const assetItems = assets.map(a => ({
      id: a.asset_id,
      title: a.title,
      type: a.type,
      amount: a.amount,
      updated_at: a.updated_at,
      isAsset: true as const,
      monthly_payment: 0,
    }));
    const liabilityItems = liabilities.map(l => ({
      id: l.liability_id,
      title: l.title,
      type: l.type,
      amount: l.amount,
      updated_at: l.updated_at,
      isAsset: false as const,
      monthly_payment: l.monthly_payment,
    }));
    return [...assetItems, ...liabilityItems];
  }, [assets, liabilities]);

  const filteredItems = useMemo(() => {
    let filtered = [...allItems];
    if (listFilter === 'assets') filtered = filtered.filter(i => i.isAsset);
    if (listFilter === 'liabilities') filtered = filtered.filter(i => !i.isAsset);
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        item =>
          item.title.toLowerCase().includes(query) ||
          item.type.toLowerCase().includes(query) ||
          item.amount.toString().includes(query)
      );
    }
    return filtered;
  }, [allItems, searchQuery, listFilter]);

  /** Группировка по типу (Актив/Пассив уже учтён в listFilter) для раскрывающихся блоков */
  const itemsByType = useMemo(() => {
    const groups: Record<string, typeof filteredItems> = {};
    filteredItems.forEach(item => {
      const t = item.type || 'Прочее';
      if (!groups[t]) groups[t] = [];
      groups[t].push(item);
    });
    return groups;
  }, [filteredItems]);

  const assetsTotal = useMemo(() => {
    return assets.reduce((sum, a) => sum + (a.amount || 0), 0);
  }, [assets]);

  const liabilitiesTotal = useMemo(() => {
    return liabilities.reduce((sum, l) => sum + (l.amount || 0), 0);
  }, [liabilities]);

  const assetsByType = useMemo(() => {
    const map: Record<string, number> = {};
    assets.forEach(a => {
      map[a.type] = (map[a.type] || 0) + (a.amount || 0);
    });
    return map;
  }, [assets]);

  const liabilitiesByType = useMemo(() => {
    const map: Record<string, number> = {};
    liabilities.forEach(l => {
      map[l.type] = (map[l.type] || 0) + (l.amount || 0);
    });
    return map;
  }, [liabilities]);


  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const amount = parseFloat(formAmount);
      if (isNaN(amount) || !formTitle || !formType) return;

      if (editingIsAsset) {
        if (editingId) {
          await apiRequest(`/api/assets/${editingId}`, {
            method: 'PUT',
            body: JSON.stringify({
              title: formTitle,
              type: formType,
              amount,
            }),
          });
        } else {
          await apiRequest('/api/assets', {
            method: 'POST',
            body: JSON.stringify({
              title: formTitle,
              type: formType,
              amount,
            }),
          });
        }
      } else {
        const monthlyPayment = parseFloat(formMonthlyPayment) || 0;
        if (editingId) {
          await apiRequest(`/api/liabilities/${editingId}`, {
            method: 'PUT',
            body: JSON.stringify({
              title: formTitle,
              type: formType,
              amount,
              monthly_payment: monthlyPayment,
            }),
          });
        } else {
          await apiRequest('/api/liabilities', {
            method: 'POST',
            body: JSON.stringify({
              title: formTitle,
              type: formType,
              amount,
              monthly_payment: monthlyPayment,
            }),
          });
        }
      }

      resetForm();
      loadData();
    } catch (e) {
      alert('Ошибка: ' + (e instanceof Error ? e.message : String(e)));
    }
  }

  async function handleDelete(id: number, isAsset: boolean) {
    if (!confirm('Удалить?')) return;
    try {
      if (isAsset) {
        await apiRequest(`/api/assets/${id}`, { method: 'DELETE' });
      } else {
        await apiRequest(`/api/liabilities/${id}`, { method: 'DELETE' });
      }
      loadData();
    } catch (e) {
      alert('Ошибка: ' + (e instanceof Error ? e.message : String(e)));
    }
  }

  function startEdit(item: typeof allItems[0]) {
    setEditingId(item.id);
    setEditingIsAsset(item.isAsset);
    setFormTitle(item.title);
    setFormType(item.type);
    setFormAmount(item.amount.toString());
    setFormMonthlyPayment(item.monthly_payment.toString());
    setShowAddModal(true);
  }

  function resetForm() {
    setShowAddModal(false);
    setEditingId(null);
    setEditingIsAsset(true);
    setFormTitle('');
    setFormType('');
    setFormAmount('');
    setFormMonthlyPayment('');
  }

  function formatMoney(value: number): string {
    return new Intl.NumberFormat('ru-RU').format(Math.round(value));
  }

  function toggleType(type: string) {
    setExpandedTypes(prev => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }

  function formatDate(updatedAt: string | null): string {
    if (!updatedAt) return '—';
    return new Date(updatedAt).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  return (
    <>
      {/* Хедер */}
      <div className="mb-4">
        <h1 className="text-lg font-bold text-slate-900">Капитал</h1>
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

      {/* Карточки Активы/Пассивы — подпись сверху, сумма слева, цветная полоса */}
      <div className="mb-4 grid grid-cols-2 gap-3">
        <Card
          className={`cursor-pointer p-4 transition-shadow hover:shadow-lg ${listFilter === 'assets' ? 'ring-2 ring-green-500' : ''}`}
          onClick={() => setListFilter(listFilter === 'assets' ? 'all' : 'assets')}
        >
          <div className="text-sm text-slate-600">Активы</div>
          <div className="mt-1 text-2xl font-bold text-slate-900">{formatMoney(assetsTotal)} ₽</div>
          <div className="mt-2 flex h-1.5 gap-0.5 overflow-hidden rounded">
            {Object.entries(assetsByType)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 6)
              .map(([_, amount], i) => {
                const percent = assetsTotal > 0 ? (amount / assetsTotal) * 100 : 0;
                const colors = ['#3B82F6', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899', '#06B6D4'];
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
          className={`cursor-pointer p-4 transition-shadow hover:shadow-lg ${listFilter === 'liabilities' ? 'ring-2 ring-red-500' : ''}`}
          onClick={() => setListFilter(listFilter === 'liabilities' ? 'all' : 'liabilities')}
        >
          <div className="text-sm text-slate-600">Пассивы</div>
          <div className="mt-1 text-2xl font-bold text-slate-900">{formatMoney(liabilitiesTotal)} ₽</div>
          <div className="mt-2 flex h-1.5 gap-0.5 overflow-hidden rounded">
            {Object.entries(liabilitiesByType)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 6)
              .map(([_, amount], i) => {
                const percent = liabilitiesTotal > 0 ? (amount / liabilitiesTotal) * 100 : 0;
                const colors = ['#EF4444', '#F97316', '#EC4899', '#8B5CF6', '#6366F1', '#A855F7'];
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

      {/* Кнопка Добавить */}
      <div className="mb-4">
        <Button
          variant="primary"
          onClick={() => {
            setEditingIsAsset(true);
            resetForm();
            setShowAddModal(true);
          }}
          className="w-full py-3.5"
        >
          + Добавить
        </Button>
      </div>

      {/* Модальное окно добавления/редактирования */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => resetForm()}>
          <div className="max-w-md w-full" onClick={(e: React.MouseEvent<HTMLDivElement>) => e.stopPropagation()}>
            <Card className="p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-900">
                {editingId ? 'Редактировать' : editingIsAsset ? 'Добавить актив' : 'Добавить пассив'}
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
              {!editingId && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    Тип записи
                  </label>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setEditingIsAsset(true);
                        setFormType('');
                      }}
                      className={`flex-1 rounded-lg border-2 px-4 py-2.5 font-medium transition-colors ${
                        editingIsAsset
                          ? 'border-green-500 bg-green-50 text-green-700'
                          : 'border-slate-300 bg-white text-slate-700'
                      }`}
                    >
                      Актив
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setEditingIsAsset(false);
                        setFormType('');
                      }}
                      className={`flex-1 rounded-lg border-2 px-4 py-2.5 font-medium transition-colors ${
                        !editingIsAsset
                          ? 'border-red-500 bg-red-50 text-red-700'
                          : 'border-slate-300 bg-white text-slate-700'
                      }`}
                    >
                      Пассив
                    </button>
                  </div>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Название *
                </label>
                <input
                  type="text"
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  placeholder="Например: Депозит в Сбере"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Тип {editingIsAsset ? 'актива' : 'пассива'} *
                </label>
                <select
                  value={formType}
                  onChange={(e) => setFormType(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  required
                >
                  <option value="">Выберите тип</option>
                  {(editingIsAsset ? ASSET_TYPES : LIABILITY_TYPES).map(type => (
                    <option key={type} value={type}>{type}</option>
                  ))}
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

              {!editingIsAsset && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Ежемесячный платёж
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={formMonthlyPayment}
                    onChange={(e) => setFormMonthlyPayment(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                    placeholder="0.00"
                  />
                </div>
              )}

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

      {/* Список по типам (раскрывающиеся блоки), без группировки по дате */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-12 text-slate-500">
          <div className="w-10 h-10 border-2 border-slate-500 border-t-transparent rounded-full animate-spin mb-3" />
          <p className="text-sm">Загрузка...</p>
        </div>
      ) : filteredItems.length === 0 ? (
        <Card className="p-8 text-center text-slate-500">
          <p className="mb-4">Нет записей</p>
          <Button variant="primary" onClick={() => {
            setEditingIsAsset(true);
            setShowAddModal(true);
          }} className="min-w-[200px] py-3.5 px-6">
            Добавить первую запись
          </Button>
        </Card>
      ) : (
        <div className="space-y-4">
          {Object.entries(itemsByType).map(([typeName, items]) => {
            const isExpanded = expandedTypes.has(typeName);
            const typeTotal = items.reduce((s, i) => s + i.amount, 0);
            return (
              <div key={typeName}>
                <button
                  type="button"
                  onClick={() => toggleType(typeName)}
                  className="w-full flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-left hover:bg-slate-100"
                >
                  <span className="font-medium text-slate-900">{typeName}</span>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className={`text-sm whitespace-nowrap ${items[0]?.isAsset ? 'text-green-600' : 'text-red-600'}`}>
                      {formatMoney(typeTotal)} ₽ · {items.length} {items.length === 1 ? 'запись' : 'записей'}
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
                    {items.map((item) => (
                      <Card key={item.id} className="p-3">
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex-1 min-w-0">
                            <div className="mb-0.5">
                              <span className={`text-base font-semibold ${item.isAsset ? 'text-green-600' : 'text-red-600'}`}>
                                {formatMoney(item.amount)} ₽
                              </span>
                            </div>
                            <p className="text-sm font-medium text-slate-900">{item.title}</p>
                            {!item.isAsset && item.monthly_payment > 0 && (
                              <p className="text-xs text-slate-500">Платёж: {formatMoney(item.monthly_payment)} ₽/мес</p>
                            )}
                          </div>
                          <div className="flex items-center gap-1.5 flex-shrink-0">
                            <span className="text-xs text-slate-500 whitespace-nowrap">{formatDate(item.updated_at)}</span>
                            <button
                              type="button"
                              onClick={() => startEdit(item)}
                              className="rounded-lg bg-slate-100 p-2.5 text-slate-600 transition-colors hover:bg-slate-200 inline-flex items-center justify-center"
                              title="Редактировать"
                            >
                              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                              </svg>
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDelete(item.id, item.isAsset)}
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
    </>
  );
}
