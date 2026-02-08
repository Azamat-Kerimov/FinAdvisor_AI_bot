import { useState, useEffect } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { apiRequest } from '@/lib/api';
import { useConsultationActions } from '@/hooks/useStats';
import { ShareButton } from '@/components/ui/ShareButton';

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
  follow_ups?: Array<{ question: string | null; answer: string | null }>;
}

interface MessageResponse {
  goals_added: Array<{ title: string; target: number }>;
  reply: string;
}

interface FollowUpResponse {
  reply: string;
  sessions_used: number;
  limit: number;
  limit_reached?: boolean;
}

export function ConsultationScreen() {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [loading, setLoading] = useState(true);
  const [showGoalForm, setShowGoalForm] = useState(false);
  const [editingGoalId, setEditingGoalId] = useState<number | null>(null);
  
  const [consultation, setConsultation] = useState<string | null>(null);
  const [loadingConsultation, setLoadingConsultation] = useState(false);
  const [consultationError, setConsultationError] = useState<string | null>(null);
  const [consultationLimit, setConsultationLimit] = useState<string>('');
  const [canFollowupToday, setCanFollowupToday] = useState(false);
  const [, setSessionsLimit] = useState<number>(5);

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

  const [followUpMessage, setFollowUpMessage] = useState('');
  const [followUpReply, setFollowUpReply] = useState<string | null>(null);
  const [loadingFollowUp, setLoadingFollowUp] = useState(false);
  const [followUpError, setFollowUpError] = useState<string | null>(null);

  const { data: consultationActions, loading: actionsLoading, refetch: refetchActions } = useConsultationActions();

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
      const data = await apiRequest<{
        sessions_used?: number;
        limit?: number;
        limit_reached?: boolean;
        can_followup_today?: boolean;
      }>('/api/consultation/limit');
      const used = data.sessions_used ?? 0;
      const limit = data.limit ?? 5;
      setSessionsLimit(limit);
      setCanFollowupToday(!!data.can_followup_today);
      if (data.limit_reached) {
        setConsultationLimit(`Сессий в этом месяце: ${used}/${limit}`);
      } else {
        setConsultationLimit(`Сессий в этом месяце: ${used}/${limit} (1 сессия = день консультации + уточнения)`);
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
      const used = (data as { sessions_used?: number }).sessions_used ?? 0;
      const limit = (data as { limit?: number }).limit ?? 5;
      setSessionsLimit(limit);
      setCanFollowupToday(true);

      if (data.limit_reached) {
        setConsultationError(data.error || `Лимит сессий исчерпан (${used}/${limit})`);
        setConsultation(null);
        setConsultationLimit(`Сессий в этом месяце: ${used}/${limit}`);
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
          refetchActions();
        }
        const su = (data as { sessions_used?: number }).sessions_used ?? 0;
        const lim = (data as { limit?: number }).limit ?? 5;
        setConsultationLimit(`Сессий в этом месяце: ${su}/${lim}`);
      } else if (data.error) {
        setConsultationError(data.error);
        setConsultation(null);
        const su = (data as { sessions_used?: number }).sessions_used ?? 0;
        const lim = (data as { limit?: number }).limit ?? 5;
        setConsultationLimit(`Сессий в этом месяце: ${su}/${lim}`);
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

  async function handleFollowUp(e: React.FormEvent) {
    e.preventDefault();
    const msg = followUpMessage.trim();
    if (!msg) return;
    setLoadingFollowUp(true);
    setFollowUpError(null);
    setFollowUpReply(null);
    try {
      const data = await apiRequest<FollowUpResponse>('/api/consultation/follow-up', {
        method: 'POST',
        body: JSON.stringify({ message: msg }),
      });
      setFollowUpReply(data.reply);
      setFollowUpMessage('');
      const su = data.sessions_used ?? 0;
      const lim = data.limit ?? 5;
      setConsultationLimit(`Сессий в этом месяце: ${su}/${lim}`);
      loadHistory();
      refetchActions();
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      setFollowUpError(errorMsg);
    } finally {
      setLoadingFollowUp(false);
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
                className="min-w-[44px] min-h-[44px] flex items-center justify-center shrink-0 rounded-full"
                title="Пояснения"
              >
                <span className="w-6 h-6 rounded-full flex items-center justify-center bg-slate-100 text-slate-600 hover:bg-slate-200">?</span>
              </button>
            </div>
            {openHelp === 'addGoal' && (
              <p className="mt-2 p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-600">
                Прогресс цели = Ликвидный капитал / Целевая сумма. Ликвидный капитал = сумма ликвидных активов (депозит, акции, облигации, наличные, банковский счёт, криптовалюта) − обязательства, уменьшающие ликвидный капитал (кредит, займ, кредитная карта, рассрочка).
              </p>
            )}
          </div>
        )}

        <div className="mt-4 pt-4 border-t border-slate-200">
          <h3 className="text-base font-semibold text-slate-900 mb-2">Отправить сообщение</h3>
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
                className="min-w-[44px] min-h-[44px] flex items-center justify-center shrink-0 rounded-full"
                title="Пояснения"
              >
                <span className="w-6 h-6 rounded-full flex items-center justify-center bg-slate-100 text-slate-600 hover:bg-slate-200">?</span>
              </button>
            </div>
            {openHelp === 'send' && (
              <p className="mt-2 p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-600">
                ИИ извлечёт цели из сообщения и добавит их автоматически. Для пассивного дохода ИИ рассчитает необходимый капитал.
              </p>
            )}
          </form>
        </div>
      </Card>

      {/* Блок "Консультация ИИ" */}
      <Card className="p-4 mb-4 relative">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">Консультация ИИ</h2>
          <div className="flex items-center gap-2">
            {consultationLimit && (
              <span className="text-xs text-slate-500 dark:text-slate-400">{consultationLimit}</span>
            )}
            {consultation && (
              <ShareButton
                title="Консультация ИИ — FinAdvisor"
                text={consultation}
              />
            )}
          </div>
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
            className="min-w-[44px] min-h-[44px] flex items-center justify-center shrink-0 rounded-full"
            title="Пояснения"
          >
            <span className="w-6 h-6 rounded-full flex items-center justify-center bg-slate-100 text-slate-600 hover:bg-slate-200">?</span>
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
          <>
            <div className="p-4 bg-slate-50 dark:bg-slate-700/50 rounded-button text-sm whitespace-pre-wrap">
              {consultation}
            </div>
            {/* Уточняющий вопрос — только после получения консультации, в том же блоке */}
            {canFollowupToday && (
              <div className="mt-4 pt-4 border-t border-slate-200">
                <p className="text-sm font-medium text-slate-700 mb-2">Уточняющий вопрос</p>
                <p className="text-xs text-slate-500 mb-2">Задайте вопрос по консультации в этот же день. Уточнения не тратят лимит сессий.</p>
                <form onSubmit={handleFollowUp} className="space-y-2">
                  <textarea
                    value={followUpMessage}
                    onChange={(e) => setFollowUpMessage(e.target.value)}
                    className="w-full px-3 py-2 border border-border rounded-button focus:outline-none focus:ring-2 focus:ring-slate-400"
                    placeholder="Например: Как именно сократить расходы на еду?"
                    rows={2}
                  />
                  <Button
                    type="submit"
                    variant="primary"
                    disabled={loadingFollowUp || !followUpMessage.trim()}
                    className="w-full py-3.5"
                  >
                    {loadingFollowUp ? 'Отправка...' : 'Задать вопрос'}
                  </Button>
                </form>
                {followUpError && (
                  <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-button text-sm text-red-700">
                    {followUpError}
                  </div>
                )}
                {followUpReply && (
                  <div className="mt-3 p-4 bg-slate-50 rounded-button text-sm whitespace-pre-wrap">
                    {followUpReply}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </Card>

      {/* Чек-лист действий из консультации */}
      {!actionsLoading && consultationActions && consultationActions.length > 0 && (
        <Card className="p-4 mb-4">
          <h2 className="text-lg font-bold text-slate-900 mb-3">Действия из консультации</h2>
          <p className="text-sm text-slate-600 mb-3">Отметьте выполненное — в следующей консультации ИИ учтёт это.</p>
          <ul className="space-y-2">
            {consultationActions.map((action) => (
              <li key={action.id} className="flex items-start gap-2">
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      await apiRequest(`/api/consultation/actions/${action.id}`, {
                        method: 'PATCH',
                        body: JSON.stringify({ done: !action.done }),
                      });
                      refetchActions();
                    } catch (e) {
                      alert('Ошибка: ' + (e instanceof Error ? e.message : String(e)));
                    }
                  }}
                  className={`shrink-0 mt-0.5 w-5 h-5 rounded border-2 flex items-center justify-center ${
                    action.done ? 'bg-green-500 border-green-500' : 'border-slate-300'
                  }`}
                  aria-label={action.done ? 'Отменить выполнение' : 'Отметить выполненным'}
                >
                  {action.done && <span className="text-white text-xs">✓</span>}
                </button>
                <span className={`text-sm ${action.done ? 'text-slate-500 line-through' : 'text-slate-700'}`}>
                  {action.action_text}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}

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
                          <div className="mt-3 pt-3 border-t border-slate-200 text-sm text-slate-700 space-y-3">
                            <div className="whitespace-pre-wrap">{item.content}</div>
                            {item.follow_ups && item.follow_ups.length > 0 && (
                              <div className="space-y-2 pt-2 border-t border-slate-100">
                                <span className="text-xs font-medium text-slate-500">Уточнения:</span>
                                {item.follow_ups.map((fu: { question: string | null; answer: string | null }, fi: number) => (
                                  <div key={fi} className="pl-2 border-l-2 border-slate-200">
                                    {fu.question && <p className="text-slate-600 mb-1"><strong>Вопрос:</strong> {fu.question}</p>}
                                    {fu.answer && <p className="whitespace-pre-wrap">{fu.answer}</p>}
                                  </div>
                                ))}
                              </div>
                            )}
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
