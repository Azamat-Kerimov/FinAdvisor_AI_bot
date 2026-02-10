import { useState } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { ExampleReportImage } from '@/components/ui/ExampleReportImage';
import { Button } from '@/components/ui/Button';
import { resetOnboarding } from '@/lib/onboarding';

type HelpItemId = string;

interface HelpItem {
  id: HelpItemId;
  title: string;
  children: React.ReactNode;
}

/** Вкладка «Помощь» — раскрывающиеся блоки по темам (1 тема = 1 элемент) */
export function HelpScreen() {
  const [openIds, setOpenIds] = useState<Set<HelpItemId>>(new Set());

  const toggle = (id: HelpItemId) => {
    setOpenIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const items: HelpItem[] = [
    {
      id: 'about',
      title: 'О приложении',
      children: (
        <>
          <p className="text-sm text-slate-800 mb-3 leading-relaxed">
            FinAdvisor — ваш персональный финансовый помощник. Здесь вы ведёте учёт денег, ставите цели и получаете консультации ИИ на основе ваших реальных данных (транзакции, активы, долги).
          </p>
          <p className="text-sm font-medium text-slate-900 mb-2">Что умеет приложение:</p>
          <ul className="text-sm text-slate-800 space-y-2 list-disc list-inside leading-relaxed">
            <li><strong>Транзакции</strong> — доходы и расходы вручную или выписка Excel из банка.</li>
            <li><strong>Капитал</strong> — активы (счета, вклады, акции) и долги (кредиты, рассрочки).</li>
            <li><strong>Цели</strong> — финансовые цели; прогресс считается по ликвидному капиталу.</li>
            <li><strong>Консультации ИИ</strong> — персональные рекомендации по вашим цифрам. Сессия = один день; уточняющие вопросы в тот же день не тратят лимит. Бесплатно: 1 сессия в месяц, по подписке: 5 сессий в месяц.</li>
            <li><strong>Профиль</strong> — пол, возраст, семья, город для более точных советов.</li>
          </ul>
        </>
      ),
    },
    {
      id: 'transactions',
      title: 'Транзакции',
      children: (
        <p className="text-sm text-slate-800 leading-relaxed">
          Добавляйте доходы и расходы вручную или загружайте выписку Excel из банка (Сбер, Т‑Банк и др.). На главной отображаются денежный поток, сравнение с целевыми нормами и прогресс относительно себя за последние месяцы.
        </p>
      ),
    },
    {
      id: 'capital',
      title: 'Капитал',
      children: (
        <p className="text-sm text-slate-800 leading-relaxed">
          Указывайте активы (счета, вклады, акции, облигации, наличные и т.д.) и долги (кредиты, займы, рассрочки). Чистый капитал = Активы − Долги. Данные используются для расчёта резервного фонда, прогресса целей и консультаций ИИ.
        </p>
      ),
    },
    {
      id: 'goals',
      title: 'Цели и прогресс цели',
      children: (
        <p className="text-sm text-slate-800 leading-relaxed">
          Прогресс цели = Ликвидный капитал / Целевая сумма. Ликвидный капитал = сумма ликвидных активов (депозит, акции, облигации, наличные, банковский счёт, криптовалюта) − обязательства, уменьшающие ликвидный капитал (кредит, займ, кредитная карта, рассрочка).
        </p>
      ),
    },
    {
      id: 'reserve',
      title: 'Резервный фонд (главная)',
      children: (
        <p className="text-sm text-slate-800 leading-relaxed">
          Резерв считается так: ликвидный капитал (активы: депозиты, счета, наличные и т.д. минус ликвидные долги) делим на средние месячные расходы за последние 3 месяца. Рекомендуется иметь запас на 3–6 месяцев расходов.
        </p>
      ),
    },
    {
      id: 'benchmarks',
      title: 'Главная: сравнение с целевыми нормами',
      children: (
        <>
          <p className="text-sm text-slate-800 mb-2 leading-relaxed">
            «У вас» — ваша фактическая доля в процентах от дохода. «Цель» — рекомендуемый диапазон значений.
          </p>
          <p className="text-sm text-slate-800 mb-2 leading-relaxed">
            Доход — это налогооблагаемый доход: зарплата, дивиденды и купоны, прочие поступления. Если данных меньше чем за год, расчёт делается за доступный период.
          </p>
          <p className="text-sm text-slate-800 leading-relaxed">
            В отчёте отображаются: Сбережения; категории, где рекомендуемая норма превышена.
          </p>
        </>
      ),
    },
    {
      id: 'capital-block',
      title: 'Главная: чистый капитал',
      children: (
        <p className="text-sm text-slate-800 leading-relaxed">
          Активы — сумма всех активов (счета, вклады, акции, облигации, наличные и т.д.) по последним введённым значениям. Долги — сумма долгов (кредиты, займы, рассрочки). Чистый капитал = Активы − Долги. График «Финансовый путь» показывает, как активы, долги и чистый капитал менялись по месяцам.
        </p>
      ),
    },
    {
      id: 'consultation',
      title: 'Консультация ИИ',
      children: (
        <p className="text-sm text-slate-800 leading-relaxed">
          Для генерации ответа используются вся информация о транзакциях, капитале и ваши цели, а также история ваших запросов. Заполните остальные вкладки для более качественного ответа.
        </p>
      ),
    },
    {
      id: 'send-message',
      title: 'Сформулировать цель (ИИ)',
      children: (
        <p className="text-sm text-slate-800 leading-relaxed">
          ИИ извлечёт цели из сообщения и добавит их автоматически. Для пассивного дохода ИИ рассчитает необходимый капитал.
        </p>
      ),
    },
    {
      id: 'profile',
      title: 'Профиль',
      children: (
        <p className="text-sm text-slate-800 leading-relaxed">
          Информация (пол, возраст, семья, город) используется для персональной консультации и более точных рекомендаций.
        </p>
      ),
    },
    {
      id: 'rent-vs-buy',
      title: 'Аренда или покупка (сценарии)',
      children: (
        <p className="text-sm text-slate-800 leading-relaxed">
          Сравнение: покупка квартиры в ипотеку vs аренда и инвестирование разницы. Срок кредита равен горизонту сравнения. Зелёные поля — ввод. Результат показывает, что выгоднее к концу периода, график и таблица по годам.
        </p>
      ),
    },
    {
      id: 'scenario-analysis',
      title: 'Сценарный анализ',
      children: (
        <>
          <p className="text-sm text-slate-800 mb-2 leading-relaxed">
            Раздел показывает разбивку портфеля по категориям (Акции, Облигации, Недвижимость, Крипто, Кэш, Прочее) и таблицу влияния факторов (ключевая ставка, инфляция, экономический рост и др.) на каждый тип активов.
          </p>
          <p className="text-sm text-slate-800 leading-relaxed">
            Блок «Чекап рисков портфеля» даёт персонализированные подсказки по рискам и ситуациям, когда выигрываете, в зависимости от долей в портфеле.
          </p>
        </>
      ),
    },
    {
      id: 'examples',
      title: 'Примеры отчётов',
      children: (
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
              alt="Пример: чистый капитал — активы, долги, график динамики"
              className="w-full h-auto object-contain max-h-48"
            />
          </div>
        </div>
      ),
    },
  ];

  return (
    <div className="min-h-full text-slate-900 pb-6">
      <PageHeader title="Помощь" />

      <Card className="p-0 mb-4 bg-white border border-slate-200 shadow-card overflow-hidden">
        <ul className="divide-y divide-slate-200">
          {items.map((item) => {
            const isOpen = openIds.has(item.id);
            return (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => toggle(item.id)}
                  className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left hover:bg-slate-50 transition-colors focus:outline-none focus:ring-2 focus:ring-inset focus:ring-slate-300"
                  aria-expanded={isOpen}
                >
                  <span className="text-sm font-bold text-slate-900 dark:text-slate-100">{item.title}</span>
                  <span
                    className={`shrink-0 text-slate-500 text-xs transition-transform ${isOpen ? 'rotate-0' : '-rotate-90'}`}
                    aria-hidden
                  >
                    ▼
                  </span>
                </button>
                {isOpen && (
                  <div className="px-4 pb-4 pt-0 text-slate-700 border-t border-slate-100 bg-slate-50/50">
                    {item.children}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </Card>

      <div className="px-4">
        <Button
          type="button"
          variant="primary"
          onClick={resetOnboarding}
          className="w-full py-3.5"
        >
          Пройти обучение снова
        </Button>
      </div>
    </div>
  );
}
