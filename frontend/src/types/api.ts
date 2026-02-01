/** Ответ /api/stats — статистика за текущий месяц */
export interface Stats {
  total_income: number;
  total_expense: number;
  income_by_category: Record<string, number>;
  expense_by_category: Record<string, number>;
  reserve_recommended: number;
  insight: string;
}
