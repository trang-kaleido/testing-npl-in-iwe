import { describe, it, expect } from 'vitest';
import { EditorState } from '@codemirror/state';
import {
  diagnosticField,
  addDiagnostics,
  findSentenceBounds,
  collectRecheckTargets,
} from './editor.js';

function stateWithDiag(doc, diag) {
  let state = EditorState.create({ doc, extensions: [diagnosticField] });
  state = state.update({
    effects: addDiagnostics.of({ range: { from: 0, to: doc.length }, diags: [diag] }),
  }).state;
  return state;
}

describe('diagnosticField', () => {
  it('drops a diagnostic when the edit overlaps its span', () => {
    const diag = { from: 3, to: 5, category: 'GRAMMAR', message: 'bad', replacements: [] };
    const state = stateWithDiag('He go to school.', diag);

    const next = state.update({ changes: { from: 3, to: 5, insert: 'went' } }).state;

    expect(next.field(diagnosticField)).toEqual([]);
  });

  it('keeps and repositions a diagnostic when the edit is outside its span', () => {
    const diag = { from: 3, to: 5, category: 'GRAMMAR', message: 'bad', replacements: [] };
    const state = stateWithDiag('He go to school.', diag);

    const next = state.update({ changes: { from: 0, to: 0, insert: 'Well, ' } }).state;

    expect(next.field(diagnosticField)).toEqual([
      { ...diag, from: 3 + 6, to: 5 + 6 },
    ]);
  });

  it('clears stale diagnostics in a range when a recheck reports no issues', () => {
    const diag = { from: 3, to: 5, category: 'GRAMMAR', message: 'bad', replacements: [] };
    const state = stateWithDiag('He went to school.', diag);

    const next = state.update({
      effects: addDiagnostics.of({ range: { from: 0, to: 19 }, diags: [] }),
    }).state;

    expect(next.field(diagnosticField)).toEqual([]);
  });

  it('replaces rather than stacks diagnostics within a rechecked range', () => {
    const diag = { from: 3, to: 5, category: 'GRAMMAR', message: 'old', replacements: [] };
    const state = stateWithDiag('He go to school.', diag);

    const newDiag = { from: 9, to: 11, category: 'STYLE', message: 'new', replacements: [] };
    const next = state.update({
      effects: addDiagnostics.of({ range: { from: 0, to: 17 }, diags: [newDiag] }),
    }).state;

    expect(next.field(diagnosticField)).toEqual([newDiag]);
  });
});

describe('findSentenceBounds', () => {
  it('returns sentence bounds when a forward terminator exists', () => {
    const docText = 'He went. She runs.';
    expect(findSentenceBounds(docText, 10)).toEqual({ sentence: 'She runs.', sentenceStart: 9 });
  });

  it('returns null when no forward terminator exists yet', () => {
    const docText = 'He went. She runs';
    expect(findSentenceBounds(docText, 10)).toBeNull();
  });

  it('trims leading whitespace from the sentence', () => {
    const docText = 'He went.   She runs.';
    expect(findSentenceBounds(docText, 12)).toEqual({ sentence: 'She runs.', sentenceStart: 11 });
  });
});

describe('collectRecheckTargets', () => {
  it('returns no targets when the edit does not overlap any prior diagnostic', () => {
    const priorDiags = [{ from: 3, to: 5, category: 'GRAMMAR', message: 'bad', replacements: [] }];
    const state = EditorState.create({ doc: 'He go to school. She runs.' });
    const tr = state.update({ changes: { from: 20, to: 20, insert: 'fast ' } });

    expect(collectRecheckTargets(priorDiags, tr.state.doc.toString(), tr.changes)).toEqual([]);
  });

  it('returns the correct sentence bounds for a single overlapping correction', () => {
    const priorDiags = [{ from: 3, to: 5, category: 'GRAMMAR', message: 'bad', replacements: [] }];
    const state = EditorState.create({ doc: 'He go to school.' });
    const tr = state.update({ changes: { from: 3, to: 5, insert: 'went' } });

    expect(collectRecheckTargets(priorDiags, tr.state.doc.toString(), tr.changes)).toEqual([
      { sentence: 'He went to school.', sentenceStart: 0 },
    ]);
  });

  it('returns no targets when the correction also removes the sentence terminator', () => {
    const priorDiags = [{ from: 3, to: 5, category: 'GRAMMAR', message: 'bad', replacements: [] }];
    const state = EditorState.create({ doc: 'He go to school.' });
    const tr = state.update({ changes: { from: 3, to: 16, insert: 'went to college' } });

    expect(collectRecheckTargets(priorDiags, tr.state.doc.toString(), tr.changes)).toEqual([]);
  });

  it('deduplicates two diagnostics overlapped by the same edit into one target', () => {
    const priorDiags = [
      { from: 3, to: 5, category: 'GRAMMAR', message: 'bad1', replacements: [] },
      { from: 9, to: 15, category: 'GRAMMAR', message: 'bad2', replacements: [] },
    ];
    const state = EditorState.create({ doc: 'He go to school today.' });
    const tr = state.update({ changes: { from: 0, to: 17, insert: 'He went to college ' } });

    expect(collectRecheckTargets(priorDiags, tr.state.doc.toString(), tr.changes).length).toBe(1);
  });
});
