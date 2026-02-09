import { useState, useEffect } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { apiRequest } from '@/lib/api';
import { useTheme, type Theme as ThemeOption } from '@/contexts/ThemeContext';

interface Profile {
  gender: string | null;
  birth_date: string | null;
  marital_status: string | null;
  children_count: number | null;
  city: string | null;
}

const GENDER_OPTIONS = [
  { value: '', label: 'Не указано' },
  { value: 'male', label: 'Мужской' },
  { value: 'female', label: 'Женский' },
];

const MARITAL_OPTIONS = [
  { value: '', label: 'Не указано' },
  { value: 'single', label: 'Холост / не замужем' },
  { value: 'married', label: 'В браке' },
  { value: 'divorced', label: 'В разводе' },
  { value: 'widowed', label: 'Вдовец / вдова' },
];

const THEME_OPTIONS: { value: ThemeOption; label: string }[] = [
  { value: 'system', label: 'Как в системе' },
  { value: 'light', label: 'Светлая' },
  { value: 'dark', label: 'Тёмная' },
];

const MONTH_NAMES = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];

function daysInMonth(month: number, year: number): number {
  return new Date(year, month, 0).getDate();
}

function formatBirthDateDisplay(value: string | null): string {
  if (!value) return '';
  const [y, m, d] = value.split('-').map(Number);
  if (!m || m < 1 || m > 12) return value;
  const monthName = MONTH_NAMES[m - 1];
  return `${d ?? ''} ${monthName} ${y ?? ''}`.trim();
}

function parseBirthDate(value: string | null): { day: number; month: number; year: number } {
  const now = new Date();
  if (!value) {
    return { day: 1, month: now.getMonth() + 1, year: now.getFullYear() - 25 };
  }
  const [y, m, d] = value.split('-').map(Number);
  const month = m && m >= 1 && m <= 12 ? m : 1;
  const year = y && y > 1900 && y <= now.getFullYear() ? y : now.getFullYear() - 25;
  const maxDay = daysInMonth(month, year);
  const day = Math.min(maxDay, Math.max(1, d || 1));
  return { day, month, year };
}

function buildBirthDate(day: number, month: number, year: number): string {
  const d = String(day).padStart(2, '0');
  const m = String(month).padStart(2, '0');
  return `${year}-${m}-${d}`;
}

