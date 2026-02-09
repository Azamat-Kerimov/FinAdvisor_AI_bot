import { useState, type RefObject } from 'react';
import html2canvas from 'html2canvas';
import { logAction } from '@/lib/api';

interface ShareButtonProps {
  title: string;
  text: string;
  className?: string;
  /** Только иконка (серый цвет), без текста */
  iconOnly?: boolean;
  /** Элемент для захвата в картинку; при наличии шарится изображение блока вместо текста */
  captureRef?: RefObject<HTMLElement | null>;
}

/** Иконка «Поделиться»: три точки и линии, повёрнута на 90° против часовой стрелки, серый. */
function ShareIcon({ className = '' }: { className?: string }) {
  return (
    <svg
      className={className}
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="currentColor"
      stroke="none"
      aria-hidden
    >
      <circle cx="6" cy="12" r="2" />
      <circle cx="16" cy="7" r="2" />
      <circle cx="16" cy="17" r="2" />
      <path
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        d="M8 12 L 14 7 M 8 12 L 14 17"
      />
    </svg>
  );
}

/** Ссылка на бота для вставки в отчёт при пересылке */
const SHARE_BOT_LINK = 'https://t.me/FinAdvisor_AI_bot';

function shareTextOnly(title: string, text: string, setCopied: (v: boolean) => void) {
  const reportText = `${text}\n\nFinAdvisor: ${SHARE_BOT_LINK}`;
  const sharePayload = { title, text: reportText };
  if (typeof navigator !== 'undefined' && navigator.share) {
    return navigator.share(sharePayload);
  }
  return navigator.clipboard?.writeText(`${title}\n\n${reportText}`).then(() => {
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  });
}

/**
 * Кнопка «Поделиться». Если передан captureRef — захватывает блок в картинку и шарит изображение (и подпись со ссылкой на бота).
 * Иначе шарит только текст с ссылкой. Web Share API или fallback (копирование в буфер).
 */
export function ShareButton({ title, text, className = '', captureRef }: ShareButtonProps) {
  const [copied, setCopied] = useState(false);

  async function handleShare() {
    const reportText = `${text}\n\nFinAdvisor: ${SHARE_BOT_LINK}`;

    if (captureRef?.current && typeof navigator !== 'undefined' && navigator.share) {
      try {
        const canvas = await html2canvas(captureRef.current, {
          scale: 2,
          useCORS: true,
          logging: false,
          backgroundColor: undefined,
        });
        const blob = await new Promise<Blob | null>((resolve) => {
          canvas.toBlob(resolve, 'image/png', 0.95);
        });
        if (blob) {
          const file = new File([blob], 'denezhnyj-potok.png', { type: 'image/png' });
          if (navigator.canShare?.({ files: [file] })) {
            await navigator.share({
              title,
              text: `FinAdvisor: ${SHARE_BOT_LINK}`,
              files: [file],
            });
            logAction('share', { block: title.slice(0, 200), asImage: true });
            return;
          }
        }
      } catch (e) {
        if ((e as Error)?.name === 'AbortError') return;
      }
    }

    try {
      await shareTextOnly(title, text, setCopied);
      logAction('share', { block: title.slice(0, 200) });
    } catch (e) {
      if ((e as Error)?.name === 'AbortError') return;
      try {
        await navigator.clipboard?.writeText(`${title}\n\n${reportText}`);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
        logAction('share', { block: title.slice(0, 200), method: 'clipboard' });
      } catch {
        // ignore
      }
    }
  }

  return (
    <button
      type="button"
      onClick={handleShare}
      className={`inline-flex items-center justify-center rounded-button min-w-[44px] min-h-[44px] text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors ${className}`}
      title={copied ? 'Скопировано' : 'Поделиться'}
      aria-label="Поделиться"
    >
      <ShareIcon className="w-5 h-5" />
    </button>
  );
}
