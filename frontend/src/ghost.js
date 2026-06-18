import { StateField } from '@codemirror/state';
import { EditorView, WidgetType, Decoration, keymap } from '@codemirror/view';
import { FORCED_CONTINUATIONS } from './ghost-data.js';

const TERMINATOR_RE = /[.?!]/;

export { FORCED_CONTINUATIONS };

// Build a character-level trie from (phrase, continuation) pairs.
// Each node: { children: {char: node}, continuation: string | null }
export function buildTrie(entries) {
  const root = { children: {}, continuation: null };
  for (const [phrase, cont] of entries) {
    let node = root;
    for (const ch of phrase.toLowerCase()) {
      if (!node.children[ch]) node.children[ch] = { children: {}, continuation: null };
      node = node.children[ch];
    }
    node.continuation = cont;
  }
  return root;
}

// Returns the forced continuation if the current sentence ends with exactly one
// trie phrase (matched at a word boundary), null if none or conflicting.
export function lookupGhost(trie, currentSentence) {
  if (!currentSentence) return null;
  const text = currentSentence.toLowerCase();
  let found = null;

  for (let start = 0; start < text.length; start++) {
    if (start > 0 && text[start - 1] !== ' ') continue;

    let node = trie;
    for (let i = start; i < text.length && node; i++) {
      node = node.children[text[i]];
    }
    if (node && node.continuation !== null) {
      if (found !== null && found !== node.continuation) return null;
      found = node.continuation;
    }
  }

  return found;
}

const TRIE = buildTrie(FORCED_CONTINUATIONS);

function getCurrentSentence(docText, cursorPos) {
  let prevTermPos = -1;
  for (let i = cursorPos - 1; i >= 0; i--) {
    if (TERMINATOR_RE.test(docText[i])) { prevTermPos = i; break; }
  }
  return docText.slice(prevTermPos + 1, cursorPos).trimStart();
}

class GhostWidget extends WidgetType {
  constructor(text) {
    super();
    this.text = text;
  }

  eq(other) { return this.text === other.text; }

  toDOM() {
    const span = document.createElement('span');
    span.className = 'cm-ghost-text';
    span.textContent = this.text;
    return span;
  }

  ignoreEvent() { return true; }
}

export const ghostField = StateField.define({
  create(state) {
    const pos = state.selection.main.head;
    const suggestion = lookupGhost(TRIE, getCurrentSentence(state.doc.toString(), pos));
    return { suggestion, pos };
  },
  update(prev, tr) {
    const pos = tr.state.selection.main.head;
    if (!tr.docChanged && pos === prev.pos) return prev;
    const suggestion = lookupGhost(TRIE, getCurrentSentence(tr.state.doc.toString(), pos));
    return { suggestion, pos };
  },
  provide(f) {
    return EditorView.decorations.from(f, ({ suggestion, pos }) => {
      if (!suggestion) return Decoration.none;
      return Decoration.set([
        Decoration.widget({ widget: new GhostWidget(suggestion), side: 1 }).range(pos),
      ]);
    });
  },
});

export function acceptGhostCommand(view) {
  const { suggestion, pos } = view.state.field(ghostField);
  if (!suggestion) return false;
  view.dispatch({
    changes: { from: pos, to: pos, insert: suggestion },
    selection: { anchor: pos + suggestion.length },
  });
  return true;
}

export const ghostKeymap = keymap.of([{ key: 'Tab', run: acceptGhostCommand }]);
