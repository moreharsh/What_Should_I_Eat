import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { recipeOrigin, prepLabel, difficultyLabel } from '../src/recipeUi.js';

test('recipe Back returns to the originating menu options screen', () => {
  assert.equal(recipeOrigin('menu_options', 'cuisines'), 'menu_options');
  assert.equal(recipeOrigin('recipe', 'menu_options'), 'menu_options');
});

test('recipe Back returns to the dashboard for history cards', () => {
  assert.equal(recipeOrigin('dashboard', 'menu_options'), 'dashboard');
  assert.equal(recipeOrigin('recipe', 'dashboard'), 'dashboard');
});

test('retrying a recipe preserves origin and defaults safely', () => {
  assert.equal(recipeOrigin('recipe', 'menu_options'), 'menu_options');
  assert.equal(recipeOrigin('cuisines', 'menu_options'), 'cuisines');
});

test('prep times retain overnight and fermentation details', () => {
  const full = '20 min active; soak overnight and ferment 10–12 hours';
  assert.equal(prepLabel(full), full);
  assert.equal(prepLabel(' '), 'Prep time not specified');
  assert.equal(difficultyLabel(' Medium '), 'Medium');
  assert.equal(difficultyLabel(undefined), 'Difficulty not specified');
});

test('recipe option and favorite cards use buttons and stable focus styles', () => {
  const source = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8');
  assert.match(source, /triedFavorites\.map\([\s\S]*?<button[\s\S]*?focus-visible:ring-2/);
  assert.match(source, /menuOptions\.map\([\s\S]*?<button[\s\S]*?focus-visible:ring-2/);
  assert.doesNotMatch(source, /<div\s+[^>]*onClick=/);
  assert.doesNotMatch(source, /⚡ 10ms/);
});

test('dietary chips wrap, expose selected state and meet touch size', () => {
  const source = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8');
  assert.match(source, /aria-label="Dietary restrictions" className="flex flex-wrap/);
  assert.match(source, /aria-pressed=\{selectedDiet\.includes\(diet\)\}/);
  assert.match(source, /min-h-11 px-4 py-2 rounded-full/);
});
