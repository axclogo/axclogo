"""Generate and validate profile assets; publish only complete, healthy modules."""
import argparse
import datetime as dt
import html
import json
import os
from pathlib import Path
import re
import shutil
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SVG_NS = 'http://www.w3.org/2000/svg'


def config():
    return json.loads((ROOT / 'profile.config.json').read_text())


def expected_modules(cfg):
    cards = ['stats', 'languages'] + [
        'repo-' + repo['name'] for group in cfg['groups'] for repo in group['repos']
    ]
    result = {name: [f'cards/{name}-{theme}.svg' for theme in cfg['themes']] for name in cards}
    result['activity'] = [f'activity/{kind}-{theme}.svg'
                          for kind in ('streak', 'graph') for theme in cfg['themes']]
    result['snake'] = ['github-contribution-grid-snake.svg', 'github-contribution-grid-snake-dark.svg']
    result['headings'] = [f'headings/{group["id"]}.svg' for group in cfg['groups']]
    return result


def validate_config(cfg):
    if not re.fullmatch(r'[A-Za-z0-9-]+', cfg['username']):
        raise ValueError('Invalid username')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', cfg['repository']):
        raise ValueError('Invalid repository')
    if set(cfg['themes']) != {'dark', 'light'}:
        raise ValueError('Both dark and light themes are required')
    ids, repos = [], []
    for group in cfg['groups']:
        if not re.fullmatch(r'[a-z0-9-]+', group['id']):
            raise ValueError('Invalid group id')
        if type(group.get('columns', 2)) is not int or group.get('columns', 2) not in (1, 2):
            raise ValueError('Group columns must be 1 or 2')
        ids.append(group['id'])
        for repo in group['repos']:
            if not re.fullmatch(r'[A-Za-z0-9_-]+', repo['name']):
                raise ValueError('Invalid repository name')
            if not re.fullmatch(r'[0-9A-Fa-f]{6}', repo['color']):
                raise ValueError('Invalid color')
            repos.append(repo['name'])
    if len(ids) != len(set(ids)) or len(repos) != len(set(repos)):
        raise ValueError('Duplicate group or repository')
    if cfg['activity'] != {'days': 365, 'graph_days': 31, 'timezone': 'UTC'}:
        raise ValueError('Activity uses a documented 365-day UTC window and 31-day graph')


def validate_svg(file):
    raw = Path(file).read_text()
    if not 100 <= len(raw) <= 2_000_000:
        raise ValueError(f'Unexpected SVG size: {file}')
    if re.search(r'Something went wrong|Maximum retries exceeded|Bad credentials|DEPLOYMENT_NOT_FOUND', raw, re.I):
        raise ValueError(f'Error card: {file}')
    if '<!DOCTYPE' in raw or '<!ENTITY' in raw:
        raise ValueError(f'External XML declaration: {file}')
    root = ET.fromstring(raw)
    if root.tag != f'{{{SVG_NS}}}svg' or not root.get('viewBox'):
        raise ValueError(f'Invalid SVG root/viewBox: {file}')
    for node in root.iter():
        if node.tag.split('}')[-1] in {'script', 'foreignObject', 'image'}:
            raise ValueError(f'Unsupported SVG element: {file}')
        for key, value in node.attrib.items():
            if key.lower().startswith('on'):
                raise ValueError(f'Event handler in SVG: {file}')
            if key.split('}')[-1] in {'href', 'src'} and not value.startswith('#'):
                raise ValueError(f'External SVG resource: {file}')
    if re.search(r'@import|url\(\s*[\"\']?(?:https?:|//|data:)', raw, re.I):
        raise ValueError(f'External CSS resource: {file}')


def write_json(file, data):
    file = Path(file)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def record_module(build, module, files, error=None):
    result_file = Path(build) / 'results.json'
    results = json.loads(result_file.read_text()) if result_file.exists() else {}
    results[module] = {'ok': False, 'error': error} if error else {'ok': True, 'files': files}
    write_json(result_file, results)


def github_graphql(query, variables):
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        raise ValueError('GITHUB_TOKEN is required')
    request = urllib.request.Request('https://api.github.com/graphql',
        data=json.dumps({'query': query, 'variables': variables}).encode(),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json',
                 'User-Agent': 'axclogo-profile-assets'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.load(response)
            if result.get('errors'):
                raise ValueError('GitHub GraphQL returned errors')
            return result['data']
        except urllib.error.HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise ValueError(f'GitHub API HTTP {error.code}') from error
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)


