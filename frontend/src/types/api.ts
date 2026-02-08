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

/** Элемент ответа /api/consultation/history (сессия = 1 день: консультация + уточнения) */
export interface ConsultationHistoryItem {
  date: string;
  content: string;
  follow_ups?: Array<{ question: string | null; answer: string | null }>;
}

/** Ответ /api/benchmarks */
export interface BenchmarksResponse {
  total_income: number;
  total_expense: number;
  categories: Array<{ name: string; user_pct: number; target_low: number; target_high: number }>;
  savings: { user_pct: number; target_low: number; target_high: number } | null;
  period_months?: number;
}

/** Ответ /api/progress-vs-self */
export interface ProgressVsSelfResponse {
  period_before: string;
  period_now: string;
  categories: Array<{ category: string; before: number; now: number }>;
}

/** Ответ /api/onboarding-progress */
export interface OnboardingProgressResponse {
  has_transactions: boolean;
  has_capital: boolean;
  has_profile: boolean;
  has_consultation: boolean;
}

/** Ответ /api/alerts */
export interface AlertsResponse {
  alerts: Array<{ type: string; text: string }>;
}

/** Ответ /api/focus-goal */
export interface FocusGoalResponse {
  id: number;
  title: string;
  target_amount: number;
  for_month: number;
  for_year: number;
  achieved_at: string | null;
}

/** Элемент /api/consultation/actions */
export interface ConsultationActionItem {
  id: number;
  action_text: string;
  done: boolean;
  created_at: string | null;
}

/** Ответ /api/badges */
export interface BadgesResponse {
  badges: Array<{ id: string; label: string }>;
}

/** Ответ /api/simulator */
export interface SimulatorResponse {
  goal_months: number | null;
  debt_months: number | null;
  total_debt?: number;
}
