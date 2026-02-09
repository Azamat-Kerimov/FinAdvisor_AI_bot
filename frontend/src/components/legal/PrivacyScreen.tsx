import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';

/** Экран «Политика конфиденциальности». Текст можно заменить на полную версию. */
export function PrivacyScreen() {
  return (
    <div className="min-h-full bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100 pb-6">
      <PageHeader title="Политика конфиденциальности" />

      <Card className="p-4 mb-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-card">
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-4 italic">
          Страница на стадии разработки, скоро будет красиво.
        </p>
        <div className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
          <p className="mb-3 leading-relaxed">
            Политика конфиденциальности описывает, какие данные собирает приложение FinAdvisor и как они используются.
          </p>
          <p className="mb-3 leading-relaxed">
            Мы храним только данные, необходимые для работы сервиса: транзакции, цели, профиль и историю консультаций. Разместите здесь полный текст политики конфиденциальности.
          </p>
        </div>
      </Card>
    </div>
  );
}
