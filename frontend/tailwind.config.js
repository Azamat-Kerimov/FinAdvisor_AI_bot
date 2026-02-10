/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        // Палитра в духе Telegram Mini Apps (светлая тема)
        tg: {
          bg: 'var(--tg-bg, #f4f4f5)',
          'secondary-bg': 'var(--tg-secondary-bg, #ffffff)',
          'section-bg': 'var(--tg-section-bg, rgba(255,255,255,0.9))',
          text: 'var(--tg-text, #000000)',
          hint: 'var(--tg-hint, #999999)',
          link: 'var(--tg-link, #2481cc)',
          panel: 'var(--tg-panel, #ffffff)',
        },
        // Сохраняем семантику для доходов/расходов
        income: { DEFAULT: '#10B981', light: '#D1FAE5' },
        expense: { DEFAULT: '#EF4444', light: '#FEE2E2' },
        savings: { DEFAULT: '#2481cc', light: '#E3F2FD' },
        surface: { DEFAULT: 'var(--tg-bg, #f4f4f5)', card: 'var(--tg-secondary-bg, #ffffff)' },
        muted: 'var(--tg-hint, #64748B)',
        border: 'var(--tg-border, #e5e5e5)',
      },
      borderRadius: {
        // Более округлые элементы в духе таббара
        card: '16px',
        button: '999px',
        // Для полей ввода оставляем мягкое скругление
        input: '8px',
      },
      boxShadow: {
        card: '0 1px 1px rgba(0,0,0,0.03)',
        'card-hover': '0 1px 3px rgba(0,0,0,0.05)',
      },
    },
  },
  plugins: [],
};
