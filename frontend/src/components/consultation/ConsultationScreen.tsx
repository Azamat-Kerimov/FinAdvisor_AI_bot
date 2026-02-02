import { useState, useEffect, useRef } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { apiRequest } from '@/lib/api';

interface Goal {
  id: number;
  title: string;
  target: number;
  current: number;
  description: string | null;
}

interface ConsultationResponse {
  consultation: string | null;
  error?: string;
  limit_reached?: boolean;
  requests_used?: number;
}

export function ConsultationScreen() {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [loading, setLoading] = useState(true);
  const [showGoalForm, setShowGoalForm] = useState(false);
  const [editingGoalId, setEditingGoalId] = useState<number | null>(null);
  
  const [consultation, setConsultation] = useState<string | null>(null);
  const [loadingConsultation, setLoadingConsultation] = useState(false);
  const [consultationError, setConsultationError] = useState<string | null>(null);
  const [requestsUsed, setRequestsUsed] = useState<number>(0);
  
  const [goalTitle, setGoalTitle] = useState('');
  const [goalTarget, setGoalTarget] = useState('');
  const [goalDescription, setGoalDescription] = useState('');
  const [message, setMessage] = useState('');

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadGoals();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [consultation]);

  async function loadGoals() {
    try {
      const data = await apiRequest<Goal[]>('/api/goals');
      setGoals(data);
    } catch (e) {
      console.error('Ошибка загрузки целей:', e);
    } finally {
      setLoading(false);
    }
  }

  async function handleGoalSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const target = parseFloat(goalTarget);
      if (isNaN(target) || !goalTitle) return;

      if (editingGoalId) {
        await deleteGoal(editingGoalId, true);
        await apiRequest('/api/goals', {
          method: 'POST',
          body: JSON.stringify({
            title: goalTitle,
            target,
            description: goalDescription || null,
          }),
        });
      } else {
        await apiRequest('/api/goals', {
          method: 'POST',
          body: JSON.stringify({
            title: goalTitle,
            target,
            description: goalDescription || null,
          }),
        });
      }

      resetGoalForm();
      loadGoals();
    } catch (e) {
      alert('Ошибка: ' + (e instanceof Error ? e.message : String(e)));
    }
  }

  async function deleteGoal(id: number, skipConfirm = false) {
    if (!skipConfirm && !confirm('Удалить цель?')) return;
    try {
      await apiRequest(`/api/goals/${id}`, { method: 'DELETE' });
      if (!skipConfirm) {
        loadGoals();
      }
    } catch (e) {
      throw e;
    }
  }

  async function handleDeleteGoal(id: number) {
    try {
      await deleteGoal(id, false);
    } catch (e) {
      alert('Ошибка: ' + (e instanceof Error ? e.message : String(e)));
    }
  }

  function resetGoalForm() {
    setShowGoalForm(false);
    setEditingGoalId(null);
    setGoalTitle('');
    setGoalTarget('');
    setGoalDescription('');
  }

  async function handleGetConsultation() {
    setLoadingConsultation(true);
    setConsultationError(null);
    try {
      const data = await apiRequest<ConsultationResponse>('/api/consultation');
      if (data.error || data.limit_reached) {
        setConsultationError(data.error || `Лимит консультаций исчерпан (${data.requests_used}/5)`);
        setConsultation(null);
      } else {
        setConsultation(data.consultation || null);
        setRequestsUsed(data.requests_used || 0);
      }
    } catch (e) {
      setConsultationError(e instanceof Error ? e.message : String(e));
      setConsultation(null);
    } finally {
      setLoadingConsultation(false);
    }
  }

  async function handleSendMessage(e: React.FormEvent) {
    e.preventDefault();
    if (!message.trim()) return;

    setLoadingConsultation(true);
    try {
      await apiRequest('/api/consultation/message', {
        method: 'POST',
        body: JSON.stringify({ message }),
      });
      setMessage('');
      loadGoals();
      alert('Сообщение отправлено. Цели обновлены.');
    } catch (e) {
      alert('Ошибка: ' + (e instanceof Error ? e.message : String(e)));
    } finally {
      setLoadingConsultation(false);
    }
  }

  function formatMoney(value: number): string {
    return new Intl.NumberFormat('ru-RU').format(Math.round(value));
  }

  return (
    <>
      <PageHeader
        title="Консультация"
        rightAction={
          <Button
            variant="primary"
            onClick={() => setShowGoalForm(!showGoalForm)}
            className="text-xs px-3 py-1.5"
          >
            {showGoalForm ? '✕' : '🎯'}
          </Button>
        }
      />

      {showGoalForm && (
        <Card className="p-4 mb-4">
          <form onSubmit={handleGoalSubmit} className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Название цели
              </label>
              <input
                type="text"
                value={goalTitle}
                onChange={(e) => setGoalTitle(e.target.value)}
                className="w-full px-3 py-2 border border-border rounded-button focus:outline-none focus:ring-2 focus:ring-slate-400"
                placeholder="Например: Накопить на отпуск"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Целевая сумма
              </label>
              <input
                type="number"
                step="0.01"
                value={goalTarget}
                onChange={(e) => setGoalTarget(e.target.value)}
                className="w-full px-3 py-2 border border-border rounded-button focus:outline-none focus:ring-2 focus:ring-slate-400"
                placeholder="0.00"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Описание
              </label>
              <textarea
                value={goalDescription}
                onChange={(e) => setGoalDescription(e.target.value)}
                className="w-full px-3 py-2 border border-border rounded-button focus:outline-none focus:ring-2 focus:ring-slate-400"
                placeholder="Необязательно"
                rows={2}
              />
            </div>
            <div className="flex gap-2">
              <Button type="submit" variant="primary" className="flex-1">
                {editingGoalId ? 'Сохранить' : 'Добавить'}
              </Button>
              <Button type="button" variant="secondary" onClick={resetGoalForm}>
                Отмена
              </Button>
            </div>
          </form>
        </Card>
      )}

      <Card className="p-4 mb-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-bold text-slate-900">Цели</h2>
          {requestsUsed > 0 && (
            <span className="text-xs text-muted">
              Консультаций: {requestsUsed}/5
            </span>
          )}
        </div>
        {loading ? (
          <div className="text-center py-4 text-muted text-sm">Загрузка...</div>
        ) : goals.length === 0 ? (
          <div className="text-center py-4 text-muted text-sm">
            Нет целей. Добавьте цель выше.
          </div>
        ) : (
          <div className="space-y-3">
            {goals.map((goal) => {
              const progress = goal.target > 0 ? (goal.current / goal.target) * 100 : 0;
              return (
                <div key={goal.id} className="space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-slate-900">{goal.title}</p>
                      {goal.description && (
                        <p className="text-sm text-slate-600">{goal.description}</p>
                      )}
                    </div>
                    <Button
                      variant="ghost"
                      onClick={() => handleDeleteGoal(goal.id)}
                      className="text-xs px-2 py-1 text-red-600"
                    >
                      🗑️
                    </Button>
                  </div>
                  <div className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-600">
                        {formatMoney(goal.current)} ₽ / {formatMoney(goal.target)} ₽
                      </span>
                      <span className="font-medium">{Math.round(progress)}%</span>
                    </div>
                    <div className="w-full bg-slate-200 rounded-full h-2">
                      <div
                        className="bg-slate-800 h-2 rounded-full transition-all"
                        style={{ width: `${Math.min(100, progress)}%` }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <Card className="p-4 mb-4">
        <h2 className="text-lg font-bold text-slate-900 mb-3">Консультация ИИ</h2>
        <Button
          variant="primary"
          onClick={handleGetConsultation}
          disabled={loadingConsultation}
          className="w-full mb-3"
        >
          {loadingConsultation ? 'Генерация...' : 'Получить консультацию'}
        </Button>

        {consultationError && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-button text-sm text-red-700 mb-3">
            {consultationError}
          </div>
        )}

        {consultation && (
          <div className="p-4 bg-slate-50 rounded-button text-sm whitespace-pre-wrap">
            {consultation}
          </div>
        )}
      </Card>

      <Card className="p-4">
        <h2 className="text-lg font-bold text-slate-900 mb-3">Отправить сообщение</h2>
        <form onSubmit={handleSendMessage} className="space-y-2">
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className="w-full px-3 py-2 border border-border rounded-button focus:outline-none focus:ring-2 focus:ring-slate-400"
            placeholder="Например: Хочу накопить 500 000 на машину за год"
            rows={3}
          />
          <Button type="submit" variant="primary" disabled={loadingConsultation || !message.trim()} className="w-full">
            Отправить
          </Button>
        </form>
        <p className="text-xs text-muted mt-2">
          ИИ извлечёт цели из сообщения и добавит их автоматически.
        </p>
      </Card>
    </>
  );
}
