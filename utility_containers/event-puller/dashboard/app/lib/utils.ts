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

export function getContrastTextColor(hexColor: string): string {
  // Remove the hash if it's there
  const color = hexColor.charAt(0) === '#' ? hexColor.substring(1) : hexColor;
  const r = parseInt(color.substring(0, 2), 16);
  const g = parseInt(color.substring(2, 4), 16);
  const b = parseInt(color.substring(4, 6), 16);

  // Calculate brightness
  const brightness = (r * 299 + g * 587 + b * 114) / 1000;
  return brightness > 128 ? 'black' : 'white';
}
