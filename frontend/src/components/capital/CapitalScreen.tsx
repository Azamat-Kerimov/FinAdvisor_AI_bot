import { useState, useEffect } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
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

export function CapitalScreen() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [liabilities, setLiabilities] = useState<Liability[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'assets' | 'liabilities'>('assets');
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);

  const [formTitle, setFormTitle] = useState('');
  const [formType, setFormType] = useState('');
  const [formAmount, setFormAmount] = useState('');
  const [formMonthlyPayment, setFormMonthlyPayment] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const amount = parseFloat(formAmount);
      if (isNaN(amount) || !formTitle || !formType) return;

      if (activeTab === 'assets') {
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

  async function handleDelete(id: number) {
    if (!confirm('Удалить?')) return;
    try {
      if (activeTab === 'assets') {
        await apiRequest(`/api/assets/${id}`, { method: 'DELETE' });
      } else {
        await apiRequest(`/api/liabilities/${id}`, { method: 'DELETE' });
      }
      loadData();
    } catch (e) {
      alert('Ошибка: ' + (e instanceof Error ? e.message : String(e)));
    }
  }

  function startEdit(item: Asset | Liability) {
    setEditingId('asset_id' in item ? item.asset_id : item.liability_id);
    setFormTitle(item.title);
    setFormType(item.type);
    setFormAmount(item.amount.toString());
    if ('monthly_payment' in item) {
      setFormMonthlyPayment(item.monthly_payment.toString());
    }
    setShowAddForm(true);
  }

  function resetForm() {
    setShowAddForm(false);
    setEditingId(null);
    setFormTitle('');
    setFormType('');
    setFormAmount('');
    setFormMonthlyPayment('');
  }

  function formatMoney(value: number): string {
    return new Intl.NumberFormat('ru-RU').format(Math.round(value));
  }

  const totalAssets = assets.reduce((sum, a) => sum + (a.amount || 0), 0);
  const totalLiabilities = liabilities.reduce((sum, l) => sum + (l.amount || 0), 0);
  const netWorth = totalAssets - totalLiabilities;
  const totalMonthlyPayments = liabilities.reduce((sum, l) => sum + (l.monthly_payment || 0), 0);

  return (
    <>
      <PageHeader
        title="Капитал"
        rightAction={
          <Button
            variant="primary"
            onClick={() => setShowAddForm(!showAddForm)}
            className="text-xs px-3 py-1.5"
          >
            {showAddForm ? '✕' : '+'}
          </Button>
        }
      />

      <div className="mb-4 flex gap-2">
        <button
          type="button"
          onClick={() => {
            setActiveTab('assets');
            resetForm();
          }}
          className={`flex-1 py-2 px-4 rounded-button font-medium transition-colors ${
            activeTab === 'assets'
              ? 'bg-slate-800 text-white'
              : 'bg-white border border-border text-slate-700'
          }`}
        >
          Активы
        </button>
        <button
          type="button"
          onClick={() => {
            setActiveTab('liabilities');
            resetForm();
          }}
          className={`flex-1 py-2 px-4 rounded-button font-medium transition-colors ${
            activeTab === 'liabilities'
              ? 'bg-slate-800 text-white'
              : 'bg-white border border-border text-slate-700'
          }`}
        >
          Долги
        </button>
      </div>

      <Card className="p-4 mb-4 bg-slate-50">
        <div className="space-y-2">
          <div className="flex justify-between">
            <span className="text-slate-600">Активы:</span>
            <span className="font-bold text-green-600">{formatMoney(totalAssets)} ₽</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-600">Долги:</span>
            <span className="font-bold text-red-600">{formatMoney(totalLiabilities)} ₽</span>
          </div>
          {activeTab === 'liabilities' && totalMonthlyPayments > 0 && (
            <div className="flex justify-between text-sm">
              <span className="text-slate-600">Ежемесячные платежи:</span>
              <span className="font-medium">{formatMoney(totalMonthlyPayments)} ₽</span>
            </div>
          )}
          <div className="pt-2 border-t border-border flex justify-between">
            <span className="font-medium text-slate-700">Чистый капитал:</span>
            <span className={`font-bold text-lg ${netWorth >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {formatMoney(netWorth)} ₽
            </span>
          </div>
        </div>
      </Card>

      {showAddForm && (
        <Card className="p-4 mb-4">
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Название
              </label>
              <input
                type="text"
                value={formTitle}
                onChange={(e) => setFormTitle(e.target.value)}
                className="w-full px-3 py-2 border border-border rounded-button focus:outline-none focus:ring-2 focus:ring-slate-400"
                placeholder="Например: Депозит в Сбере"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Тип
              </label>
              <input
                type="text"
                value={formType}
                onChange={(e) => setFormType(e.target.value)}
                className="w-full px-3 py-2 border border-border rounded-button focus:outline-none focus:ring-2 focus:ring-slate-400"
                placeholder={activeTab === 'assets' ? 'Депозит, Акции, Недвижимость...' : 'Кредит, Ипотека, Займ...'}
                required
              />
            </div>
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
            {activeTab === 'liabilities' && (
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Ежемесячный платёж
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={formMonthlyPayment}
                  onChange={(e) => setFormMonthlyPayment(e.target.value)}
                  className="w-full px-3 py-2 border border-border rounded-button focus:outline-none focus:ring-2 focus:ring-slate-400"
                  placeholder="0.00"
                />
              </div>
            )}
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
      ) : (
        <div className="space-y-2">
          {activeTab === 'assets' ? (
            assets.length === 0 ? (
              <Card className="p-8 text-center text-muted">
                <p className="mb-4">Нет активов</p>
                <Button variant="primary" onClick={() => setShowAddForm(true)}>
                  Добавить актив
                </Button>
              </Card>
            ) : (
              assets.map((asset) => (
                <Card key={asset.asset_id} className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-bold text-lg text-green-600">
                          {formatMoney(asset.amount)} ₽
                        </span>
                        <span className="text-xs px-2 py-0.5 bg-slate-100 rounded-full text-slate-600">
                          {asset.type}
                        </span>
                      </div>
                      <p className="text-sm font-medium text-slate-900">{asset.title}</p>
                    </div>
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        onClick={() => startEdit(asset)}
                        className="text-xs px-2 py-1"
                      >
                        ✏️
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={() => handleDelete(asset.asset_id)}
                        className="text-xs px-2 py-1 text-red-600"
                      >
                        🗑️
                      </Button>
                    </div>
                  </div>
                </Card>
              ))
            )
          ) : (
            liabilities.length === 0 ? (
              <Card className="p-8 text-center text-muted">
                <p className="mb-4">Нет долгов</p>
                <Button variant="primary" onClick={() => setShowAddForm(true)}>
                  Добавить долг
                </Button>
              </Card>
            ) : (
              liabilities.map((liab) => (
                <Card key={liab.liability_id} className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-bold text-lg text-red-600">
                          {formatMoney(liab.amount)} ₽
                        </span>
                        <span className="text-xs px-2 py-0.5 bg-slate-100 rounded-full text-slate-600">
                          {liab.type}
                        </span>
                      </div>
                      <p className="text-sm font-medium text-slate-900 mb-1">{liab.title}</p>
                      {liab.monthly_payment > 0 && (
                        <p className="text-xs text-slate-600">
                          Платёж: {formatMoney(liab.monthly_payment)} ₽/мес
                        </p>
                      )}
                    </div>
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        onClick={() => startEdit(liab)}
                        className="text-xs px-2 py-1"
                      >
                        ✏️
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={() => handleDelete(liab.liability_id)}
                        className="text-xs px-2 py-1 text-red-600"
                      >
                        🗑️
                      </Button>
                    </div>
                  </div>
                </Card>
              ))
            )
          )}
        </div>
      )}
    </>
  );
}
