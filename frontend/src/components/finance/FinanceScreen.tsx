import { useState } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { TransactionsScreen } from '@/components/transactions/TransactionsScreen';
import { CapitalScreen } from '@/components/capital/CapitalScreen';

export type FinanceTab = 'transactions' | 'capital';

const FINANCE_TAB_STORAGE_KEY = 'finadvisor_active_finance_tab';

/** Объединённая вкладка «Финансы»: Транзакции и Капитал с переключением подвкладок. */
export function FinanceScreen() {
  const [tab, setTab] = useState<FinanceTab>(() => {
    if (typeof window === 'undefined') return 'transactions';
    const stored = localStorage.getItem(FINANCE_TAB_STORAGE_KEY);
    return stored === 'capital' ? 'capital' : 'transactions';
  });

  function selectTab(next: FinanceTab) {
    setTab(next);
    if (typeof window !== 'undefined') {
      localStorage.setItem(FINANCE_TAB_STORAGE_KEY, next);
    }
  }

  return (
    <div className="min-h-full pb-6">
      <PageHeader title="Финансы" />
      <div className="flex rounded-lg border border-slate-200 dark:border-slate-600 bg-slate-100 dark:bg-slate-800 p-0.5 mb-4">
        <button
          type="button"
          onClick={() => selectTab('transactions')}
          className={`flex-1 py-2 px-3 text-sm font-medium rounded-md transition-colors ${
            tab === 'transactions'
              ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 shadow-sm'
              : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
          }`}
        >
          Транзакции
        </button>
        <button
          type="button"
          onClick={() => selectTab('capital')}
          className={`flex-1 py-2 px-3 text-sm font-medium rounded-md transition-colors ${
            tab === 'capital'
              ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 shadow-sm'
              : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
          }`}
        >
          Капитал
        </button>
      </div>
      {tab === 'transactions' && <TransactionsScreen embedded />}
      {tab === 'capital' && <CapitalScreen embedded />}
    </div>
  );
}
