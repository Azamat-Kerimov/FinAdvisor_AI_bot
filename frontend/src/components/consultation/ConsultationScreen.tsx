import { useState, useEffect } from 'react';
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

interface ConsultationHistoryItem {
  content: string;
  date: string;
}

interface MessageResponse {
  goals_added: Array<{ title: string; target: number }>;
  reply: string;
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
  const [consultationLimit, setConsultationLimit] = useState<string>('');
  
  const [history, setHistory] = useState<ConsultationHistoryItem[]>([]);
  const [selectedHistoryIndex, setSelectedHistoryIndex] = useState<number | null>(null);
  
  const [goalTitle, setGoalTitle] = useState('');
  const [goalTarget, setGoalTarget] = useState('');
  const [goalDescription, setGoalDescription] = useState('');
  const [message, setMessage] = useState('');
  const [sendingMessage, setSendingMessage] = useState(false);

  useEffect(() => {
    loadGoals();
    loadHistory();
    loadConsultationLimit();
  }, []);

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

  async function loadHistory() {
    try {
      const data = await apiRequest<ConsultationHistoryItem[]>('/api/consultation/history');
      setHistory(data);
    } catch (e) {
      console.error('Ошибка загрузки истории:', e);
    }
  }

  async function loadConsultationLimit() {
    try {
      const data = await apiRequest<ConsultationResponse>('/api/consultation');
      setRequestsUsed(data.requests_used || 0);
      if (data.limit_reached) {
        setConsultationLimit(`Лимит консультаций: ${data.requests_used || 0}/5`);
      } else {
        setConsultationLimit(`Консультаций использовано: ${data.requests_used || 0}/5`);
      }
    } catch (e) {
      console.error('Ошибка загрузки лимита:', e);
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
    setConsultation(null);
    try {
      const data = await apiRequest<ConsultationResponse>('/api/consultation');
      setRequestsUsed(data.requests_used || 0);
      
      if (data.limit_reached) {
        setConsultationError(data.error || `Лимит консультаций исчерпан (${data.requests_used}/5)`);
        setConsultation(null);
        setConsultationLimit(`Лимит консультаций: ${data.requests_used || 0}/5`);
      } else if (data.consultation) {
        // Проверяем, не является ли это сообщением об ошибке
        const consultationText = data.consultation;
        if (consultationText.includes('⏱️') || consultationText.includes('❌') || consultationText.includes('ошибка')) {
          setConsultationError(consultationText);
          setConsultation(null);
        } else {
          setConsultation(consultationText);
          setConsultationError(null);
          loadHistory();
        }
        setConsultationLimit(`Консультаций использовано: ${data.requests_used || 0}/5`);
      } else if (data.error) {
        setConsultationError(data.error);
        setConsultation(null);
        setConsultationLimit(`Консультаций использовано: ${data.requests_used || 0}/5`);
      } else {
        setConsultationError('Не удалось получить консультацию');
        setConsultation(null);
      }
    } catch (e) {
      const errorMsg = e instanceof Error ? e.message : String(e);
      setConsultationError(errorMsg.includes('timeout') || errorMsg.includes('Timeout')
        ? '⏱️ Генерация консультации заняла слишком много времени. Попробуйте позже.'
        : `Ошибка: ${errorMsg}`);
      setConsultation(null);
    } finally {
      setLoadingConsultation(false);
    }
  }

  async function handleSendMessage(e: React.FormEvent) {
    e.preventDefault();
    const msg = message.trim();
    if (!msg) return;

    setSendingMessage(true);
    try {
      const response = await apiRequest<MessageResponse>('/api/consultation/message', {
        method: 'POST',
        body: JSON.stringify({ message: msg }),
      });
      
      setMessage('');
      await loadGoals();
      
      if (response.goals_added && response.goals_added.length > 0) {
        const goalsList = response.goals_added
          .map(g => `${g.title} — ${Math.round(g.target).toLocaleString('ru-RU')} ₽`)
          .join(', ');
        alert(`Цели добавлены: ${goalsList}`);
      } else {
        alert(response.reply || 'Сообщение отправлено.');
      }
    } catch (e) {
      alert('Ошибка: ' + (e instanceof Error ? e.message : String(e)));
    } finally {
      setSendingMessage(false);
    }
  }

  function formatMoney(value: number): string {
    return new Intl.NumberFormat('ru-RU').format(Math.round(value));
  }

  function formatDate(dateStr: string): string {
    const date = new Date(dateStr);
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
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
        <h2 className="text-lg font-bold text-slate-900 mb-3">Цели</h2>
        {loading ? (
          <div className="text-center py-4 text-muted text-sm">Загрузка...</div>
        ) : goals.length === 0 ? (
          <div className="text-center py-4 text-muted text-sm">
            Нет целей. Добавьте цель выше или отправьте сообщение ИИ.
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

      {/* Блок "Отправить сообщение" - перемещён выше */}
      <Card className="p-4 mb-4">
        <h2 className="text-lg font-bold text-slate-900 mb-3">Отправить сообщение</h2>
        <form onSubmit={handleSendMessage} className="space-y-2">
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className="w-full px-3 py-2 border border-border rounded-button focus:outline-none focus:ring-2 focus:ring-slate-400"
            placeholder="Например: Хочу накопить 500 000 на машину за год или оставьте пустым"
            rows={3}
          />
          <Button type="submit" variant="primary" disabled={sendingMessage || !message.trim()} className="w-full">
            {sendingMessage ? 'Отправка...' : 'Отправить'}
          </Button>
        </form>
        <p className="text-xs text-muted mt-2">
          ИИ извлечёт цели из сообщения и добавит их автоматически. Для пассивного дохода ИИ рассчитает необходимый капитал.
        </p>
      </Card>

      {/* Блок "Консультация ИИ" */}
      <Card className="p-4 mb-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-bold text-slate-900">Консультация ИИ</h2>
          {consultationLimit && (
            <span className="text-xs text-slate-500">{consultationLimit}</span>
          )}
        </div>
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

      {/* История консультаций */}
      {history.length > 0 && (
        <Card className="p-4">
          <h2 className="text-lg font-bold text-slate-900 mb-3">История консультаций</h2>
          <div className="space-y-2">
            {history.map((item, index) => (
              <button
                key={index}
                type="button"
                onClick={() => setSelectedHistoryIndex(selectedHistoryIndex === index ? null : index)}
                className={`w-full rounded-lg border-2 p-3 text-left transition-colors ${
                  selectedHistoryIndex === index
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-slate-200 bg-white hover:border-slate-300'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-slate-900">
                    Консультация от {formatDate(item.date)}
                  </span>
                  <svg
                    className={`h-4 w-4 text-slate-400 transition-transform ${
                      selectedHistoryIndex === index ? 'rotate-180' : ''
                    }`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
                {selectedHistoryIndex === index && (
                  <div className="mt-3 pt-3 border-t border-slate-200 text-sm text-slate-700 whitespace-pre-wrap">
                    {item.content}
                  </div>
                )}
              </button>
            ))}
          </div>
        </Card>
      )}
    </>
  );
}
