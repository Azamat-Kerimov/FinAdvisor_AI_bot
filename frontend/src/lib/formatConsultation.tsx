import React, { Fragment } from 'react';

/** Форматирование текста консультации: убираем звездочки и заменяем на жирный текст, удаляем ненужные секции */

/**
 * Получает чистый текст консультации для копирования/шаринга (удаляет markdown, ненужные секции)
 */
export function getCleanConsultationText(text: string): string {
  if (!text) return text;
  
  let formatted = removeUnwantedSections(text);
  
  // Удаляем markdown звездочки, заменяя на обычный текст
  // Двойные звездочки **текст** -> текст (жирный остается как обычный)
  formatted = formatted.replace(/\*\*([^*]+?)\*\*/g, '$1');
  // Одинарные звездочки *текст* -> текст
  formatted = formatted.replace(/\*([^*\n]+?)\*/g, '$1');
  
  return formatted.trim();
}

/**
 * Удаляет ненужные секции из текста консультации
 */
function removeUnwantedSections(text: string): string {
  let formatted = text;

  // Паттерны для поиска секций (с учетом разных вариантов форматирования)
  const sectionPatterns = [
    // "Доходы и расходы"
    /💰\s*\*?\*?Доходы и расходы\*?\*?[\s\S]*?(?=\n\n(?:[1-6]\.\s*\*\*|📊|💡|⚠️|📋|🎯|💼|💰|Проблемные|Конкретные|Работа|Вопрос|CHECK|FOCUS_MONTH)|$)/gi,
    /\*\*Доходы и расходы\*\*[\s\S]*?(?=\n\n(?:[1-6]\.\s*\*\*|📊|💡|⚠️|📋|🎯|💼|💰|Проблемные|Конкретные|Работа|Вопрос|CHECK|FOCUS_MONTH)|$)/gi,
    /💰\s*Доходы и расходы[\s\S]*?(?=\n\n(?:[1-6]\.\s*\*\*|📊|💡|⚠️|📋|🎯|💼|💰|Проблемные|Конкретные|Работа|Вопрос|CHECK|FOCUS_MONTH)|$)/gi,
    
    // "Финансовые цели"
    /🎯\s*\*?\*?Финансовые цели\*?\*?[\s\S]*?(?=\n\n(?:[1-6]\.\s*\*\*|📊|💡|⚠️|📋|🎯|💼|💰|Проблемные|Конкретные|Работа|Вопрос|CHECK|FOCUS_MONTH)|$)/gi,
    /\*\*Финансовые цели\*\*[\s\S]*?(?=\n\n(?:[1-6]\.\s*\*\*|📊|💡|⚠️|📋|🎯|💼|💰|Проблемные|Конкретные|Работа|Вопрос|CHECK|FOCUS_MONTH)|$)/gi,
    /🎯\s*Финансовые цели[\s\S]*?(?=\n\n(?:[1-6]\.\s*\*\*|📊|💡|⚠️|📋|🎯|💼|💰|Проблемные|Конкретные|Работа|Вопрос|CHECK|FOCUS_MONTH)|$)/gi,
    
    // "Активы и долги"
    /💼\s*\*?\*?Активы и долги\*?\*?[\s\S]*?(?=\n\n(?:[1-6]\.\s*\*\*|📊|💡|⚠️|📋|🎯|💼|💰|Проблемные|Конкретные|Работа|Вопрос|CHECK|FOCUS_MONTH)|$)/gi,
    /\*\*Активы и долги\*\*[\s\S]*?(?=\n\n(?:[1-6]\.\s*\*\*|📊|💡|⚠️|📋|🎯|💼|💰|Проблемные|Конкретные|Работа|Вопрос|CHECK|FOCUS_MONTH)|$)/gi,
    /💼\s*Активы и долги[\s\S]*?(?=\n\n(?:[1-6]\.\s*\*\*|📊|💡|⚠️|📋|🎯|💼|💰|Проблемные|Конкретные|Работа|Вопрос|CHECK|FOCUS_MONTH)|$)/gi,
  ];

  sectionPatterns.forEach((pattern) => {
    formatted = formatted.replace(pattern, '');
  });

  // Удаляем блоки "📋 Задача:" и "🎯 Фокус месяца:" (а также старые форматы CHECK: и FOCUS_MONTH:)
  // Эти блоки парсятся на бэкенде и не должны показываться пользователю
  const taskPatterns = [
    /^📋\s*Задача:\s*.*$/gim,
    /^CHECK:\s*.*$/gim,
    /^🎯\s*Фокус месяца:\s*.*$/gim,
    /^FOCUS_MONTH:\s*.*$/gim,
  ];
  
  taskPatterns.forEach((pattern) => {
    formatted = formatted.replace(pattern, '');
  });

  // Очищаем множественные пустые строки
  formatted = formatted.replace(/\n{3,}/g, '\n\n');
  formatted = formatted.trim();

  return formatted;
}

