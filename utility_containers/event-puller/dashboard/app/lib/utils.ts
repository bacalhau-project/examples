import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Truncates a given text to a specified maximum length and appends an ellipsis if the text exceeds that length.
 *
 * @param text - The text to be truncated.
 * @param maxLength - The maximum length of the truncated text. Defaults to 10.
 * @returns The truncated text with an ellipsis appended if it exceeds the maximum length.
 */
export const truncateText = (
  text: string | undefined | null,
  maxLength: number = 10,
  withEllipsis: boolean = true,
) => {
  if (!text) return '';

  if (text.length > maxLength) {
    return text.slice(0, maxLength) + (withEllipsis ? '...' : '');
  }
  return text;
};
