import copy
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import profile as profile_assets


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cfg = profile_assets.config()
        self.svg = profile_assets.svg_frame(100, 100, 'Healthy', '<text x="10" y="20">OK</text>', self.cfg['themes']['light'])

    def write_svg(self, path, content=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content or self.svg)

    def test_failure_preserves_both_themes_and_last_success(self):
        files = profile_assets.expected_modules(self.cfg)['stats']
        output, artifacts = self.root / 'output', self.root / 'artifacts'
        for file in files:
            self.write_svg(output / file)
            self.write_svg(artifacts / 'cards' / 'stats' / file, self.svg.replace('OK', 'NEW'))
        (artifacts / 'cards' / 'stats' / files[-1]).write_text('<svg>Something went wrong</svg>')
        profile_assets.write_json(artifacts / 'cards/results.json', {'stats': {'ok': True, 'files': files}})
        profile_assets.write_json(output / 'status.json', {'modules': {'stats': {'last_success': 'old', 'files': files}}})
        failures = profile_assets.merge_assets(artifacts, output, self.cfg, 'now')
        self.assertIn('stats', failures)
        for file in files:
            self.assertEqual((output / file).read_text(), self.svg)
        state = json.loads((output / 'status.json').read_text())['modules']['stats']
        self.assertEqual(state['state'], 'retained')
        self.assertEqual(state['last_success'], 'old')

    def test_healthy_module_publishes_despite_missing_other_jobs(self):
        files = profile_assets.expected_modules(self.cfg)['stats']
        artifacts, output = self.root / 'artifacts', self.root / 'output'
        for file in files:
            self.write_svg(artifacts / 'cards' / 'stats' / file)
        profile_assets.write_json(artifacts / 'cards/results.json', {'stats': {'ok': True, 'files': files}})
        failures = profile_assets.merge_assets(artifacts, output, self.cfg, 'now')
        self.assertNotIn('stats', failures)
        self.assertIn('snake', failures)
        state = json.loads((output / 'status.json').read_text())['modules']
        self.assertEqual(state['stats']['state'], 'updated')
        self.assertEqual(state['snake']['state'], 'missing')

    def test_unexpected_paths_cannot_escape_output(self):
        artifacts, output = self.root / 'artifacts', self.root / 'output'
        profile_assets.write_json(artifacts / 'cards/results.json', {'stats': {'ok': True, 'files': ['../../escape.svg']}})
        self.assertIn('stats', profile_assets.merge_assets(artifacts, output, self.cfg, 'now'))
        self.assertFalse((self.root / 'escape.svg').exists())

    def test_svg_validation_rejects_error_and_external_resources(self):
        for bad in ['<svg>Something went wrong</svg>', '<html>404</html>',
                    self.svg.replace('</svg>', '<script>alert(1)</script></svg>'),
                    self.svg.replace('</svg>', '<image href="https://example.com/x.png"/></svg>')]:
            file = self.root / 'bad.svg'
            file.write_text(bad)
            with self.assertRaises(ValueError):
                profile_assets.validate_svg(file)

    def test_streak_handles_unfinished_today_and_gaps(self):
        def days(counts):
            return [{'contributionCount': count} for count in counts]
        self.assertEqual(profile_assets.streaks(days([1, 2, 0])), (2, 2, 3))
        self.assertEqual(profile_assets.streaks(days([1, 2, 0, 0])), (0, 2, 3))
        self.assertEqual(profile_assets.streaks(days([1, 0, 2, 1])), (2, 2, 4))
        self.assertEqual(profile_assets.streaks(days([0, 0])), (0, 0, 0))

    def test_activity_rendering_handles_all_zero_and_leap_year(self):
        start = dt.date(2024, 1, 1)
        days = [{'date': (start + dt.timedelta(days=i)).isoformat(), 'contributionCount': 0} for i in range(365)]
        for theme in self.cfg['themes'].values():
            for kind, svg in profile_assets.render_activity(days, theme).items():
                file = self.root / f'{kind}.svg'
                file.write_text(svg)
                profile_assets.validate_svg(file)
                self.assertNotIn('nan', svg.lower())

    def test_config_and_readme_references_match_managed_assets(self):
        profile_assets.validate_config(self.cfg)
        readme = profile_assets.readme_text(self.cfg)
        for files in profile_assets.expected_modules(self.cfg).values():
            for file in files:
                self.assertIn(file, readme)
        for host in ['vercel.app', 'herokuapp.com', 'demolab.com']:
            self.assertNotIn(host, readme)
        bad = copy.deepcopy(self.cfg)
        bad['groups'][0]['repos'][0]['name'] = '../../escape'
        with self.assertRaises(ValueError):
            profile_assets.validate_config(bad)


if __name__ == '__main__':
    unittest.main()
