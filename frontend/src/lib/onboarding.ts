/** Утилиты для управления онбордингом */

export const ONBOARDING_STORAGE_KEY = 'finadvisor_onboarding_seen';
export const PROGRESS_CLOSED_KEY = 'finadvisor_progress_closed';

/** Проверяет, был ли показан онбординг */
export function isOnboardingSeen(): boolean {
  if (typeof localStorage === 'undefined') return false;
  return localStorage.getItem(ONBOARDING_STORAGE_KEY) === 'true';
}

/** Проверяет, был ли закрыт блок прогресса */
export function isProgressClosed(): boolean {
  if (typeof localStorage === 'undefined') return false;
  return localStorage.getItem(PROGRESS_CLOSED_KEY) === 'true';
}

/** Отмечает онбординг как просмотренный */
export function markOnboardingSeen(): void {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(ONBOARDING_STORAGE_KEY, 'true');
  }
}

/** Отмечает блок прогресса как закрытый */
export function markProgressClosed(): void {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(PROGRESS_CLOSED_KEY, 'true');
  }
}

/** Сбрасывает онбординг (показывает снова) */
export function resetOnboarding(): void {
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem(ONBOARDING_STORAGE_KEY);
    localStorage.removeItem(PROGRESS_CLOSED_KEY);
  }
  // Перезагружаем страницу, чтобы применить изменения
  window.location.reload();
}
