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
  const [, setRequestsUsed] = useState<number>(0);
  const [consultationLimit, setConsultationLimit] = useState<string>('');
  
  const [history, setHistory] = useState<ConsultationHistoryItem[]>([]);
  const [selectedHistoryIndex, setSelectedHistoryIndex] = useState<number | null>(null);
  const [openHelp, setOpenHelp] = useState<'addGoal' | 'send' | 'consultation' | null>(null);
  const HISTORY_PAGE_SIZE = 3;
  const [historyPage, setHistoryPage] = useState(1);
  
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
      setHistoryPage(1);
    } catch (e) {
      console.error('Ошибка загрузки истории:', e);
    }
  }

  async function loadConsultationLimit() {
    try {
      const data = await apiRequest<{ requests_used?: number; limit_reached?: boolean }>('/api/consultation/limit');
      setRequestsUsed(data.requests_used || 0);
      if (data.limit_reached) {
        setConsultationLimit(`Лимит консультаций: ${data.requests_used ?? 0}/5`);
      } else {
        setConsultationLimit(`Консультаций использовано: ${data.requests_used ?? 0}/5`);
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

  function startEditGoal(goal: Goal) {
    setGoalTitle(goal.title);
    setGoalTarget(String(goal.target));
    setGoalDescription(goal.description || '');
    setEditingGoalId(goal.id);
    setShowGoalForm(true);
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
      <PageHeader title="Консультация ИИ" />

      <Card className="p-4 mb-4">
        <h2 className="text-lg font-bold text-slate-900 mb-3">Цели</h2>
      {showGoalForm && (
        <div className="pt-3 border-t border-slate-200">
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
              <Button type="submit" variant="primary" className="flex-[65_1_0] py-3.5">
                {editingGoalId ? 'Сохранить' : 'Добавить'}
              </Button>
              <Button type="button" variant="secondary" onClick={resetGoalForm} className="flex-[35_1_0] py-3.5">
                Отмена
              </Button>
            </div>
          </form>
        </div>
      )}
      {!showGoalForm && (
          <>
            {loading ? (
              <div className="text-center py-4 text-muted text-sm">Загрузка...</div>
            ) : goals.length === 0 ? (
              <div className="text-center py-4 text-muted text-sm">
                Нет целей. Нажмите «Добавить цель» или отправьте сообщение ИИ.
              </div>
            ) : (
              <div className="space-y-3">
                {goals.map((goal) => {
                  const progress = goal.target <= 0 ? 100 : Math.max(0, Math.min(100, (Math.max(0, goal.current) / goal.target) * 100));
                  return (
                    <div key={goal.id} className="space-y-2">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-slate-900">{goal.title}</p>
                          {goal.description && (
                            <p className="text-sm text-slate-600">{goal.description}</p>
                          )}
                        </div>
                        <div className="flex items-center gap-1.5 flex-shrink-0">
                          <button
                            type="button"
                            onClick={() => startEditGoal(goal)}
                            className="rounded-lg bg-slate-100 p-2.5 text-slate-600 transition-colors hover:bg-slate-200 inline-flex items-center justify-center"
                            title="Редактировать"
                          >
                            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeleteGoal(goal.id)}
                            className="rounded-lg bg-red-50 p-2.5 text-red-600 transition-colors hover:bg-red-100 inline-flex items-center justify-center"
                            title="Удалить"
                          >
                            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </div>
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
                            style={{ width: `${progress}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
        {!showGoalForm && (
          <div className="mt-3 pt-3 border-t border-slate-200">
            <div className="flex items-center gap-2">
              <Button
                variant="primary"
                onClick={() => setShowGoalForm(true)}
                className="flex-1 py-3.5"
              >
                🎯 Добавить цель
              </Button>
              <button
                type="button"
                onClick={() => setOpenHelp(openHelp === 'addGoal' ? null : 'addGoal')}
                className="rounded-full w-8 h-8 flex items-center justify-center bg-slate-100 text-slate-600 hover:bg-slate-200 shrink-0"
                title="Пояснения"
              >
                ?
              </button>
            </div>
            {openHelp === 'addGoal' && (
              <p className="mt-2 p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-600">
                Прогресс цели = Ликвидный капитал / Целевая сумма. Ликвидный капитал = сумма ликвидных активов (депозит, акции, облигации, наличные, банковский счёт, криптовалюта) − обязательства, уменьшающие ликвидный капитал (кредит, займ, кредитная карта, рассрочка).
              </p>
            )}
          </div>
        )}
      </Card>

      {/* Блок "Отправить сообщение" */}
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
          <div className="flex items-center gap-2">
            <Button type="submit" variant="primary" disabled={sendingMessage || !message.trim()} className="flex-1 py-3.5">
              {sendingMessage ? 'Отправка...' : 'Отправить'}
            </Button>
            <button
              type="button"
              onClick={() => setOpenHelp(openHelp === 'send' ? null : 'send')}
              className="rounded-full w-8 h-8 flex items-center justify-center bg-slate-100 text-slate-600 hover:bg-slate-200 shrink-0"
              title="Пояснения"
            >
              ?
            </button>
          </div>
          {openHelp === 'send' && (
            <p className="mt-2 p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-600">
              ИИ извлечёт цели из сообщения и добавит их автоматически. Для пассивного дохода ИИ рассчитает необходимый капитал.
            </p>
          )}
        </form>
      </Card>

      {/* Блок "Консультация ИИ" */}
      <Card className="p-4 mb-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-bold text-slate-900">Консультация ИИ</h2>
          {consultationLimit && (
            <span className="text-xs text-slate-500">{consultationLimit}</span>
          )}
        </div>
        <div className="flex items-center gap-2 mb-3">
          <Button
            variant="primary"
            onClick={handleGetConsultation}
            disabled={loadingConsultation}
            className="flex-1 py-3.5"
          >
            {loadingConsultation ? 'Генерация...' : 'Получить консультацию'}
          </Button>
          <button
            type="button"
            onClick={() => setOpenHelp(openHelp === 'consultation' ? null : 'consultation')}
            className="rounded-full w-8 h-8 flex items-center justify-center bg-slate-100 text-slate-600 hover:bg-slate-200 shrink-0"
            title="Пояснения"
          >
            ?
          </button>
        </div>
        {openHelp === 'consultation' && (
          <p className="mb-3 p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-600">
            Для генерации ответа используются вся информация о транзакциях, капитале и ваши цели, а также история ваших запросов. Заполните остальные вкладки для более качественного ответа.
          </p>
        )}

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

      {/* История консультаций: последние первые, по 3 на странице */}
      {history.length > 0 && (
        <Card className="p-4">
          <h2 className="text-lg font-bold text-slate-900 mb-3">История консультаций</h2>
          {(() => {
            const totalPages = Math.ceil(history.length / HISTORY_PAGE_SIZE);
            const start = (historyPage - 1) * HISTORY_PAGE_SIZE;
            const pageItems = history.slice(start, start + HISTORY_PAGE_SIZE);
            const globalIndex = (i: number) => start + i;
            return (
              <>
                <div className="space-y-2">
                  {pageItems.map((item, i) => {
                    const index = globalIndex(i);
                    return (
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
                    );
                  })}
                </div>
                {totalPages > 1 && (
                  <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-200">
                    <span className="text-sm text-slate-500">
                      {start + 1}–{Math.min(start + HISTORY_PAGE_SIZE, history.length)} из {history.length}
                    </span>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        disabled={historyPage <= 1}
                        onClick={() => setHistoryPage((p) => Math.max(1, p - 1))}
                        className="px-3 py-1.5 rounded-lg border border-slate-300 text-sm disabled:opacity-50"
                      >
                        Назад
                      </button>
                      <button
                        type="button"
                        disabled={historyPage >= totalPages}
                        onClick={() => setHistoryPage((p) => p + 1)}
                        className="px-3 py-1.5 rounded-lg border border-slate-300 text-sm disabled:opacity-50"
                      >
                        Вперёд
                      </button>
                    </div>
                  </div>
                )}
              </>
            );
          })()}
        </Card>
      )}
    </>
  );
}
