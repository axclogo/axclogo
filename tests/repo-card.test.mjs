import test from 'node:test';
import assert from 'node:assert/strict';
import { renderRepositoryCard } from '../scripts/repo-card.mjs';

const repo = {
  name: 'AxcAgentEngine-WebUI', nameWithOwner: 'axclogo/AxcAgentEngine-WebUI',
  description: 'A TypeScript workbench for AxcAgentEngine.',
  primaryLanguage: { name: 'TypeScript', color: '#3178C6' },
  stargazerCount: 1, forkCount: 0,
};
const options = { card_width: '420', description_lines_count: 3, title_color: '3178C6' };

test('real renderer shows TypeScript and zero forks in both themes', async () => {
  for (const theme of ['default', 'react']) {
    const svg = await renderRepositoryCard(repo, { ...options, theme });
    assert.match(svg, /data-testid="lang-name"[^>]*>TypeScript<\/text>/);
    assert.match(svg, /data-testid="lang-color"[^>]*fill="#3178C6"/);
    assert.match(svg, /data-testid="stargazers"[^>]*>1<\/text>/);
    assert.match(svg, /data-testid="forkcount"[^>]*>0<\/text>/);
    assert.match(svg, /viewBox="0 0 420 150"/);
  }
  assert.equal(repo.forkCount, 0);
});

test('real renderer preserves zero stars, positive counts and unknown language', async () => {
  const zero = await renderRepositoryCard({ ...repo, primaryLanguage: null, stargazerCount: 0 }, options);
  assert.match(zero, /data-testid="stargazers"[^>]*>0<\/text>/);
  assert.match(zero, /data-testid="forkcount"[^>]*>0<\/text>/);
  assert.doesNotMatch(zero, /data-testid="primary-lang"/);
  const positive = await renderRepositoryCard({ ...repo, forkCount: 66 }, { ...options, card_width: '280' });
  assert.match(positive, /data-testid="forkcount"[^>]*>66<\/text>/);
  assert.match(positive, /viewBox="0 0 280 150"/);
});

test('missing or invalid counts fail instead of inventing zeros', async () => {
  for (const value of [undefined, null, -1, NaN, '0']) {
    await assert.rejects(renderRepositoryCard({ ...repo, forkCount: value }, options), /Invalid repository forkCount/);
  }
});