def contribution_days(cfg, today):
    start = today - dt.timedelta(days=cfg['activity']['days'] - 1)
    query = '''query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) { contributionsCollection(from: $from, to: $to) {
        contributionCalendar { weeks { contributionDays { date contributionCount } } }
      } }
    }'''
    data = github_graphql(query, {'login': cfg['username'],
        'from': start.isoformat() + 'T00:00:00Z', 'to': today.isoformat() + 'T23:59:59Z'})
    days = [day for week in data['user']['contributionsCollection']['contributionCalendar']['weeks']
            for day in week['contributionDays'] if start.isoformat() <= day['date'] <= today.isoformat()]
    days.sort(key=lambda day: day['date'])
    expected = [(start + dt.timedelta(days=i)).isoformat() for i in range(cfg['activity']['days'])]
    if [day['date'] for day in days] != expected:
        raise ValueError('Incomplete or duplicate contribution calendar; keeping previous images')
    if any(type(day['contributionCount']) is not int or day['contributionCount'] < 0 for day in days):
        raise ValueError('Invalid contribution count')
    return days


def streaks(days):
    counts = [day['contributionCount'] for day in days]
    longest = run = 0
    for count in counts:
        run = run + 1 if count else 0
        longest = max(longest, run)
    # An unfinished UTC day with no contributions does not break yesterday's streak.
    current = 0
    for count in reversed(counts[:-1] if counts and not counts[-1] else counts):
        if not count:
            break
        current += 1
    return current, longest, sum(counts)


def svg_frame(width, height, title, body, theme, description=''):
    return f'''<svg xmlns="{SVG_NS}" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">{html.escape(title)}</title><desc id="desc">{html.escape(description or title)}</desc>
<rect width="{width}" height="{height}" rx="10" fill="#{theme['bg_color']}"/>
<g font-family="Segoe UI, Ubuntu, sans-serif" fill="#{theme['text_color']}">{body}</g></svg>'''


def render_activity(days, theme):
    current, longest, total = streaks(days)
    since, until = days[0]['date'], days[-1]['date']
    body = '<text x="24" y="32" font-size="18" font-weight="600" fill="#36BCF7">Contribution streak</text>'
    for x, value, label in [(85, current, 'Current days'), (250, longest, 'Longest days'), (415, total, 'Contributions')]:
        body += f'<text x="{x}" y="83" text-anchor="middle" font-size="30" font-weight="600">{value:,}</text>'
        body += f'<text x="{x}" y="108" text-anchor="middle" font-size="12">{label}</text>'
    body += f'<text x="250" y="140" text-anchor="middle" font-size="11">Past 365 days · UTC · {since} – {until}</text>'
    streak = svg_frame(500, 160, 'Contribution streak — past 365 days', body, theme,
        f'Current streak {current} days, longest streak {longest} days, {total} contributions. Window: {since} to {until}, UTC.')
    recent = days[-31:]
    maximum = max(1, max(day['contributionCount'] for day in recent))
    coords = [(50 + i * 27, 188 - day['contributionCount'] / maximum * 125) for i, day in enumerate(recent)]
    body = '<text x="24" y="32" font-size="18" font-weight="600" fill="#36BCF7">Contribution activity · past 31 days</text>'
    for fraction in (0, .5, 1):
        y = 188 - fraction * 125
        body += f'<path d="M50 {y}H860" stroke="#{theme["text_color"]}" opacity=".15"/>'
        body += f'<text x="40" y="{y + 4}" text-anchor="end" font-size="11">{maximum * fraction:g}</text>'
    points = ' '.join(f'{x:.1f},{y:.1f}' for x, y in coords)
    body += f'<polyline points="{points}" fill="none" stroke="#36BCF7" stroke-width="2.5"/>'
    for i, ((x, y), day) in enumerate(zip(coords, recent)):
        body += f'<circle cx="{x}" cy="{y:.1f}" r="3" fill="#36BCF7"><title>{day["date"]}: {day["contributionCount"]}</title></circle>'
        if i % 5 == 0:
            body += f'<text x="{x}" y="208" text-anchor="middle" font-size="11">{day["date"][5:]}</text>'
    body += f'<text x="860" y="232" text-anchor="end" font-size="11">UTC · through {until}</text>'
    return {'streak': streak, 'graph': svg_frame(900, 250, 'Contribution activity', body, theme)}


