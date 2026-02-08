import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { ExampleReportImage } from '@/components/ui/ExampleReportImage';

/** Вкладка «Помощь» — описание приложения и как им пользоваться */
export function HelpScreen() {
  return (
    <div className="min-h-full bg-slate-50 text-slate-900 pb-6">
      <PageHeader title="Помощь" />

      <Card className="p-4 mb-4 bg-white border border-slate-200 shadow-card">
        <h2 className="text-lg font-bold text-slate-900 mb-3">Добро пожаловать!</h2>
        <p className="text-sm text-slate-800 mb-3 leading-relaxed">
          FinAdvisor — ваш персональный финансовый помощник. Здесь вы ведёте учёт денег, ставите цели и получаете консультации ИИ на основе ваших реальных данных (транзакции, активы, долги).
        </p>
        <p className="text-sm font-medium text-slate-900 mb-2">Что умеет приложение:</p>
        <ul className="text-sm text-slate-800 space-y-2 mb-3 list-disc list-inside leading-relaxed">
          <li><strong>Транзакции</strong> — добавляйте доходы и расходы вручную или загружайте выписку Excel из банка (Сбер, Т‑Банк).</li>
          <li><strong>Капитал</strong> — указывайте активы (счета, вклады, акции) и долги (кредиты, рассрочки).</li>
          <li><strong>Цели</strong> — задавайте финансовые цели; прогресс считается автоматически по ликвидному капиталу.</li>
          <li><strong>Консультации ИИ</strong> — получайте персональные рекомендации и план действий по вашим цифрам. Одна сессия = один день (консультация + уточняющие вопросы в тот же день не тратят лимит). Бесплатно: 1 сессия в месяц, по подписке: 5 сессий в месяц.</li>
          <li><strong>Профиль</strong> — пол, возраст, семья, город для более точных советов.</li>
        </ul>
        <p className="text-sm text-slate-700 mb-4">
          На главной вы увидите денежный поток, чистый капитал, сравнение с целевыми нормами, прогресс относительно себя и последние рекомендации ИИ.
        </p>
        <p className="text-sm font-medium text-slate-900 mb-2">Примеры отчётов:</p>
        <div className="grid grid-cols-1 gap-3">
          <div className="rounded-lg border border-slate-200 overflow-hidden bg-slate-50">
            <p className="text-xs font-medium text-slate-700 p-2">Денежный поток</p>
            <ExampleReportImage
              src="/examples/cashflow.png"
              alt="Пример: денежный поток — расходы, доходы, разница, график по месяцам"
              className="w-full h-auto object-contain max-h-48"
            />
          </div>
          <div className="rounded-lg border border-slate-200 overflow-hidden bg-slate-50">
            <p className="text-xs font-medium text-slate-700 p-2">Чистый капитал и финансовый путь</p>
            <ExampleReportImage
              src="/examples/capital.png"
              alt="Пример: чистый капитал — активы, пассивы, график динамики"
              className="w-full h-auto object-contain max-h-48"
            />
          </div>
        </div>
      </Card>
    </div>
  );
}
