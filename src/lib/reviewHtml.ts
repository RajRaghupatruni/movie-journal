import DOMPurify from 'dompurify';
import type { ClipboardEvent, DragEvent } from 'react';

/** Preserve the legacy editor's formatting, without links, media, styles or attributes. */
export function sanitizeReviewHtml(value: unknown): string {
  return DOMPurify.sanitize(typeof value === 'string' ? value : '', {
    ALLOWED_TAGS: ['p', 'br', 'div', 'b', 'strong', 'i', 'em', 'u', 's', 'strike', 'ul', 'ol', 'li'],
    ALLOWED_ATTR: [],
    ALLOW_DATA_ATTR: false,
    ALLOW_ARIA_ATTR: false,
  });
}

/** Paste as text so browser insertion cannot execute untrusted clipboard HTML. */
export function pasteReviewText(event: ClipboardEvent<HTMLDivElement>): void {
  event.preventDefault();
  document.execCommand('insertText', false, event.clipboardData.getData('text/plain'));
}

export function preventReviewDrop(event: DragEvent<HTMLDivElement>): void {
  event.preventDefault();
}
