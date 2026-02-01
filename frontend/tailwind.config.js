/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        // Fintech palette: calm, scannable
        income: { DEFAULT: '#10B981', light: '#D1FAE5' },
        expense: { DEFAULT: '#EF4444', light: '#FEE2E2' },
        savings: { DEFAULT: '#3B82F6', light: '#DBEAFE' },
        surface: { DEFAULT: '#F8FAFC', card: '#FFFFFF' },
        muted: '#64748B',
        border: '#E2E8F0',
      },
      borderRadius: {
        card: '12px',
        button: '8px',
      },
      boxShadow: {
        card: '0 1px 3px rgba(0,0,0,0.06)',
        'card-hover': '0 4px 12px rgba(0,0,0,0.08)',
      },
    },
  },
  plugins: [],
};
