export function formatDateDDMMYY(input: string | Date | null | undefined): string {
  if (!input) return '';
  const d = input instanceof Date ? input : new Date(input);
  if (Number.isNaN(d.getTime())) return '';
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = String(d.getFullYear()).slice(-2);
  return `${day}.${month}.${year}`;
}

/** Преобразует строку вида ДД.ММ.ГГ(ГГ) или с разделителями .-/ в ISO YYYY-MM-DD. */
export function parseDateDDMMYYToISO(input: string): string | null {
  if (!input) return null;
  const cleaned = input.trim();
  if (!cleaned) return null;
  const parts = cleaned.split(/[.\-\/]/).filter(Boolean);
  if (parts.length < 3) return null;
  let [dd, mm, yy] = parts;
  if (yy.length === 2) {
    // Простое правило: 70–99 -> 19xx, иначе 20xx
    const n = parseInt(yy, 10);
    yy = (n >= 70 ? '19' : '20') + yy;
  }
  const day = parseInt(dd, 10);
  const month = parseInt(mm, 10);
  const year = parseInt(yy, 10);
  if (!year || !month || !day) return null;
  if (month < 1 || month > 12 || day < 1 || day > 31) return null;
  const d = new Date(year, month - 1, day);
  if (Number.isNaN(d.getTime())) return null;
  const isoMonth = String(d.getMonth() + 1).padStart(2, '0');
  const isoDay = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${isoMonth}-${isoDay}`;
}

