import { describe, it, expect } from 'vitest';
import { EditorState } from '@codemirror/state';
import { buildTrie, lookupGhost, formatSuggestion, FORCED_CONTINUATIONS, ghostField, acceptGhostCommand } from './ghost.js';

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

describe('multi-branch continuations', () => {
  const branchTrie = buildTrie([['result', [' in', ' from']]]);

  it('returns the full branch array on match', () => {
    expect(lookupGhost(branchTrie, 'this result')).toEqual([' in', ' from']);
  });

  it('formats branches as "first/rest" for display', () => {
    expect(formatSuggestion([' in', ' from'])).toBe(' in/from');
    expect(formatSuggestion([' to', ' that'])).toBe(' to/that');
    expect(formatSuggestion(' to')).toBe(' to');
  });

  it('does not treat two matches with equal branch content as conflicting', () => {
    const trie = buildTrie([
      ['solution', [' to', ' for']],
      ['other solution', [' to', ' for']],
    ]);
    expect(lookupGhost(trie, 'other solution')).toEqual([' to', ' for']);
  });

  it('Tab accepts only the first (primary) branch', () => {
    const doc = 'this is the result';
    let state = EditorState.create({
      doc,
      extensions: [ghostField],
      selection: { anchor: doc.length },
    });
    expect(state.field(ghostField).suggestion).toEqual([' in', ' from']);

    const view = { state, dispatch: (tr) => { state = state.update(tr).state; } };
    acceptGhostCommand(view);
    expect(state.doc.toString()).toBe('this is the result in');
  });
});

describe('FORCED_CONTINUATIONS', () => {
  it('includes "according" → " to"', () => {
    const entry = FORCED_CONTINUATIONS.find(([p]) => p === 'according');
    expect(entry).toBeDefined();
    expect(entry[1]).toBe(' to');
  });

  it('includes "in front" → " of"', () => {
    const entry = FORCED_CONTINUATIONS.find(([p]) => p === 'in front');
    expect(entry).toBeDefined();
    expect(entry[1]).toBe(' of');
  });
});

describe('ghostField', () => {
  function stateAt(doc, pos) {
    return EditorState.create({ doc, extensions: [ghostField], selection: { anchor: pos } });
  }

  it('computes a suggestion when the cursor is after a known phrase', () => {
    const doc = 'The trophy sits in front';
    const state = stateAt(doc, doc.length);
    expect(state.field(ghostField).suggestion).toBe(' of');
  });

  it('shows no suggestion when the prefix is not a known phrase', () => {
    const doc = 'make a decision';
    const state = stateAt(doc, doc.length);
    expect(state.field(ghostField).suggestion).toBeNull();
  });

  it('shows no suggestion when the cursor is at position 0 (no prefix)', () => {
    const doc = 'in front';
    const state = stateAt(doc, 0);
    expect(state.field(ghostField).suggestion).toBeNull();
  });

  it('clears the suggestion when the user types past a known phrase', () => {
    const doc = 'in front';
    let state = stateAt(doc, doc.length);
    expect(state.field(ghostField).suggestion).toBe(' of');

    // Simulate real typing: change + cursor advances past the inserted char
    state = state.update({
      changes: { from: doc.length, to: doc.length, insert: 'f' },
      selection: { anchor: doc.length + 1 },
    }).state;
    expect(state.field(ghostField).suggestion).toBeNull();
  });

  it('updates to a new suggestion when the phrase changes', () => {
    const doc = 'in front';
    let state = stateAt(doc, doc.length);
    state = state.update({
      changes: { from: 0, to: doc.length, insert: 'according' },
    }).state;
    expect(state.field(ghostField).suggestion).toBe(' to');
  });

  it('uses text after the last terminator as the current sentence', () => {
    const doc = 'He went. She arrived according';
    const state = stateAt(doc, doc.length);
    expect(state.field(ghostField).suggestion).toBe(' to');
  });
});
