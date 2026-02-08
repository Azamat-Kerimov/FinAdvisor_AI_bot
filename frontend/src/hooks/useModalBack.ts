import { useEffect, useRef, useCallback } from 'react';

const MODAL_STATE_KEY = 'finadvisor_modal';

/**
 * Закрытие модалки по кнопке «Назад» (History API).
 * При открытии делается pushState; при popstate вызывается onClose.
 * При закрытии по клику/свайпу вызывается onClose и затем history.back().
 */
export function useModalBack(isOpen: boolean, onClose: () => void) {
  const pushedRef = useRef(false);
  const closedByPopRef = useRef(false);

  useEffect(() => {
    if (!isOpen) {
      if (pushedRef.current && !closedByPopRef.current) {
        pushedRef.current = false;
        window.history.back();
      }
      closedByPopRef.current = false;
      return;
    }
    closedByPopRef.current = false;
    pushedRef.current = true;
    window.history.pushState({ [MODAL_STATE_KEY]: true }, '');
    const handlePopState = () => {
      closedByPopRef.current = true;
      pushedRef.current = false;
      onClose();
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [isOpen, onClose]);

  const handleOverlayClose = useCallback(() => {
    onClose();
  }, [onClose]);
  return { handleOverlayClose };
}

/** Свайп вниз: если пользователь потянул вниз достаточно — вызываем onClose */
export function useSwipeDown(onClose: () => void) {
  const startY = useRef(0);
  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    startY.current = e.touches[0].clientY;
  }, []);
  const handleTouchEnd = useCallback(
    (e: React.TouchEvent) => {
      const endY = e.changedTouches[0].clientY;
      if (endY - startY.current > 60) onClose();
    },
    [onClose]
  );
  return { onTouchStart: handleTouchStart, onTouchEnd: handleTouchEnd };
}
