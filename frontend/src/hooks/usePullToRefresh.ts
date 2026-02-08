import { useRef, useCallback, useState } from 'react';

const PULL_THRESHOLD = 70;
const MAX_PULL = 90;

/**
 * Pull-to-refresh: при тяге вниз в верхней части страницы (scrollY === 0) вызывается onRefresh.
 * Возвращает { pullProps для обёртки контента, pullY для индикатора, isRefreshing }.
 */
export function usePullToRefresh(onRefresh: () => void | Promise<void>) {
  const startY = useRef(0);
  const [pullY, setPullY] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    if (typeof window !== 'undefined' && window.scrollY === 0) {
      startY.current = e.touches[0].clientY;
    }
  }, []);

  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    if (isRefreshing || (typeof window !== 'undefined' && window.scrollY > 0)) return;
    const y = e.touches[0].clientY;
    const delta = y - startY.current;
    if (delta > 0) {
      setPullY(Math.min(delta, MAX_PULL));
    }
  }, [isRefreshing]);

  const handleTouchEnd = useCallback(() => {
    if (pullY >= PULL_THRESHOLD && !isRefreshing) {
      setIsRefreshing(true);
      setPullY(0);
      Promise.resolve(onRefresh()).finally(() => {
        setIsRefreshing(false);
      });
    } else {
      setPullY(0);
    }
  }, [pullY, isRefreshing, onRefresh]);

  return {
    pullProps: {
      onTouchStart: handleTouchStart,
      onTouchMove: handleTouchMove,
      onTouchEnd: handleTouchEnd,
      style: { touchAction: pullY > 0 ? 'none' : 'auto' },
    },
    pullY,
    isRefreshing,
  };
}
