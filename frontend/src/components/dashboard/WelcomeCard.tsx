import { Card } from '@/components/ui/Card';

/** Fallback при ошибке/таймауте загрузки статистики. Минимум текста, без спиннера. */
export function WelcomeCard() {
  return (
    <Card className="p-6 text-center">
      <h2 className="text-lg font-semibold text-slate-900 mb-2">Добро пожаловать</h2>
      <p className="text-sm text-muted leading-relaxed">
        Добавьте операции или загрузите выписку из Сбера или Т‑Банка — статистика появится здесь.
      </p>
    </Card>
  );
}