def generate_activity(build):
    cfg = config()
    files = expected_modules(cfg)['activity']
    try:
        days = contribution_days(cfg, dt.datetime.now(dt.timezone.utc).date())
        for name, theme in cfg['themes'].items():
            for kind, svg in render_activity(days, theme).items():
                target = Path(build) / 'activity' / 'activity' / f'{kind}-{name}.svg'
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(svg)
                validate_svg(target)
        record_module(build, 'activity', files)
    except Exception as error:
        record_module(build, 'activity', [], type(error).__name__ + ': ' + str(error))
        raise


def generate_headings(build):
    cfg = config()
    for group in cfg['groups']:
        title = html.escape(group['title'])
        svg = f'''<svg xmlns="{SVG_NS}" width="435" height="50" viewBox="0 0 435 50" role="img" aria-label="{title}">
<title>{title}</title><style>
@keyframes typing {{ 0% {{ width: 0 }} 55%, 90% {{ width: 435px }} 100% {{ width: 0 }} }}
.reveal {{ animation: typing 7s steps(28, end) infinite; }}
@media (prefers-reduced-motion: reduce) {{ .reveal {{ animation: none; }} }}
</style><defs><clipPath id="clip"><rect class="reveal" width="435" height="50"/></clipPath></defs>
<text x="0" y="34" font-family="monospace" font-size="28" fill="#36BCF7" clip-path="url(#clip)">{title}</text></svg>'''
        target = Path(build) / 'headings' / 'headings' / f'{group["id"]}.svg'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(svg)
        validate_svg(target)
    record_module(build, 'headings', expected_modules(cfg)['headings'])


def record_snake(build):
    files = expected_modules(config())['snake']
    try:
        for file in files:
            validate_svg(Path(build) / 'snake' / file)
        record_module(build, 'snake', files)
    except Exception:
        record_module(build, 'snake', [], 'Snake generation or SVG validation failed')
        raise


def merge_assets(artifacts, output, cfg, now=None):
    """Only accept exact allowlisted file sets; keep both themes on any module failure."""
    now = now or dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    status_path = output / 'status.json'
    old = json.loads(status_path.read_text()) if status_path.exists() else {'modules': {}}
    found = {}
    for result_file in Path(artifacts).glob('*/results.json'):
        for module, result in json.loads(result_file.read_text()).items():
            if module in found:
                raise ValueError(f'Duplicate module result: {module}')
            found[module] = (result_file.parent, result)
    status = {'updated_at': now, 'source_sha': os.environ.get('GITHUB_SHA', ''),
              'run_url': os.environ.get('PROFILE_RUN_URL', ''), 'modules': {}}
    failures = []
    for module, files in expected_modules(cfg).items():
        previous = old.get('modules', {}).get(module, {})
        try:
            if module not in found:
                raise ValueError('Generation job produced no result')
            directory, result = found[module]
            if not result.get('ok'):
                raise ValueError(result.get('error', 'Generation failed'))
            if sorted(result.get('files', [])) != sorted(files):
                raise ValueError('Incomplete or unexpected file set')
            for file in files:
                candidate = directory / module / file
                if candidate.is_symlink() or not candidate.resolve().is_relative_to(directory.resolve()):
                    raise ValueError('Unsafe asset path')
                validate_svg(candidate)
            for file in files:
                target = output / file
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(directory / module / file, target)
            status['modules'][module] = {'state': 'updated', 'last_success': now, 'files': files}
        except (ValueError, OSError, ET.ParseError) as error:
            failures.append(module)
            available = True
            for file in files:
                try:
                    validate_svg(output / file)
                except (ValueError, OSError, ET.ParseError):
                    available = False
            status['modules'][module] = {
                'state': 'retained' if available else 'missing',
                'last_success': previous.get('last_success'), 'files': files,
                'error': str(error),
            }
    # Remove only previously managed obsolete files; never wipe the output branch.
    current_files = {file for files in expected_modules(cfg).values() for file in files}
    for previous in old.get('modules', {}).values():
        for file in previous.get('files', []):
            candidate = output / file
            if file not in current_files and candidate.resolve().is_relative_to(output.resolve()):
                candidate.unlink(missing_ok=True)
    write_json(status_path, status)
    lines = ['# Profile asset status', '', f'Last attempt: {now}', '',
             '| Module | Result | Last success |', '| --- | --- | --- |']
    for module, item in status['modules'].items():
        lines.append(f'| {module} | {item["state"]} | {item["last_success"] or "never"} |')
    lines += ['', 'Updated: new validated images. Retained: previous images preserved after failure.',
              'Missing: no valid images available. See status.json and the workflow run for details.',
              '', f'Workflow run: {status["run_url"]}']
    report = '\n'.join(lines) + '\n'
    (output / 'README.md').write_text(report)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
            summary.write(report)
    return failures


