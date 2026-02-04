import { useState, useEffect, useMemo } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { apiRequest } from '@/lib/api';
import { PieChart } from '../transactions/PieChart';

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

const ITEMS_PER_PAGE = 50;

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
  const [currentPage, setCurrentPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTypeFilter, setSelectedTypeFilter] = useState<string | null>(null);
  
  const [showAddModal, setShowAddModal] = useState(false);
  const [showPieChart, setShowPieChart] = useState<'assets' | 'liabilities' | null>(null);
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
      setCurrentPage(1);
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
    
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        item =>
          item.title.toLowerCase().includes(query) ||
          item.type.toLowerCase().includes(query) ||
          item.amount.toString().includes(query)
      );
    }
    
    if (selectedTypeFilter) {
      filtered = filtered.filter(item => item.type === selectedTypeFilter);
    }
    
    return filtered;
  }, [allItems, searchQuery, selectedTypeFilter]);

  const paginatedItems = useMemo(() => {
    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    return filteredItems.slice(start, start + ITEMS_PER_PAGE);
  }, [filteredItems, currentPage]);

  const totalPages = Math.ceil(filteredItems.length / ITEMS_PER_PAGE);

  const groupedItems = useMemo(() => {
    const groups: Record<string, typeof allItems> = {};
    paginatedItems.forEach(item => {
      const date = item.updated_at
        ? new Date(item.updated_at).toLocaleDateString('ru-RU', {
            day: 'numeric',
            month: 'long',
            year: 'numeric',
          })
        : 'Без даты';
      if (!groups[date]) groups[date] = [];
      groups[date].push(item);
    });
    return groups;
  }, [paginatedItems]);

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

  const uniqueTypes = useMemo(() => {
    const types = new Set<string>();
    assets.forEach(a => types.add(a.type));
    liabilities.forEach(l => types.add(l.type));
    return Array.from(types).sort();
  }, [assets, liabilities]);

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

  function getDayTotal(date: string): number {
    const items = groupedItems[date] || [];
    const assetsSum = items.filter(i => i.isAsset).reduce((sum, i) => sum + i.amount, 0);
    const liabilitiesSum = items.filter(i => !i.isAsset).reduce((sum, i) => sum + i.amount, 0);
    return assetsSum - liabilitiesSum;
  }

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
        <h1 className="text-lg font-bold text-slate-900">Капитал</h1>
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

      {/* Фильтр по категориям */}
      <div className="mb-4">
        <div className="relative">
          <select
            value={selectedTypeFilter || ''}
            onChange={(e) => setSelectedTypeFilter(e.target.value || null)}
            className="appearance-none rounded-full border border-slate-300 bg-white px-4 py-2 pr-8 text-sm focus:border-blue-500 focus:outline-none"
          >
            <option value="">Все категории</option>
            {uniqueTypes.map(type => (
              <option key={type} value={type}>{type}</option>
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

      {/* Карточки Активы/Пассивы */}
      <div className="mb-4 grid grid-cols-2 gap-3">
        <Card
          className="cursor-pointer p-4 transition-shadow hover:shadow-lg"
          onClick={() => setShowPieChart(showPieChart === 'assets' ? null : 'assets')}
        >
          <div className="text-2xl font-bold text-slate-900">{formatMoney(assetsTotal)} ₽</div>
          <div className="mt-1 text-sm text-slate-600">Активы</div>
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
          className="cursor-pointer p-4 transition-shadow hover:shadow-lg"
          onClick={() => setShowPieChart(showPieChart === 'liabilities' ? null : 'liabilities')}
        >
          <div className="text-2xl font-bold text-slate-900">{formatMoney(liabilitiesTotal)} ₽</div>
          <div className="mt-1 text-sm text-slate-600">Пассивы</div>
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

      {/* Pie Chart Modal */}
      {showPieChart && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => setShowPieChart(null)}>
          <Card className="max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-900">
                {showPieChart === 'assets' ? 'Активы по типам' : 'Пассивы по типам'}
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
              data={showPieChart === 'assets' ? assetsByType : liabilitiesByType}
              total={showPieChart === 'assets' ? assetsTotal : liabilitiesTotal}
              title={showPieChart === 'assets' ? 'Активы' : 'Пассивы'}
            />
          </Card>
        </div>
      )}

      {/* Кнопка Добавить */}
      <div className="mb-4">
        <Button
          variant="primary"
          onClick={() => {
            setEditingIsAsset(true);
            resetForm();
            setShowAddModal(true);
          }}
          className="w-full"
        >
          + Добавить
        </Button>
      </div>

      {/* Модальное окно добавления/редактирования */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => resetForm()}>
          <Card className="max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
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
      )}

      {/* Список активов/пассивов */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-12 text-slate-500">
          <div className="w-10 h-10 border-2 border-slate-500 border-t-transparent rounded-full animate-spin mb-3" />
          <p className="text-sm">Загрузка...</p>
        </div>
      ) : Object.keys(groupedItems).length === 0 ? (
        <Card className="p-8 text-center text-slate-500">
          <p className="mb-4">Нет записей</p>
          <Button variant="primary" onClick={() => {
            setEditingIsAsset(true);
            setShowAddModal(true);
          }}>
            Добавить первую запись
          </Button>
        </Card>
      ) : (
        <>
          {Object.entries(groupedItems).map(([date, items]) => {
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
                  {items.map((item) => (
                    <Card key={item.id} className="p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="mb-1 flex items-center gap-2">
                            <span className={`text-base font-semibold ${item.isAsset ? 'text-green-600' : 'text-red-600'}`}>
                              {formatMoney(item.amount)} ₽
                            </span>
                            <span className="text-xs px-2 py-0.5 bg-slate-100 rounded-full text-slate-600">
                              {item.type}
                            </span>
                          </div>
                          <p className="text-sm font-medium text-slate-900">{item.title}</p>
                          {!item.isAsset && item.monthly_payment > 0 && (
                            <p className="text-xs text-slate-500 mt-0.5">
                              Платёж: {formatMoney(item.monthly_payment)} ₽/мес
                            </p>
                          )}
                        </div>
                        <div className="flex gap-1">
                          <button
                            type="button"
                            onClick={() => startEdit(item)}
                            className="rounded-lg bg-slate-100 p-2 text-slate-600 transition-colors hover:bg-slate-200"
                          >
                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDelete(item.id, item.isAsset)}
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
