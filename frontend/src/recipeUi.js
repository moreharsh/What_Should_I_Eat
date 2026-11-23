/** Navigation decisions shared by recipe cards, retries and Back actions. */
export function recipeOrigin(currentView, previousOrigin = 'cuisines') {
  if (currentView === 'dashboard' || currentView === 'menu_options') {
    return currentView;
  }
  if (currentView === 'recipe') return previousOrigin;
  return 'cuisines';
}

/** Keep long preparation guidance intact rather than claiming a shorter duration. */
export function prepLabel(value) {
  if (typeof value !== 'string' || !value.trim()) return 'Prep time not specified';
  return value.trim();
}

/** Difficulty display is metadata, not a fixed-width card column. */
export function difficultyLabel(value) {
  return typeof value === 'string' && value.trim() ? value.trim() : 'Difficulty not specified';
}
