// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { sanitizeReviewHtml } from './reviewHtml';

describe('stored review HTML boundary', () => {
  it('keeps the formatting used by existing reviews', () => {
    const review = '<div><b>Great</b> <i>film</i><br><u>Yes</u><strike>No</strike><ul><li>Again</li></ul></div>';
    expect(sanitizeReviewHtml(review)).toBe(review);
  });

  it.each([
    '<img src=x onerror="alert(1)"><b onclick="alert(2)">Review</b>',
    '<svg><a href="javascript:alert(1)">bad</a></svg><script>alert(2)</script>',
    '<iframe srcdoc="<script>alert(1)</script>"></iframe><p style="background:url(x)" id="x" data-x="y">OK</p>',
    '<a href="javascript:alert(1)">Click</a><form><input name="attributes"></form>',
  ])('strips executable content and every attribute', (payload) => {
    const holder = document.createElement('div');
    holder.innerHTML = sanitizeReviewHtml(payload);
    expect(holder.querySelector('script,svg,img,iframe,a,form,input,style')).toBeNull();
    for (const element of holder.querySelectorAll('*')) expect(element.attributes.length).toBe(0);
  });

  it('handles malformed legacy values', () => {
    expect(sanitizeReviewHtml(null)).toBe('');
    expect(sanitizeReviewHtml({ review: 'wrong shape' })).toBe('');
  });
});