export function ProfileScreen() {
  const { theme, setTheme } = useTheme();
  const [profile, setProfile] = useState<Profile>({
    gender: null,
    birth_date: null,
    marital_status: null,
    children_count: null,
    city: null,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [openHelp, setOpenHelp] = useState(false);
  const [birthDateModalOpen, setBirthDateModalOpen] = useState(false);
  const [birthDateDraft, setBirthDateDraft] = useState(parseBirthDate(profile.birth_date));

  useEffect(() => {
    loadProfile();
  }, []);

  async function loadProfile() {
    try {
      const data = await apiRequest<Profile>('/api/profile');
      setProfile({
        gender: data.gender ?? null,
        birth_date: data.birth_date ?? null,
        marital_status: data.marital_status ?? null,
        children_count: data.children_count ?? null,
        city: data.city ?? null,
      });
    } catch (e) {
      console.error('Ошибка загрузки профиля:', e);
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await apiRequest('/api/profile', {
        method: 'PUT',
        body: JSON.stringify({
          gender: profile.gender || null,
          birth_date: profile.birth_date || null,
          marital_status: profile.marital_status || null,
          children_count: profile.children_count ?? null,
          city: profile.city || null,
        }),
      });
      alert('Профиль сохранён.');
    } catch (err) {
      alert('Ошибка: ' + (err instanceof Error ? err.message : String(err)));
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteAllData() {
    if (!confirm('Удалить все данные (транзакции, цели, активы, долги, историю консультаций)? Профиль и аккаунт останутся. Действие необратимо.')) return;
    setDeleting(true);
    try {
      await apiRequest('/api/me/data', { method: 'DELETE' });
      alert('Все данные удалены. Профиль сохранён.');
    } catch (err) {
      alert('Ошибка: ' + (err instanceof Error ? err.message : String(err)));
    } finally {
      setDeleting(false);
    }
  }

  if (loading) {
    return (
      <>
        <PageHeader title="Профиль" />
        <div className="flex justify-center py-8">
          <div className="w-8 h-8 border-2 border-slate-300 border-t-slate-600 rounded-full animate-spin" />
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader title="Профиль" />

      <Card className="p-4 mb-4 dark:bg-slate-800 dark:border-slate-700">
        <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 mb-2">Тема оформления</h2>
        <div className="flex flex-wrap gap-2 mb-4">
          {THEME_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setTheme(opt.value)}
              className={`px-4 py-2 rounded-button text-sm font-medium transition-colors ${
                theme === opt.value
                  ? 'bg-slate-800 dark:bg-slate-200 text-white dark:text-slate-900'
                  : 'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-600'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <hr className="border-slate-200 dark:border-slate-600 mb-4" />
        <div className="flex items-center gap-2 mb-3">
          <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">Данные профиля</h2>
          <button
            type="button"
            onClick={() => setOpenHelp(!openHelp)}
            className="min-w-[44px] min-h-[44px] flex items-center justify-center shrink-0 rounded-full"
            title="Пояснения"
          >
            <span className="w-6 h-6 rounded-full flex items-center justify-center bg-slate-100 text-slate-600 hover:bg-slate-200">?</span>
          </button>
        </div>
        {openHelp && (
          <p className="mb-3 p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-600">
            Информация используется для персональной консультации.
          </p>
        )}
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Пол</label>
            <select
              value={profile.gender ?? ''}
              onChange={(e) => setProfile((p) => ({ ...p, gender: e.target.value || null }))}
              className="w-full px-3 py-2 border border-border rounded-button focus:outline-none focus:ring-2 focus:ring-slate-400"
            >
              {GENDER_OPTIONS.map((o) => (
                <option key={o.value || 'empty'} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Дата рождения</label>
            <button
              type="button"
              onClick={() => {
                setBirthDateDraft(parseBirthDate(profile.birth_date));
                setBirthDateModalOpen(true);
              }}
              className="w-full px-3 py-2 border border-border dark:border-slate-600 rounded-button focus:outline-none focus:ring-2 focus:ring-slate-400 text-left bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
            >
              {formatBirthDateDisplay(profile.birth_date) || 'Выберите дату'}
            </button>
            {birthDateModalOpen && (
              <div
                className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/50 p-0 sm:p-4"
                onClick={() => setBirthDateModalOpen(false)}
              >
                <div
                  className="w-full max-h-[85vh] overflow-auto rounded-t-xl sm:rounded-xl bg-white dark:bg-slate-800 shadow-xl p-4 border-t border-slate-200 dark:border-slate-700"
                  onClick={(e) => e.stopPropagation()}
                >
                  <p className="text-sm font-medium text-slate-900 dark:text-slate-100 mb-3">Дата рождения</p>
                  <div className="grid grid-cols-3 gap-2 mb-4">
                    <div>
                      <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">День</label>
                      <select
                        value={birthDateDraft.day}
                        onChange={(e) => setBirthDateDraft((d) => ({ ...d, day: Number(e.target.value) }))}
                        className="w-full px-2 py-2 border border-slate-300 dark:border-slate-600 rounded-button bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 text-sm"
                      >
                        {Array.from({ length: daysInMonth(birthDateDraft.month, birthDateDraft.year) }, (_, i) => i + 1).map((n) => (
                          <option key={n} value={n}>{n}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">Месяц</label>
                      <select
                        value={birthDateDraft.month}
                        onChange={(e) => {
                          const month = Number(e.target.value);
                          setBirthDateDraft((d) => ({
                            ...d,
                            month,
                            day: Math.min(d.day, daysInMonth(month, d.year)),
                          }));
                        }}
                        className="w-full px-2 py-2 border border-slate-300 dark:border-slate-600 rounded-button bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 text-sm"
                      >
                        {MONTH_NAMES.map((name, i) => (
                          <option key={i} value={i + 1}>{name}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">Год</label>
                      <select
                        value={birthDateDraft.year}
                        onChange={(e) => {
                          const year = Number(e.target.value);
                          setBirthDateDraft((d) => ({
                            ...d,
                            year,
                            day: Math.min(d.day, daysInMonth(d.month, year)),
                          }));
                        }}
                        className="w-full px-2 py-2 border border-slate-300 dark:border-slate-600 rounded-button bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 text-sm"
                      >
                        {Array.from({ length: 101 }, (_, i) => new Date().getFullYear() - 100 + i).reverse().map((y) => (
                          <option key={y} value={y}>{y}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant="secondary"
                      className="flex-1"
                      onClick={() => setBirthDateModalOpen(false)}
                    >
                      Отмена
                    </Button>
                    <Button
                      type="button"
                      variant="primary"
                      className="flex-1"
                      onClick={() => {
                        setProfile((p) => ({
                          ...p,
                          birth_date: buildBirthDate(birthDateDraft.day, birthDateDraft.month, birthDateDraft.year),
                        }));
                        setBirthDateModalOpen(false);
                      }}
                    >
                      Готово
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Семейное положение</label>
            <select
              value={profile.marital_status ?? ''}
              onChange={(e) => setProfile((p) => ({ ...p, marital_status: e.target.value || null }))}
              className="w-full px-3 py-2 border border-border rounded-button focus:outline-none focus:ring-2 focus:ring-slate-400"
            >
              {MARITAL_OPTIONS.map((o) => (
                <option key={o.value || 'empty'} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Количество детей</label>
            <input
              type="number"
              min={0}
              max={20}
              value={profile.children_count ?? ''}
              onChange={(e) => {
                const v = e.target.value;
                setProfile((p) => ({ ...p, children_count: v === '' ? null : parseInt(v, 10) }));
              }}
              className="w-full px-3 py-2 border border-border rounded-button focus:outline-none focus:ring-2 focus:ring-slate-400"
              placeholder="0"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Город проживания</label>
            <input
              type="text"
              value={profile.city ?? ''}
              onChange={(e) => setProfile((p) => ({ ...p, city: e.target.value || null }))}
              className="w-full px-3 py-2 border border-border rounded-button focus:outline-none focus:ring-2 focus:ring-slate-400"
              placeholder="Например: Москва"
            />
          </div>
          <Button type="submit" variant="primary" className="w-full py-3.5" disabled={saving}>
            {saving ? 'Сохранение...' : 'Сохранить'}
          </Button>
        </form>
      </Card>

      <Card className="p-4 mb-4">
        <h2 className="text-sm font-bold text-slate-900 mb-2">Удаление данных</h2>
        <p className="text-sm text-slate-600 mb-3">
          Удаляются все транзакции, цели, активы, долги и история консультаций. Профиль и аккаунт (подписка) сохраняются.
        </p>
        <Button
          type="button"
          variant="secondary"
          className="w-full py-3.5 border-red-200 text-red-700 hover:bg-red-50"
          onClick={handleDeleteAllData}
          disabled={deleting}
        >
          {deleting ? 'Удаление...' : 'Удалить все данные'}
        </Button>
      </Card>
    </>
  );
}
