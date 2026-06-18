import { EditorView, ViewPlugin, Decoration, hoverTooltip } from '@codemirror/view';
import { EditorState, StateField, StateEffect } from '@codemirror/state';
import { basicSetup } from 'codemirror';
import { squiggleClass } from './squiggle.js';
import { ghostField, ghostKeymap } from './ghost.js';

const BACKEND_URL = 'http://localhost:8000';
const TERMINATOR_RE = /[.?!]/;

// ── Diagnostic state ─────────────────────────────────────────────────────────
//
// Stores [{from, to, category, message, replacements}] in a StateField.
// Positions are mapped through document changes so squiggles track edits.
// Decorations (squiggles) are derived from the field; class is determined by category.

export const addDiagnostics = StateEffect.define();

export const diagnosticField = StateField.define({
  create: () => [],
  update(diags, tr) {
    let updated = diags;
    if (tr.docChanged) {
      const changedRanges = [];
      tr.changes.iterChanges((fromA, toA) => changedRanges.push([fromA, toA]));
      updated = updated
        .filter(d => !changedRanges.some(([cf, ct]) => d.from < ct && cf < d.to))
        .map(d => ({
          ...d,
          from: tr.changes.mapPos(d.from, 1),
          to: tr.changes.mapPos(d.to, -1),
        }))
        .filter(d => d.from < d.to);
    }
    for (const effect of tr.effects) {
      if (effect.is(addDiagnostics)) {
        const { range, diags: newDiags } = effect.value;
        updated = updated.filter(d => !(d.from >= range.from && d.to <= range.to));
        updated = [...updated, ...newDiags];
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

// ── Sentence bounds & recheck targeting ─────────────────────────────────────
//
// Pure helpers: given doc text and a position, find the enclosing completed
// sentence; given prior diagnostics and a change, find which sentences need
// rechecking because an edit touched a diagnosed span.

export function findSentenceBounds(docText, pos) {
  let prevTermPos = -1;
  for (let i = pos - 1; i >= 0; i--) {
    if (TERMINATOR_RE.test(docText[i])) { prevTermPos = i; break; }
  }
  let nextTermPos = -1;
  for (let i = pos; i < docText.length; i++) {
    if (TERMINATOR_RE.test(docText[i])) { nextTermPos = i; break; }
  }
  if (nextTermPos === -1) return null;

  const rawStart = prevTermPos + 1;
  const rawSentence = docText.slice(rawStart, nextTermPos + 1);
  const leadingWS = rawSentence.length - rawSentence.trimStart().length;
  return { sentence: rawSentence.trimStart(), sentenceStart: rawStart + leadingWS };
}

export function collectRecheckTargets(priorDiags, docText, changes) {
  const overlapped = [];
  changes.iterChanges((fromA, toA) => {
    for (const d of priorDiags) {
      if (d.from < toA && fromA < d.to) overlapped.push(d);
    }
  });

  const seen = new Set();
  const targets = [];
  for (const d of overlapped) {
    const mappedPos = changes.mapPos(d.from, 1);
    const bounds = findSentenceBounds(docText, mappedPos);
    if (!bounds || bounds.sentence.length <= 1) continue;
    if (seen.has(bounds.sentenceStart)) continue;
    seen.add(bounds.sentenceStart);
    targets.push(bounds);
  }
  return targets;
}

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

    view.dispatch({
      effects: addDiagnostics.of({
        range: { from: sentenceStart, to: sentenceStart + sentence.length },
        diags: newDiags,
      }),
    });
  } catch (err) {
    console.error('Accuracy check failed:', err);
  }
}

// ── Sentence detection plugin ────────────────────────────────────────────────
//
// Fires checkAccuracy when a single terminator character (. ? !) is typed,
// and also when an edit overlaps an existing diagnostic's span (a correction),
// so newly-revealed errors (LT's rules are literal-pattern matches, so fixing
// one error can expose another) surface without waiting for a terminator retype.

const sentenceDetector = ViewPlugin.fromClass(class {
  update(update) {
    if (!update.docChanged) return;

    const docText = update.state.doc.toString();
    const checkedStarts = new Set();

    update.changes.iterChanges((fromA, toA, fromB, toB, inserted) => {
      const insertedStr = inserted.toString();
      if (insertedStr.length !== 1 || !TERMINATOR_RE.test(insertedStr)) return;

      const bounds = findSentenceBounds(docText, fromB);
      if (!bounds || bounds.sentence.length <= 1) return;

      checkedStarts.add(bounds.sentenceStart);
      checkAccuracy(bounds.sentence, bounds.sentenceStart, update.view);
    });

    const priorDiags = update.startState.field(diagnosticField);
    for (const bounds of collectRecheckTargets(priorDiags, docText, update.changes)) {
      if (checkedStarts.has(bounds.sentenceStart)) continue;
      checkAccuracy(bounds.sentence, bounds.sentenceStart, update.view);
    }
  }
});

// ── Editor setup ─────────────────────────────────────────────────────────────

if (typeof document !== 'undefined' && document.getElementById('editor')) {
  new EditorView({
    state: EditorState.create({
      doc: '',
      extensions: [
        ghostKeymap,
        basicSetup,
        diagnosticField,
        accuracyTooltip,
        sentenceDetector,
        ghostField,
      ],
    }),
    parent: document.getElementById('editor'),
  });
}
