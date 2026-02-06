/** Ответ /api/stats — статистика за выбранный месяц */
export interface Stats {
  month?: number;
  year?: number;
  total_income: number;
  total_expense: number;
  income_by_category: Record<string, number>;
  expense_by_category: Record<string, number>;
  reserve_recommended: number;
  insight: string;
}

/** Элемент ответа /api/stats/monthly */
export interface MonthlyBalanceItem {
  year: number;
  month: number;
  label: string;
  income: number;
  expense: number;
  difference: number;
}

/** Ответ /api/capital/summary */
export interface CapitalSummary {
  assets: number;
  liabilities: number;
  net: number;
}

/** Элемент ответа /api/capital/history */
export interface CapitalHistoryItem {
  year: number;
  month: number;
  label: string;
  assets: number;
  liabilities: number;
  net: number;
}

/** Элемент ответа /api/consultation/history */
export interface ConsultationHistoryItem {
  content: string;
  date: string;
}
