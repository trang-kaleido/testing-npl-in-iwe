import { describe, it, expect } from 'vitest';
import { EditorState } from '@codemirror/state';
import { diagnosticField, addDiagnostics } from './editor.js';

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
