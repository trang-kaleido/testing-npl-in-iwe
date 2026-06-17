/**
 * Maps a LanguageTool category id to the CSS class used for squiggle coloring.
 * grammar → red, spelling (TYPOS) → blue, style → grey.
 */
export function squiggleClass(category) {
  const cat = (category || '').toUpperCase();
  if (cat === 'TYPOS' || cat === 'CONFUSED_WORDS') return 'cm-squiggle-spelling';
  if (cat === 'STYLE' || cat === 'REDUNDANCY' || cat === 'COLLOCATIONS') return 'cm-squiggle-style';
  return 'cm-squiggle-grammar';
}
