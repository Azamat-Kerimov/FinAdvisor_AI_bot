import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';

const FEEDBACK_LINK = import.meta.env.VITE_FEEDBACK_LINK ?? 'https://t.me/FinAdvisorBot';

function openFeedback() {
  const w = window as Window & { Telegram?: { WebApp?: { openTelegramLink?: (url: string) => void; openLink?: (url: string) => void } } };
  if (w.Telegram?.WebApp?.openTelegramLink) {
    w.Telegram.WebApp.openTelegramLink(FEEDBACK_LINK);
  } else {
    window.open(FEEDBACK_LINK, '_blank', 'noopener,noreferrer');
  }
}

/** Экран «Обратная связь» — переход в Telegram для связи с поддержкой. */
export function FeedbackScreen() {
  return (
    <div className="min-h-full text-slate-900 dark:text-slate-100 pb-6">
      <PageHeader title="Обратная связь" />

      <Card className="p-4 mb-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-card">
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-4 italic">
          Страница на стадии разработки, скоро будет красиво.
        </p>
        <p className="text-sm text-slate-700 dark:text-slate-300 mb-4 leading-relaxed">
          Напишите нам — мы учтём ваши предложения и замечания по приложению.
        </p>
        <Button onClick={openFeedback} variant="primary">
          Написать в Telegram
        </Button>
      </Card>
    </div>
  );
}