/**
 * Преобразует текст консультации в React-элементы с жирным текстом вместо звездочек
 */
export function renderConsultationText(text: string): React.ReactNode {
  if (!text) return text;

  // Сначала удаляем ненужные секции
  let formatted = removeUnwantedSections(text);
  
  // Разбиваем текст на части, обрабатывая звездочки
  const parts: React.ReactNode[] = [];
  const lines = formatted.split('\n');
  let globalKeyCounter = 0;
  
  lines.forEach((line, lineIndex) => {
    if (!line.trim()) {
      parts.push(<Fragment key={`line-${lineIndex}-empty`}>{'\n'}</Fragment>);
      return;
    }

    const lineParts: React.ReactNode[] = [];
    
    // Сначала обрабатываем двойные звездочки **текст**, затем одинарные *текст*
    const doubleStarMatches: Array<{ start: number; end: number; text: string }> = [];
    const doubleStarRegex = /\*\*([^*]+?)\*\*/g;
    let match;
    
    while ((match = doubleStarRegex.exec(line)) !== null) {
      doubleStarMatches.push({
        start: match.index,
        end: match.index + match[0].length,
        text: match[1],
      });
    }

    // Обрабатываем строку по частям
    let currentIndex = 0;
    
    // Добавляем двойные звездочки и текст между ними
    doubleStarMatches.forEach((doubleMatch) => {
      // Текст до двойных звездочек
      if (doubleMatch.start > currentIndex) {
        const beforeText = line.slice(currentIndex, doubleMatch.start);
        // Обрабатываем одинарные звездочки в этом фрагменте
        const singleParts = processSingleStars(beforeText, globalKeyCounter);
        lineParts.push(...singleParts);
        globalKeyCounter += singleParts.length;
      }
      // Жирный текст из двойных звездочек
      lineParts.push(<strong key={`bold-${globalKeyCounter++}`}>{doubleMatch.text}</strong>);
      currentIndex = doubleMatch.end;
    });

    // Остаток строки после всех двойных звездочек
    if (currentIndex < line.length) {
      const remaining = line.slice(currentIndex);
      const singleParts = processSingleStars(remaining, globalKeyCounter);
      lineParts.push(...singleParts);
      globalKeyCounter += singleParts.length;
    }

    // Если не было звездочек вообще
    if (lineParts.length === 0) {
      lineParts.push(line);
    }

    // Объединяем части строки в один фрагмент
    parts.push(
      <Fragment key={`line-${lineIndex}`}>
        {lineParts}
      </Fragment>
    );
    
    // Добавляем перенос строки между строками (кроме последней)
    if (lineIndex < lines.length - 1) {
      parts.push(<Fragment key={`linebreak-${lineIndex}`}>{'\n'}</Fragment>);
    }
  });

  return parts.length > 0 ? parts : formatted;
}

/**
 * Обрабатывает одинарные звездочки *текст* в тексте
 */
function processSingleStars(text: string, startKey: number): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const singleStarRegex = /\*([^*\n]+?)\*/g;
  let match;
  let lastIndex = 0;
  let keyCounter = startKey;

  while ((match = singleStarRegex.exec(text)) !== null) {
    // Текст до звездочек
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    // Жирный текст
    parts.push(<strong key={`single-${keyCounter++}`}>{match[1]}</strong>);
    lastIndex = match.index + match[0].length;
  }

  // Остаток
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : [text];
}
