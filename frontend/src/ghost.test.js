import { describe, it, expect } from 'vitest';
import { EditorState } from '@codemirror/state';
import { buildTrie, lookupGhost, FORCED_CONTINUATIONS, ghostField } from './ghost.js';

const testTrie = buildTrie([
  ['have an impact', ' on'],
  ['According', ' to'],
  ['in terms', ' of'],
]);

describe('lookupGhost', () => {
  it('returns the continuation when the sentence ends with a known phrase', () => {
    expect(lookupGhost(testTrie, 'have an impact')).toBe(' on');
    expect(lookupGhost(testTrie, 'According')).toBe(' to');
    expect(lookupGhost(testTrie, 'in terms')).toBe(' of');
  });

  it('matches a phrase at the end of a longer sentence', () => {
    expect(lookupGhost(testTrie, 'This policy will have an impact')).toBe(' on');
    expect(lookupGhost(testTrie, 'You should consider this in terms')).toBe(' of');
  });

  it('returns null for a prefix not in the trie (open-set)', () => {
    expect(lookupGhost(testTrie, 'make a')).toBeNull();
    expect(lookupGhost(testTrie, '')).toBeNull();
    expect(lookupGhost(testTrie, 'hello world')).toBeNull();
  });

  it('is case-insensitive', () => {
    expect(lookupGhost(testTrie, 'HAVE AN IMPACT')).toBe(' on');
    expect(lookupGhost(testTrie, 'according')).toBe(' to');
  });

  it('does not match a phrase embedded mid-word (word-boundary check)', () => {
    const trie = buildTrie([['act', ' on']]);
    expect(lookupGhost(trie, 'have contact')).toBeNull();
  });

  it('returns null when there is no input', () => {
    expect(lookupGhost(testTrie, null)).toBeNull();
    expect(lookupGhost(testTrie, undefined)).toBeNull();
  });
});

describe('FORCED_CONTINUATIONS', () => {
  it('includes "have an impact" → " on"', () => {
    const entry = FORCED_CONTINUATIONS.find(([p]) => p === 'have an impact');
    expect(entry).toBeDefined();
    expect(entry[1]).toBe(' on');
  });

  it('includes "According" → " to"', () => {
    const entry = FORCED_CONTINUATIONS.find(([p]) => p === 'According');
    expect(entry).toBeDefined();
    expect(entry[1]).toBe(' to');
  });
});

describe('ghostField', () => {
  function stateAt(doc, pos) {
    return EditorState.create({ doc, extensions: [ghostField], selection: { anchor: pos } });
  }

  it('computes a suggestion when the cursor is after a known phrase', () => {
    const doc = 'This will have an impact';
    const state = stateAt(doc, doc.length);
    expect(state.field(ghostField).suggestion).toBe(' on');
  });

  it('shows no suggestion when the prefix is not a known phrase', () => {
    const doc = 'make a difference';
    const state = stateAt(doc, doc.length);
    expect(state.field(ghostField).suggestion).toBeNull();
  });

  it('shows no suggestion when the cursor is at position 0 (no prefix)', () => {
    const doc = 'have an impact';
    const state = stateAt(doc, 0);
    expect(state.field(ghostField).suggestion).toBeNull();
  });

  it('clears the suggestion when the user types past a known phrase', () => {
    const doc = 'have an impact';
    let state = stateAt(doc, doc.length);
    expect(state.field(ghostField).suggestion).toBe(' on');

    // Simulate real typing: change + cursor advances past the inserted char
    state = state.update({
      changes: { from: doc.length, to: doc.length, insert: 'f' },
      selection: { anchor: doc.length + 1 },
    }).state;
    expect(state.field(ghostField).suggestion).toBeNull();
  });

  it('updates to a new suggestion when the phrase changes', () => {
    const doc = 'have an impact';
    let state = stateAt(doc, doc.length);
    state = state.update({
      changes: { from: 0, to: doc.length, insert: 'in terms' },
    }).state;
    expect(state.field(ghostField).suggestion).toBe(' of');
  });

  it('uses text after the last terminator as the current sentence', () => {
    const doc = 'He went. She noted this in terms';
    const state = stateAt(doc, doc.length);
    expect(state.field(ghostField).suggestion).toBe(' of');
  });
});
