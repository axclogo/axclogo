// Adapter for the pinned 2.2.0 renderer. Its public pin API hides zero counts;
// use the same fetcher and renderer so zero stars/forks remain visible.
const coreEntry = () => import.meta.resolve('@stats-organization/github-readme-stats-core');

export async function renderRepositoryCard(repo, options) {
  const { renderRepoCard } = await import(new URL('./cards/repo.js', coreEntry()));
  for (const key of ['stargazerCount', 'forkCount']) {
    if (!Number.isSafeInteger(repo[key]) || repo[key] < 0) {
      throw new Error(`Invalid repository ${key}`);
    }
  }
  let svg = renderRepoCard({
    ...repo,
    // Reserve a one-digit slot for zero counts, which the upstream renderer
    // would otherwise omit. Restore the actual zero before returning SVG.
    stargazerCount: repo.stargazerCount || 1,
    forkCount: repo.forkCount || 1,
  }, {
    ...options,
    card_width_input: Number(options.card_width),
    hide_border: true,
    show_icons: false,
  });
  for (const [key, id] of [['stargazerCount', 'stargazers'], ['forkCount', 'forkcount']]) {
    if (repo[key] !== 0) continue;
    const label = new RegExp(`(<text\\b[^>]*data-testid="${id}"[^>]*>)1(</text>)`);
    if (!label.test(svg)) throw new Error(`Renderer did not produce ${id} slot`);
    svg = svg.replace(label, (_, open, close) => `${open}0${close}`);
  }
  return svg;
}

export async function fetchRepository(username, name) {
  const { fetchRepo } = await import(new URL('./fetchers/repo.js', coreEntry()));
  return fetchRepo(username, name);
}
