import { describe, it, expect } from 'vitest';
import { getCurrentSentence } from './stall.js';

describe('getCurrentSentence', () => {
  it('returns the full text when sentence is unfinished', () => {
    expect(getCurrentSentence('The government should reduce', 28)).toBe('The government should reduce');
  });

  it('returns null when cursor is immediately after a terminator', () => {
    expect(getCurrentSentence('The government should reduce.', 29)).toBeNull();
  });

  it('returns current unfinished sentence after a completed one', () => {
    const text = 'He went. The government should reduce';
    expect(getCurrentSentence(text, text.length)).toBe('The government should reduce');
  });

  it('returns null for empty input', () => {
    expect(getCurrentSentence('', 0)).toBeNull();
  });

  it('trims leading whitespace from the sentence', () => {
    const text = 'He went.  The government should reduce';
    expect(getCurrentSentence(text, text.length)).toBe('The government should reduce');
  });

  it('returns null for cursor at position 0 with no text', () => {
    expect(getCurrentSentence('abc', 0)).toBeNull();
  });

  it('returns just the first word for a one-word start', () => {
    expect(getCurrentSentence('Furthermore', 11)).toBe('Furthermore');
  });

  it('does not fire at sentence boundary after question mark', () => {
    expect(getCurrentSentence('What is this?', 13)).toBeNull();
  });
});
