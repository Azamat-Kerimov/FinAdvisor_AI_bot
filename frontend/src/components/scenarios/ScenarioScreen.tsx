import { useState, useMemo, useEffect } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { useCapitalSummary } from '@/hooks/useStats';
import { apiRequest } from '@/lib/api';
import { ShareButton } from '@/components/ui/ShareButton';

function formatMoney(value: number): string {
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(Math.round(value));
}

/** Краткая подпись для оси: "0", "5.0 млн", "10.0 тыс." — один знак после запятой */
function formatAxisMoney(value: number): string {
  if (value === 0) return '0';
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(1)} млн`;
  if (abs >= 1_000) return `${(value / 1_000).toFixed(1)} тыс.`;
  return value.toFixed(1);
}

/** Платёж по аннуитету: PMT = PV * (r*(1+r)^n) / ((1+r)^n - 1) */
function annuityPayment(pv: number, annualRatePct: number, years: number): number {
  if (years <= 0 || pv <= 0) return 0;
  const r = annualRatePct / 100 / 12;
  const n = years * 12;
  if (r === 0) return pv / n;
  return (pv * (r * Math.pow(1 + r, n))) / (Math.pow(1 + r, n) - 1);
}

/** Остаток долга после k месяцев */
function loanBalance(pv: number, annualRatePct: number, years: number, monthsPaid: number): number {
  if (monthsPaid >= years * 12) return 0;
  const pmt = annuityPayment(pv, annualRatePct, years);
  const r = annualRatePct / 100 / 12;
  return pv * Math.pow(1 + r, monthsPaid) - pmt * ((Math.pow(1 + r, monthsPaid) - 1) / r);
}

/** Эффективная месячная ставка из годовой (капитализация раз в месяц): (1 + r_год)^(1/12) - 1 */
function effectiveMonthlyRate(annualRatePct: number): number {
  const onePlusAnnual = 1 + annualRatePct / 100;
  return Math.pow(onePlusAnnual, 1 / 12) - 1;
}

export interface RentVsBuyInputs {
  propertyPrice: number;
  downPaymentPct: number;
  ratePct: number;
  termYears: number; // одновременно срок кредита и горизонт сравнения
  monthlyRent: number;
  rentIndexationPct: number;
  appreciationPct: number;
  investmentReturnPct: number;
}

interface RentVsBuyRow {
  year: number;
  buyEquity: number;
  rentPortfolio: number;
  buyPropertyValue: number;
  buyLoanBalance: number;
}

function computeRentVsBuy(input: RentVsBuyInputs): {
  recommendation: 'buy' | 'rent';
  monthlyPayment: number;
  loanAmount: number;
  rows: RentVsBuyRow[];
} {
  const price = input.propertyPrice;
  const downPct = input.downPaymentPct / 100;
  const loanAmount = price * (1 - downPct);
  const horizon = Math.max(1, Math.min(30, input.termYears)); // срок кредита = горизонт
  const monthlyPayment = annuityPayment(loanAmount, input.ratePct, horizon);
  const rows: RentVsBuyRow[] = [];
  let rentPortfolio = price * downPct;
  // Эффективная месячная ставка для инвестиций (как в Excel: (1+годовая)^(1/12)-1)
  const rMonthly = effectiveMonthlyRate(input.investmentReturnPct);
  const appr = input.appreciationPct / 100;
  const rentIndex = input.rentIndexationPct / 100;

  for (let y = 1; y <= horizon; y++) {
    const monthsPaid = Math.min(y * 12, horizon * 12);
    const buyLoanBal = loanBalance(loanAmount, input.ratePct, horizon, monthsPaid);
    // Рост стоимости жилья за y лет: (1+годовая)^y
    const buyPropertyValue = price * Math.pow(1 + appr, y);
    const buyEquity = Math.max(0, buyPropertyValue - buyLoanBal);

    const rentInYearY = input.monthlyRent * Math.pow(1 + rentIndex, y - 1);
    const monthlyInvest = monthlyPayment - rentInYearY;
    for (let m = 0; m < 12; m++) {
      rentPortfolio = rentPortfolio * (1 + rMonthly) + monthlyInvest;
    }
    rows.push({
      year: y,
      buyEquity,
      rentPortfolio: Math.max(0, rentPortfolio),
      buyPropertyValue,
      buyLoanBalance: buyLoanBal,
    });
  }

  const last = rows[rows.length - 1];
  const recommendation = last.buyEquity >= last.rentPortfolio ? 'buy' : 'rent';
  return { recommendation, monthlyPayment, loanAmount, rows };
}

/** Блок «Аренда или покупка» */
function RentVsBuyBlock() {
  const [price, setPrice] = useState(15000000);
  const [downPct, setDownPct] = useState(20);
  const [ratePct, setRatePct] = useState(18);
  const [termYears, setTermYears] = useState(20); // срок кредита = горизонт сравнения
  const [rent, setRent] = useState(80000);
  const [rentIndexationPct, setRentIndexationPct] = useState(5);
  const [appreciationPct, setAppreciationPct] = useState(5);
  const [investReturnPct, setInvestReturnPct] = useState(12);
  const [tableVisible, setTableVisible] = useState(false);
  const [blockHelpOpen, setBlockHelpOpen] = useState(false);

  const result = useMemo(() => {
    const input: RentVsBuyInputs = {
      propertyPrice: price,
      downPaymentPct: downPct,
      ratePct: ratePct,
      termYears: termYears,
      monthlyRent: rent,
      rentIndexationPct: rentIndexationPct,
      appreciationPct: appreciationPct,
      investmentReturnPct: investReturnPct,
    };
    return computeRentVsBuy(input);
  }, [price, downPct, ratePct, termYears, rent, rentIndexationPct, appreciationPct, investReturnPct]);

  const maxChart = useMemo(() => Math.max(1, ...result.rows.map((r) => Math.max(r.buyEquity, r.rentPortfolio))), [result.rows]);

  return (
    <Card className="p-4 mb-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-card">
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">Аренда или покупка</h2>
          <button
            type="button"
            onClick={() => setBlockHelpOpen((v) => !v)}
            className="shrink-0 min-w-[44px] min-h-[44px] inline-flex items-center justify-center focus:outline-none focus:ring-2 focus:ring-slate-400 rounded-full"
            aria-label="Пояснения"
            title="Пояснения"
          >
            <span className="w-6 h-6 rounded-full inline-flex items-center justify-center bg-slate-200 text-slate-600 text-xs font-medium hover:bg-slate-300">?</span>
          </button>
        </div>
        <ShareButton
          title="Аренда или покупка — FinAdvisor"
          text={`Вывод: ${result.recommendation === 'buy' ? 'Покупка выгоднее' : 'Аренда выгоднее'}. Платёж по ипотеке: ${formatMoney(result.monthlyPayment)} ₽/мес. Сумма кредита: ${formatMoney(result.loanAmount)} ₽`}
        />
      </div>
      {blockHelpOpen && (
        <p className="text-xs text-slate-600 mb-3 p-2 rounded-lg bg-slate-100 border border-slate-200">
          Сравнение: покупка квартиры в ипотеку vs аренда и инвестирование разницы. Срок кредита равен горизонту сравнения. Зелёные поля — ввод.
        </p>
      )}
      <div className="grid grid-cols-2 gap-x-4 gap-y-3 mb-4 items-start">
        {([
          { label: 'Цена недвижимости, ₽', input: <input type="number" min={100000} step={100000} value={price} onChange={(e) => setPrice(Number(e.target.value) || 0)} className="w-full rounded border border-green-300 bg-green-50/50 px-2 py-1.5 text-sm" /> },
          { label: 'Первый взнос, %', input: <input type="number" min={0} max={100} value={downPct} onChange={(e) => setDownPct(Number(e.target.value) || 0)} className="w-full rounded border border-green-300 bg-green-50/50 px-2 py-1.5 text-sm" /> },
          { label: 'Ставка по ипотеке, % год', input: <input type="number" min={0} step={0.5} value={ratePct} onChange={(e) => setRatePct(Number(e.target.value) || 0)} className="w-full rounded border border-green-300 bg-green-50/50 px-2 py-1.5 text-sm" /> },
          { label: 'Срок кредита и горизонт, лет', input: <input type="number" min={1} max={30} value={termYears} onChange={(e) => setTermYears(Number(e.target.value) || 1)} className="w-full rounded border border-green-300 bg-green-50/50 px-2 py-1.5 text-sm" /> },
          { label: 'Аренда в месяц, ₽', input: <input type="number" min={0} step={5000} value={rent} onChange={(e) => setRent(Number(e.target.value) || 0)} className="w-full rounded border border-green-300 bg-green-50/50 px-2 py-1.5 text-sm" /> },
          { label: 'Рост стоимости жилья, % год', input: <input type="number" min={-10} step={0.5} value={appreciationPct} onChange={(e) => setAppreciationPct(Number(e.target.value) ?? 0)} className="w-full rounded border border-green-300 bg-green-50/50 px-2 py-1.5 text-sm" /> },
          { label: 'Индексация арендных платежей, %', input: <input type="number" min={0} step={0.5} value={rentIndexationPct} onChange={(e) => setRentIndexationPct(Number(e.target.value) ?? 0)} className="w-full rounded border border-green-300 bg-green-50/50 px-2 py-1.5 text-sm" />, hint: 'На сколько % в год растёт плата за аренду.' },
          { label: 'Доходность альтернативных инвестиций, % год', input: <input type="number" min={0} step={0.5} value={investReturnPct} onChange={(e) => setInvestReturnPct(Number(e.target.value) || 0)} className="w-full rounded border border-green-300 bg-green-50/50 px-2 py-1.5 text-sm" />, hint: 'Ожидаемая годовая доходность вложений (облигации, ETF и т.п.).' },
        ] as Array<{ label: string; input: React.ReactNode; hint?: string }>).map((item, i) => (
          <label key={i} className="flex flex-col text-xs text-slate-600">
            <span className="min-h-[1.25rem] leading-tight">{item.label}</span>
            <div className="mt-0.5 flex items-center">{item.input}</div>
            {item.hint && <p className="mt-0.5 text-xs text-slate-400">{item.hint}</p>}
          </label>
        ))}
      </div>

      <div className="mb-4 p-3 rounded-lg bg-slate-100 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-600">
        <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
          Вывод: {result.recommendation === 'buy' ? 'Покупка выгоднее' : <span className="text-emerald-600 dark:text-emerald-400 font-semibold">Аренда выгоднее</span>}
        </p>
        <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
          Платёж по ипотеке: {formatMoney(result.monthlyPayment)} ₽/мес. · Сумма кредита: {formatMoney(result.loanAmount)} ₽
        </p>
      </div>

      <h3 className="text-sm font-medium text-slate-700 mb-2">Чистые активы через годы</h3>
      <div className="mb-2 flex items-center gap-4 text-xs text-slate-500">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded bg-blue-500" /> Покупка (капитал в недвижимости)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded bg-emerald-500" /> Аренда (инвестиции)
        </span>
      </div>
      {(() => {
        const CHART_HEIGHT_PX = 180;
        const MIN_BAR_PX = 6;
        const axisTicks: { value: number; label: string }[] =
          maxChart <= 0
            ? [{ value: 0, label: '0' }]
            : [
                { value: 0, label: '0' },
                ...([1, 2, 3].map((i) => {
                  const v = (maxChart / 3) * i;
                  return { value: v, label: formatAxisMoney(v) };
                })),
              ];
        return (
          <div className="flex flex-col w-full">
            <div className="flex gap-0 relative" style={{ height: CHART_HEIGHT_PX, minHeight: CHART_HEIGHT_PX }}>
              <div className="border-b border-l border-slate-300 shrink-0" style={{ width: 1, height: CHART_HEIGHT_PX }} />
              <div className="flex-1 min-w-0 relative flex flex-col">
                <div
                  className="absolute left-0 top-0 bottom-0 flex flex-col justify-between text-xs text-slate-600 py-0.5 z-10 pl-1 pr-1 bg-slate-50/90"
                  style={{ width: 38 }}
                >
                  {[...axisTicks].reverse().map((t) => (
                    <span key={t.value}>{t.label}</span>
                  ))}
                </div>
                <div
                  className="flex gap-1 items-end pb-0.5 flex-1"
                  style={{ height: CHART_HEIGHT_PX, minHeight: CHART_HEIGHT_PX, marginLeft: 38 }}
                >
                {result.rows.map((r) => {
                  const maxVal = Math.max(r.buyEquity, r.rentPortfolio);
                  const minVal = Math.min(r.buyEquity, r.rentPortfolio);
                  const barHeightPx = maxChart > 0 && maxVal > 0
                    ? Math.max(MIN_BAR_PX, (maxVal / maxChart) * CHART_HEIGHT_PX)
                    : 0;
                  const lowerPx = maxVal > 0 ? (minVal / maxVal) * barHeightPx : 0;
                  const upperPx = barHeightPx - lowerPx;
                  const buyFirst = r.buyEquity <= r.rentPortfolio;
                  return (
                    <div key={r.year} className="flex-1 min-w-0 flex flex-col items-stretch" style={{ minWidth: 0 }}>
                      <div
                        className="w-full flex flex-col justify-end rounded-t"
                        style={{
                          height: barHeightPx,
                          minHeight: barHeightPx > 0 ? MIN_BAR_PX : 0,
                        }}
                        title={`Год ${r.year}: покупка ${formatMoney(r.buyEquity)} ₽, аренда ${formatMoney(r.rentPortfolio)} ₽`}
                      >
                        {buyFirst ? (
                          <>
                            {upperPx > 0 && <div className="w-full bg-emerald-500 rounded-t shrink-0" style={{ height: upperPx }} />}
                            {lowerPx > 0 && <div className="w-full bg-blue-500 shrink-0" style={{ height: lowerPx }} />}
                          </>
                        ) : (
                          <>
                            {upperPx > 0 && <div className="w-full bg-blue-500 rounded-t shrink-0" style={{ height: upperPx }} />}
                            {lowerPx > 0 && <div className="w-full bg-emerald-500 shrink-0" style={{ height: lowerPx }} />}
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
                </div>
              </div>
            </div>
            <div className="flex gap-1 mt-1" style={{ marginLeft: 39 }}>
              {result.rows.map((r) => (
                <span key={r.year} className="flex-1 text-xs text-slate-500 text-center truncate min-w-0">
                  {r.year}
                </span>
              ))}
            </div>
          </div>
        );
      })()}

      <div className="mt-4">
        <button
          type="button"
          onClick={() => setTableVisible((v) => !v)}
          className="text-sm font-medium text-slate-700 hover:text-slate-900 py-1 pr-2 flex items-center gap-1"
        >
          {tableVisible ? '▼ Скрыть таблицу по годам' : '▶ Показать таблицу по годам'}
        </button>
        {tableVisible && (
          <div className="overflow-x-auto -mx-1 mt-2">
            <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="border-b border-slate-200">
              <th className="text-left py-1.5 font-medium text-slate-700">Год</th>
              <th className="text-right py-1.5 font-medium text-slate-700">Капитал (покупка)</th>
              <th className="text-right py-1.5 font-medium text-slate-700">Портфель (аренда)</th>
              <th className="text-right py-1.5 font-medium text-slate-700">Стоимость жилья</th>
              <th className="text-right py-1.5 font-medium text-slate-700">Остаток долга</th>
            </tr>
          </thead>
          <tbody>
            {result.rows.map((r) => (
              <tr key={r.year} className="border-b border-slate-100">
                <td className="py-1 text-slate-700">{r.year}</td>
                <td className="text-right py-1">{formatMoney(r.buyEquity)} ₽</td>
                <td className="text-right py-1">{formatMoney(r.rentPortfolio)} ₽</td>
                <td className="text-right py-1 text-slate-500">{formatMoney(r.buyPropertyValue)} ₽</td>
                <td className="text-right py-1 text-slate-500">{formatMoney(r.buyLoanBalance)} ₽</td>
              </tr>
            ))}
          </tbody>
            </table>
          </div>
        )}
      </div>
    </Card>
  );
}

/** Маппинг типа актива в категорию для отчёта влияния факторов */
const ASSET_TYPE_TO_CATEGORY: Record<string, 'Акции' | 'Облигации' | 'Недвижимость' | 'Крипто' | 'Кэш' | 'Прочее'> = {
  'Акции': 'Акции',
  'Облигации': 'Облигации',
  'Недвижимость': 'Недвижимость',
  'Криптовалюта': 'Крипто',
  'Депозит': 'Кэш',
  'Наличные': 'Кэш',
  'Банковский счёт': 'Кэш',
  'Драгоценные металлы': 'Прочее',
  'Прочее': 'Прочее',
};

/** Таблица влияния факторов на портфель (для кнопки ?) */
const FACTOR_IMPACT_TABLE: Array<{ factor: string; description: string; Акции: string; Облигации: string; Недвижимость: string; Крипто: string; Кэш: string }> = [
  { factor: 'Ключевая ставка', description: 'Уровень процентных ставок ЦБ', Акции: '↓', Облигации: '↓', Недвижимость: '↓', Крипто: '↓', Кэш: '↑' },
  { factor: 'Инфляция', description: 'Рост общего уровня цен', Акции: '↑/↓', Облигации: '↓', Недвижимость: '↑', Крипто: '↑/↓', Кэш: '↓' },
  { factor: 'Экономический рост', description: 'Фаза цикла: рост / рецессия', Акции: '↑', Облигации: '↓/↑', Недвижимость: '↑', Крипто: '↑', Кэш: '↑' },
  { factor: 'Курс валют', description: 'Изменение валютных курсов', Акции: '↑/↓', Облигации: '↑/↓', Недвижимость: '↑/↓', Крипто: '↑', Кэш: '↑' },
  { factor: 'Рыночная волатильность', description: 'Уровень неопределённости', Акции: '↓', Облигации: '↑', Недвижимость: '—', Крипто: '↓↓', Кэш: '↑' },
  { factor: 'Ликвидность рынков', description: 'Доступность денег в системе', Акции: '↑', Облигации: '↑', Недвижимость: '↑', Крипто: '↑↑', Кэш: '↑' },
  { factor: 'Геополитика', description: 'Войны, санкции, кризисы', Акции: '↓', Облигации: '↓', Недвижимость: '—/↓', Крипто: '↓', Кэш: '↑' },
  { factor: 'Налоги и регулирование', description: 'Изменения законов и налогов', Акции: '↓', Облигации: '↓', Недвижимость: '↓', Крипто: '↓↓', Кэш: '—' },
  { factor: 'Кредитные риски', description: 'Дефолты, банкротства', Акции: '↓', Облигации: '↓↓', Недвижимость: '—', Крипто: '↓', Кэш: '—' },
  { factor: 'Поведение инвесторов', description: 'Паника, эйфория, FOMO', Акции: '↑/↓', Облигации: '—', Недвижимость: '—', Крипто: '↑↑', Кэш: '—' },
];

/** Сценарный анализ по активам и долгам */
interface AssetItem {
  asset_id: number;
  title: string;
  type: string;
  amount: number;
}

function ScenarioAnalysisBlock() {
  const { data: summary, loading: summaryLoading } = useCapitalSummary();
  const [assetsList, setAssetsList] = useState<AssetItem[]>([]);
  const [assetsLoading, setAssetsLoading] = useState(true);
  const [factorTableOpen, setFactorTableOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    apiRequest<AssetItem[]>('/api/assets')
      .then((data) => { if (!cancelled) setAssetsList(data); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setAssetsLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const allocation = useMemo(() => {
    const byCat: Record<string, number> = { Акции: 0, Облигации: 0, Недвижимость: 0, Крипто: 0, Кэш: 0, Прочее: 0 };
    let total = 0;
    for (const a of assetsList) {
      const amt = Number(a.amount) || 0;
      if (amt <= 0) continue;
      const cat = ASSET_TYPE_TO_CATEGORY[a.type] ?? 'Прочее';
      byCat[cat] = (byCat[cat] ?? 0) + amt;
      total += amt;
    }
    const pct: Record<string, number> = {};
    for (const k of Object.keys(byCat)) pct[k] = total > 0 ? (byCat[k] / total) * 100 : 0;
    return { byCat, total, pct };
  }, [assetsList]);

  const riskReportItems = useMemo(() => {
    const items: Array<{ title: string; details: string[] }> = [];
    const { pct, total, byCat } = allocation;
    if (total === 0) return items;
    const fmt = (x: number) => formatMoney(x);
    if (pct['Акции'] >= 5) {
      items.push({
        title: `Акции — ${pct['Акции'].toFixed(0)}% портфеля (${fmt(byCat['Акции'])} ₽)`,
        details: [
          'Риски: рост ключевой ставки и волатильность рынка обычно давят на котировки; геополитика и ужесточение регулирования тоже могут снизить стоимость.',
          'Когда выигрываете: фаза экономического роста, рост ликвидности и уверенности инвесторов чаще всего поддерживают рынок акций.',
        ],
      });
    }
    if (pct['Облигации'] >= 5) {
      items.push({
        title: `Облигации — ${pct['Облигации'].toFixed(0)}% портфеля (${fmt(byCat['Облигации'])} ₽)`,
        details: [
          'Риски: рост ключевой ставки и инфляции снижает цену облигаций; дефолты эмитентов и кризисы ликвидности дают сильный отрицательный эффект.',
          'Когда выигрываете: снижение ставок и инфляции, «перелет» в акции и спрос на надёжные активы обычно положительно сказываются на облигациях.',
        ],
      });
    }
    if (pct['Недвижимость'] >= 5) {
      items.push({
        title: `Недвижимость — ${pct['Недвижимость'].toFixed(0)}% портфеля (${fmt(byCat['Недвижимость'])} ₽)`,
        details: [
          'Риски: рост ключевой ставки удорожает ипотеку и может снизить спрос и стоимость; повышение налогов и ужесточение регулирования тоже бьют по сектору. Геополитика и санкции могут дополнительно давить на рынок.',
          'Когда выигрываете: при устойчивой или растущей инфляции недвижимость часто сохраняет и приращивает стоимость в реальном выражении; рост экономики и ликвидности поддерживает спрос.',
        ],
      });
    }
    if (pct['Крипто'] >= 5) {
      items.push({
        title: `Криптовалюта — ${pct['Крипто'].toFixed(0)}% портфеля (${fmt(byCat['Крипто'])} ₽)`,
        details: [
          'Риски: высокая волатильность — при панике, ужесточении регулирования и налогов котировки могут резко падать. Рост ключевой ставки и геополитика тоже часто негативно влияют.',
          'Когда выигрываете: при росте ликвидности и ажиотаже (FOMO) возможны сильные взлёты; часть инвесторов рассматривает крипто как спекулятивный актив в фазах риска.',
        ],
      });
    }
    if (pct['Кэш'] >= 5) {
      items.push({
        title: `Кэш (счета, депозиты, наличные) — ${pct['Кэш'].toFixed(0)}% портфеля (${fmt(byCat['Кэш'])} ₽)`,
        details: [
          'Риски: при высокой инфляции покупательная способность падает; в кризисах ликвидности доступ к деньгам остаётся, но реальная доходность может быть низкой или отрицательной.',
          'Когда выигрываете: рост ключевой ставки повышает доходность по депозитам и краткосрочным инструментам; кэш даёт подушку при просадках по рисковым активам.',
        ],
      });
    }
    if (pct['Прочее'] >= 5) {
      items.push({
        title: `Прочие активы — ${pct['Прочее'].toFixed(0)}% портфеля (${fmt(byCat['Прочее'])} ₽)`,
        details: [
          'Влияние макрофакторов зависит от конкретного типа (металлы, альтернативные вложения и т.п.). Стоит оценивать каждый актив отдельно по его природе и рыночным условиям.',
        ],
      });
    }
    return items;
  }, [allocation]);

  const loading = summaryLoading || assetsLoading;

  if (loading) {
    return (
      <Card className="p-4 mb-4 bg-white border border-slate-200 shadow-card">
        <h2 className="text-base font-semibold text-slate-900 mb-3">Сценарный анализ</h2>
        <p className="text-sm text-slate-500">Загрузка данных...</p>
      </Card>
    );
  }

  if (!summary) {
    return (
      <Card className="p-4 mb-4 bg-white border border-slate-200 shadow-card">
        <h2 className="text-base font-semibold text-slate-900 mb-3">Сценарный анализ</h2>
        <p className="text-sm text-slate-500">Не удалось загрузить капитал. Заполните раздел «Капитал».</p>
      </Card>
    );
  }

  return (
    <Card className="p-4 mb-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-card">
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">Сценарный анализ</h2>
          <button
            type="button"
            onClick={() => setFactorTableOpen((v) => !v)}
            className="shrink-0 min-w-[44px] min-h-[44px] inline-flex items-center justify-center focus:outline-none focus:ring-2 focus:ring-slate-400 rounded-full"
            aria-label="Влияние факторов на портфель"
            title="Влияние факторов на портфель"
          >
            <span className="w-6 h-6 rounded-full inline-flex items-center justify-center bg-slate-200 text-slate-600 text-xs font-medium hover:bg-slate-300">?</span>
          </button>
        </div>
        <ShareButton
          title="Сценарный анализ — FinAdvisor"
          text={`Активы ${formatMoney(summary.assets)} ₽, долги ${formatMoney(summary.liabilities)} ₽. Чистый капитал: ${formatMoney(summary.net)} ₽`}
        />
      </div>
      {factorTableOpen && (
        <div className="mb-4 p-3 rounded-lg bg-slate-50 border border-slate-200 overflow-x-auto">
          <p className="text-xs font-medium text-slate-700 mb-2">Отчёт влияния факторов на портфель</p>
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="text-left py-1 font-medium text-slate-700">Фактор</th>
                <th className="text-left py-1 font-medium text-slate-700">Описание</th>
                <th className="text-center py-1 font-medium text-slate-700">Акции</th>
                <th className="text-center py-1 font-medium text-slate-700">Облигации</th>
                <th className="text-center py-1 font-medium text-slate-700">Недвижимость</th>
                <th className="text-center py-1 font-medium text-slate-700">Крипто</th>
                <th className="text-center py-1 font-medium text-slate-700">Кэш</th>
              </tr>
            </thead>
            <tbody>
              {FACTOR_IMPACT_TABLE.map((row, i) => (
                <tr key={i} className="border-b border-slate-100">
                  <td className="py-1 text-slate-800">{row.factor}</td>
                  <td className="py-1 text-slate-600">{row.description}</td>
                  <td className="text-center py-1">{row.Акции}</td>
                  <td className="text-center py-1">{row.Облигации}</td>
                  <td className="text-center py-1">{row.Недвижимость}</td>
                  <td className="text-center py-1">{row.Крипто}</td>
                  <td className="text-center py-1">{row.Кэш}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-slate-500 mt-2">↑ — положительное влияние; ↓ — отрицательное; — — слабое или нейтральное.</p>
        </div>
      )}
      <p className="text-xs text-slate-600 mb-3">
        На основе ваших активов и долгов: какие сценарии улучшают или ухудшают ваш чистый капитал.
      </p>
      <div className="mb-4 p-3 rounded-lg bg-slate-100 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-600">
        <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
          Сейчас: активы {formatMoney(summary.assets)} ₽, долги {formatMoney(summary.liabilities)} ₽
        </p>
        <p className="text-sm font-semibold text-slate-700 dark:text-slate-300 mt-1">Чистый капитал: {formatMoney(summary.net)} ₽</p>
      </div>

      {riskReportItems.length > 0 && (
        <div className="mb-4 p-3 rounded-lg bg-blue-50 border border-blue-100">
          <h3 className="text-sm font-medium text-slate-900 mb-2">Чекап рисков портфеля</h3>
          <p className="text-xs text-slate-600 mb-3">Большая часть ваших активов распределена по категориям ниже. Для каждой — основные риски и ситуации, в которых эта часть портфеля выигрывает.</p>
          <ul className="space-y-4 list-none pl-0">
            {riskReportItems.map((item, i) => (
              <li key={i} className="border-b border-blue-100 pb-3 last:border-0 last:pb-0">
                <p className="text-sm font-medium text-slate-900 mb-1.5">{item.title}</p>
                <ul className="space-y-1 text-xs text-slate-700 list-disc list-inside">
                  {item.details.map((d, j) => (
                    <li key={j}>{d}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

export function ScenarioScreen() {
  return (
    <div className="min-h-full bg-slate-50 text-slate-900">
      <PageHeader title="Сценарный анализ" />
      <RentVsBuyBlock />
      <ScenarioAnalysisBlock />
    </div>
  );
}
