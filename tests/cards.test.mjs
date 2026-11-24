import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { cardModules, validateResult } from '../scripts/cards.mjs';

test('reject renderer error SVGs even when the handler returns normally', () => {
  assert.throws(() => validateResult({ status: 'error', content: '<svg>error</svg>' }));
  assert.throws(() => validateResult({ content: '<svg>Something went wrong!</svg>' }));
  assert.throws(() => validateResult({ status: 'success', content: '' }));
  assert.equal(validateResult({ status: 'success', content: '<svg>healthy</svg>' }), '<svg>healthy</svg>');
});

test('config expands into unique atomic card modules', () => {
  const cfg = JSON.parse(readFileSync('profile.config.json'));
  const modules = cardModules(cfg);
  assert.equal(modules.length, 2 + cfg.groups.flatMap(group => group.repos).length);
  assert.equal(new Set(modules.map(module => module.id)).size, modules.length);
  assert.equal(modules.find(module => module.id === 'repo-AxcAgentEngine').options.repo, 'AxcAgentEngine');
});
