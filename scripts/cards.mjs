import { mkdir, readFile, writeFile, rm } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export function cardModules(config) {
  return [
    { id: 'stats', type: 'api', options: config.stats },
    { id: 'languages', type: 'topLangs', options: config.languages },
    ...config.groups.flatMap(group => group.repos.map(repo => ({
      id: `repo-${repo.name}`, type: 'pin',
      options: { repo: repo.name, title_color: repo.color, show_icons: 'false' },
    }))),
  ];
}

export function validateResult(result) {
  if (!result || String(result.status).startsWith('error') ||
      typeof result.content !== 'string' || !result.content.includes('<svg') ||
      /Something went wrong|Maximum retries exceeded|Bad credentials/i.test(result.content)) {
    throw new Error(`Card generation failed (${result?.error?.type || result?.status || 'invalid SVG'})`);
  }
  return result.content;
}

async function main() {
  const config = JSON.parse(await readFile('profile.config.json', 'utf8'));
  const output = process.env.PROFILE_BUILD_DIR || 'build/cards';
  const modules = cardModules(config);
  if (process.argv[2] === '--module') {
    if (!process.env.GITHUB_TOKEN) throw new Error('GITHUB_TOKEN is required');
    // The renderer reads PAT_1 at import time. Never persist this token to disk.
    process.env.PAT_1 = process.env.GITHUB_TOKEN;
    const core = await import('@stats-organization/github-readme-stats-core');
    const module = modules.find(item => item.id === process.argv[3]);
    if (!module) throw new Error('Unknown card module');
    for (const [theme, options] of Object.entries(config.themes)) {
      const result = await core[module.type]({
        username: config.username, ...options, ...module.options,
        hide_border: 'true', disable_animations: 'true',
      });
      const svg = validateResult(result);
      const target = path.join(output, module.id, 'cards', `${module.id}-${theme}.svg`);
      await mkdir(path.dirname(target), { recursive: true });
      await writeFile(target, svg);
    }
    return;
  }

  await mkdir(output, { recursive: true });
  const results = {};
  // Each module runs in its own process: a hung API request cannot block others.
  for (const module of modules) {
    await rm(path.join(output, module.id), { recursive: true, force: true });
    let failure;
    for (let attempt = 1; attempt <= 2; attempt++) {
      const result = spawnSync(process.execPath, [fileURLToPath(import.meta.url), '--module', module.id], {
        env: process.env, timeout: 90_000, stdio: 'inherit',
      });
      if (result.status === 0) { failure = null; break; }
      failure = result.error?.code || `renderer exited ${result.status}`;
    }
    results[module.id] = failure
      ? { ok: false, error: failure }
      : { ok: true, files: Object.keys(config.themes).map(theme => `cards/${module.id}-${theme}.svg`) };
    console.log(`${module.id}: ${failure || 'generated'}`);
    await writeFile(path.join(output, 'results.json'), JSON.stringify(results, null, 2));
  }
  if (Object.values(results).some(result => !result.ok)) process.exitCode = 1;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
