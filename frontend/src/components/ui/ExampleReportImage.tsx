import { useState } from 'react';

/** Картинка примера отчёта: при ошибке загрузки показываем заглушку с описанием */
export function ExampleReportImage({
  src,
  alt,
  className = '',
}: {
  src: string;
  alt: string;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <div
        className={`flex flex-col items-center justify-center bg-slate-100 text-slate-500 text-center p-6 ${className}`}
        style={{ minHeight: 120 }}
      >
        <span className="text-3xl mb-2" aria-hidden>📊</span>
        <span className="text-xs">{alt}</span>
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      className={className}
      onError={() => setFailed(true)}
    />
  );
}
