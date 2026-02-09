/** Обновление цвета шапки/фона Telegram Mini App — влияет на стиль статус-бара iOS (светлый фон → чёрные иконки). */
export function setTelegramHeaderForTheme(resolved: 'light' | 'dark') {
  const tg = (typeof window !== 'undefined' && (window as unknown as { Telegram?: { WebApp?: { setHeaderColor?: (c: string) => void; setBackgroundColor?: (c: string) => void } } }).Telegram?.WebApp);
  if (!tg) return;
  const headerBg = resolved === 'dark' ? '#0f172a' : '#ffffff';
  const pageBg = resolved === 'dark' ? '#0f172a' : '#f8fafc';
  if (typeof tg.setHeaderColor === 'function') tg.setHeaderColor(headerBg);
  if (typeof tg.setBackgroundColor === 'function') tg.setBackgroundColor(pageBg);
}
