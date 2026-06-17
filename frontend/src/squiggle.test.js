import { describe, it, expect } from 'vitest';
import { squiggleClass } from './squiggle.js';

describe('squiggleClass', () => {
  it('maps GRAMMAR category to grammar class (red)', () => {
    expect(squiggleClass('GRAMMAR')).toBe('cm-squiggle-grammar');
  });

  it('maps TYPOS category to spelling class (blue)', () => {
    expect(squiggleClass('TYPOS')).toBe('cm-squiggle-spelling');
  });

  it('maps CONFUSED_WORDS to spelling class (blue)', () => {
    expect(squiggleClass('CONFUSED_WORDS')).toBe('cm-squiggle-spelling');
  });

  it('maps STYLE category to style class (grey)', () => {
    expect(squiggleClass('STYLE')).toBe('cm-squiggle-style');
  });

  it('maps REDUNDANCY to style class (grey)', () => {
    expect(squiggleClass('REDUNDANCY')).toBe('cm-squiggle-style');
  });

  it('defaults unknown categories to grammar class', () => {
    expect(squiggleClass('MISC')).toBe('cm-squiggle-grammar');
    expect(squiggleClass('PUNCTUATION')).toBe('cm-squiggle-grammar');
  });

  it('handles empty/null category gracefully', () => {
    expect(squiggleClass('')).toBe('cm-squiggle-grammar');
    expect(squiggleClass(null)).toBe('cm-squiggle-grammar');
    expect(squiggleClass(undefined)).toBe('cm-squiggle-grammar');
  });
});
