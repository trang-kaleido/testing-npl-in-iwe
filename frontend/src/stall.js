import { StateField, StateEffect } from '@codemirror/state';
import { showTooltip, ViewPlugin } from '@codemirror/view';

const BACKEND_URL = 'http://localhost:8000';
const STALL_DELAY = 2000;
const TERMINATOR_RE = /[.?!]/;

// Returns text from the last terminator to cursorPos, trimmed.
// Returns null when the cursor is right after a terminator (sentence boundary)
// or when there is no text — stall should not fire at those positions.
export function getCurrentSentence(docText, cursorPos) {
  if (cursorPos > 0 && TERMINATOR_RE.test(docText[cursorPos - 1])) return null;

  let prevTermPos = -1;
  for (let i = cursorPos - 1; i >= 0; i--) {
    if (TERMINATOR_RE.test(docText[i])) { prevTermPos = i; break; }
  }

  const raw = docText.slice(prevTermPos + 1, cursorPos).trim();
  return raw || null;
}

export const setStallCandidates = StateEffect.define();

export const stallField = StateField.define({
  create: () => ({ candidates: [], pos: 0 }),
  update(state, tr) {
    if (tr.docChanged) return { candidates: [], pos: 0 };
    for (const effect of tr.effects) {
      if (effect.is(setStallCandidates)) return effect.value;
    }
    return state;
  },
  provide: f => showTooltip.computeN([f], state => {
    const { candidates, pos } = state.field(f);
    if (!candidates.length) return [];
    return [{
      pos,
      above: true,
      strictSide: true,
      arrow: false,
      create() {
        const dom = document.createElement('div');
        dom.className = 'cm-stall-tooltip';
        candidates.forEach(c => {
          const chip = document.createElement('span');
          chip.className = 'cm-stall-candidate';
          chip.textContent = c;
          dom.appendChild(chip);
        });
        return { dom };
      },
    }];
  }),
});

export function makeStallPlugin(initContext) {
  return ViewPlugin.fromClass(class {
    constructor(view) {
      this._view = view;
      this._timer = null;
    }

    update(update) {
      if (!update.docChanged) return;
      clearTimeout(this._timer);
      this._timer = setTimeout(() => this._checkStall(), STALL_DELAY);
    }

    async _checkStall() {
      const view = this._view;
      const cursor = view.state.selection.main.head;
      const sentence = getCurrentSentence(view.state.doc.toString(), cursor);
      if (!sentence) return;

      try {
        const resp = await fetch(`${BACKEND_URL}/stall`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            current_sentence: sentence,
            init_context: initContext,
          }),
        });
        if (!resp.ok) return;
        const suggestions = await resp.json();
        const candidates = suggestions.map(s => s.text);
        view.dispatch({ effects: setStallCandidates.of({ candidates, pos: cursor }) });
      } catch {
        // backend unavailable during spike — silent fail
      }
    }

    destroy() {
      clearTimeout(this._timer);
    }
  });
}