def readme_text(cfg):
    base = f'https://raw.githubusercontent.com/{cfg["repository"]}/{cfg["output_branch"]}/'
    def picture(light, dark, alt, width):
        return (f'<picture>\n  <source media="(prefers-color-scheme: dark)" srcset="{base}{dark}" />\n'
                f'  <img width="{width}" src="{base}{light}" alt="{html.escape(alt)}" />\n</picture>')
    def card(name, alt, width='43%'):
        return picture(f'cards/{name}-light.svg', f'cards/{name}-dark.svg', alt, width)
    sections = ['<!-- Generated by scripts/profile.py readme; edit profile.config.json instead. -->',
        '<p>\n' + card('stats', 'GitHub statistics') + '\n' + card('languages', 'Top languages', '34%') + '\n</p>',
        '<p>\n' + picture('activity/streak-light.svg', 'activity/streak-dark.svg', 'Contribution streak, past 365 days (UTC)', '43%') + '\n</p>',
        '<p align="center">\n' + picture('activity/graph-light.svg', 'activity/graph-dark.svg', 'Contribution activity, past 31 days (UTC)', '90%') + '\n</p>']
    for group in cfg['groups']:
        sections.append(f'[![{group["title"]}]({base}headings/{group["id"]}.svg)](https://github.com/{cfg["username"]})')
        columns = group.get('columns', 2)
        for i in range(0, len(group['repos']), columns):
            row = ['<p align="center">']
            for repo in group['repos'][i:i + columns]:
                row.append(f'<a href="https://github.com/{cfg["username"]}/{repo["name"]}">\n' + card('repo-' + repo['name'], repo['name']) + '\n</a>')
            row.append('</p>')
            sections.append('\n'.join(row))
    sections.append('<p align="center">\n' + picture('github-contribution-grid-snake.svg', 'github-contribution-grid-snake-dark.svg', 'Contribution snake', '100%') + '\n</p>')
    return '\n\n'.join(sections) + '\n'


def check_readme(cfg, output):
    if (ROOT / 'README.md').read_text() != readme_text(cfg):
        raise ValueError('README differs from config; run python3 scripts/profile.py readme')
    if output:
        for files in expected_modules(cfg).values():
            for file in files:
                validate_svg(Path(output) / file)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['activity', 'headings', 'snake', 'merge', 'readme', 'check'])
    parser.add_argument('--build', default='build/activity')
    parser.add_argument('--artifacts', default='build/artifacts')
    parser.add_argument('--output')
    args = parser.parse_args()
    cfg = config()
    validate_config(cfg)
    if args.command == 'activity':
        generate_activity(args.build)
    elif args.command == 'headings':
        generate_headings(args.build)
    elif args.command == 'snake':
        record_snake(args.build)
    elif args.command == 'merge':
        if not args.output:
            parser.error('--output is required for merge')
        failures = merge_assets(args.artifacts, args.output, cfg)
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
                stream.write(f'failed={str(bool(failures)).lower()}\n')
        print('Failed modules:', ', '.join(failures) or 'none')
        # Publication must still run for healthy modules. Workflow fails AFTER publishing.
    elif args.command == 'readme':
        (ROOT / 'README.md').write_text(readme_text(cfg))
    elif args.command == 'check':
        check_readme(cfg, args.output)


if __name__ == '__main__':
    main()
