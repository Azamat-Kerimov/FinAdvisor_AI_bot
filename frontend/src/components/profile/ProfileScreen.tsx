import { useState, useEffect } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { apiRequest } from '@/lib/api';

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

export function ProfileScreen() {
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

      <Card className="p-4 mb-4">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="text-lg font-bold text-slate-900">Данные профиля</h2>
          <button
            type="button"
            onClick={() => setOpenHelp(!openHelp)}
            className="rounded-full w-8 h-8 flex items-center justify-center bg-slate-100 text-slate-600 hover:bg-slate-200 shrink-0"
            title="Пояснения"
          >
            ?
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
            <label className="block text-sm font-medium text-slate-700 mb-1">Дата рождения</label>
            <input
              type="date"
              value={profile.birth_date ?? ''}
              onChange={(e) => setProfile((p) => ({ ...p, birth_date: e.target.value || null }))}
              className="w-full px-3 py-2 border border-border rounded-button focus:outline-none focus:ring-2 focus:ring-slate-400"
            />
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
        <h2 className="text-lg font-bold text-slate-900 mb-2">Удаление данных</h2>
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
