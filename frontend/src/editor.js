import { EditorView, ViewPlugin, Decoration, hoverTooltip } from '@codemirror/view';
import { EditorState, StateField, StateEffect } from '@codemirror/state';
import { basicSetup } from 'codemirror';
import { squiggleClass } from './squiggle.js';

const BACKEND_URL = 'http://localhost:8000';
const TERMINATOR_RE = /[.?!]/;

// ── Diagnostic state ─────────────────────────────────────────────────────────
//
// Stores [{from, to, category, message, replacements}] in a StateField.
// Positions are mapped through document changes so squiggles track edits.
// Decorations (squiggles) are derived from the field; class is determined by category.

const addDiagnostics = StateEffect.define();

const diagnosticField = StateField.define({
  create: () => [],
  update(diags, tr) {
    let updated = diags;
    if (tr.docChanged) {
      updated = updated
        .map(d => ({
          ...d,
          from: tr.changes.mapPos(d.from, 1),
          to: tr.changes.mapPos(d.to, -1),
        }))
        .filter(d => d.from < d.to);
    }
    for (const effect of tr.effects) {
      if (effect.is(addDiagnostics)) {
        updated = [...updated, ...effect.value];
      }
    }
    return updated;
  },
  provide(f) {
    return EditorView.decorations.from(f, diags => {
      const sorted = [...diags]
        .filter(d => d.from < d.to)
        .sort((a, b) => a.from - b.from || a.to - b.to);
      try {
        return Decoration.set(
          sorted.map(d =>
            Decoration.mark({ class: squiggleClass(d.category) }).range(d.from, d.to)
          )
        );
      } catch {
        return Decoration.none;
      }
    });
  },
});

// ── Hover popover ─────────────────────────────────────────────────────────────
//
// Shows the LanguageTool message and replacement buttons when hovering a squiggle.
// Clicking a replacement applies it to the buffer via view.dispatch.

const accuracyTooltip = hoverTooltip((view, pos) => {
  const diags = view.state.field(diagnosticField);
  const diag = diags.find(d => pos >= d.from && pos < d.to);
  if (!diag) return null;

  return {
    pos: diag.from,
    end: diag.to,
    above: true,
    create(view) {
      const dom = document.createElement('div');
      dom.className = 'cm-accuracy-tooltip';

      const msg = document.createElement('p');
      msg.className = 'cm-accuracy-message';
      msg.textContent = diag.message;
      dom.appendChild(msg);

      if (diag.replacements.length > 0) {
        const list = document.createElement('div');
        list.className = 'cm-accuracy-replacements';
        diag.replacements.slice(0, 3).forEach(r => {
          const btn = document.createElement('button');
          btn.className = 'cm-accuracy-replacement';
          btn.textContent = `→ ${r}`;
          btn.addEventListener('mousedown', e => {
            e.preventDefault(); // keep editor focus
            view.dispatch({ changes: { from: diag.from, to: diag.to, insert: r } });
          });
          list.appendChild(btn);
        });
        dom.appendChild(list);
      }

      return { dom };
    },
  };
});

// ── Accuracy check ───────────────────────────────────────────────────────────

async function checkAccuracy(sentence, sentenceStart, view) {
  try {
    const resp = await fetch(`${BACKEND_URL}/accuracy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sentence }),
    });
    if (!resp.ok) return;
    const diagnosticList = await resp.json();

    const newDiags = diagnosticList
      .filter(d => d.span.from < d.span.to)
      .map(d => ({
        from: sentenceStart + d.span.from,
        to: sentenceStart + d.span.to,
        category: d.category,
        message: d.message,
        replacements: d.replacements || [],
      }));

    if (newDiags.length > 0) {
      view.dispatch({ effects: addDiagnostics.of(newDiags) });
    }
  } catch (err) {
    console.error('Accuracy check failed:', err);
  }
}

// ── Sentence detection plugin ────────────────────────────────────────────────
//
// Fires checkAccuracy when a single terminator character (. ? !) is typed.
// Extracts the completed sentence and maps backend span offsets to doc positions.

const sentenceDetector = ViewPlugin.fromClass(class {
  update(update) {
    if (!update.docChanged) return;

    const docText = update.state.doc.toString();

    update.changes.iterChanges((fromA, toA, fromB, toB, inserted) => {
      const insertedStr = inserted.toString();
      if (insertedStr.length !== 1 || !TERMINATOR_RE.test(insertedStr)) return;

      const terminatorPos = fromB;

      let prevTermPos = -1;
      for (let i = terminatorPos - 1; i >= 0; i--) {
        if (TERMINATOR_RE.test(docText[i])) {
          prevTermPos = i;
          break;
        }
      }

      const rawStart = prevTermPos + 1;
      const rawSentence = docText.slice(rawStart, terminatorPos + 1);
      const leadingWS = rawSentence.length - rawSentence.trimStart().length;
      const sentence = rawSentence.trimStart();
      const sentenceStart = rawStart + leadingWS;

      if (sentence.length > 1) {
        checkAccuracy(sentence, sentenceStart, update.view);
      }
    });
  }
});

// ── Editor setup ─────────────────────────────────────────────────────────────

new EditorView({
  state: EditorState.create({
    doc: '',
    extensions: [
      basicSetup,
      diagnosticField,
      accuracyTooltip,
      sentenceDetector,
    ],
  }),
  parent: document.getElementById('editor'),
});
