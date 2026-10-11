"""Launch desktop window or a bounded command-line scan."""
import argparse
import json
from pathlib import Path
import sys

from marketscout import __version__, catalog
from marketscout.settings import load_settings, settings_path, normalize_settings
from marketscout.net import JsonCache
from marketscout.market import Market
from marketscout.analysis import analyze

BASE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description='FFXIV Market Scout')
    parser.add_argument('--version', action='version', version='FFXIV Market Scout ' + __version__)
    parser.add_argument('--cli', action='store_true')
    parser.add_argument('--demo', action='store_true', help='Artificial prices/sales, no market HTTP')
    parser.add_argument('--refresh', action='store_true', help='Refresh pinned game catalog')
    parser.add_argument('--fresh', action='store_true')
    parser.add_argument('--settings', type=Path)
    parser.add_argument('--sale-world')
    parser.add_argument('--purchase-scope')
    parser.add_argument('--budget', type=float)
    parser.add_argument('--batch-size', type=int)
    parser.add_argument('--scan-limit', type=int)
    parser.add_argument('--detail-limit', type=int)
    parser.add_argument('--catalog-search')
    parser.add_argument('--source', choices=('all', 'craft', 'gather'))
    parser.add_argument('--job', choices=('all', *catalog.JOBS))
    parser.add_argument('--profession', action='append', default=[], metavar='JOB:LEVEL')
    parser.add_argument('--craft-hq', action='store_true')
    args = parser.parse_args()
    config_path = args.settings or settings_path()
    data_path = BASE / 'data' / 'catalog.json'
    if args.refresh:
        catalog.refresh(data_path, lambda s: print(s, file=sys.stderr))
        if not args.cli:
            return
    if not args.cli:
        import tkinter as tk
        from marketscout.app import Application
        root = tk.Tk()
        Application(root, demo=args.demo, base_dir=BASE, settings_path=config_path)
        root.mainloop()
        return
    settings, warnings = load_settings(config_path)
    for key in ('sale_world', 'purchase_scope', 'budget', 'batch_size', 'scan_limit', 'detail_limit', 'catalog_search'):
        if getattr(args, key) is not None:
            settings[key] = getattr(args, key)
    if args.profession:
        for p in settings['professions'].values():
            p['enabled'] = False
        for value in args.profession:
            try:
                job, level = value.rsplit(':', 1)
                profile = settings['professions'][job]
                profile.update(enabled=True, level=int(level), hq=args.craft_hq)
            except (ValueError, KeyError):
                parser.error('Профессия: например Carpenter:50 или Miner:90')
    elif args.craft_hq:
        for p in settings['professions'].values():
            p['hq'] = True
    if args.profession:
        settings['analysis_mode'] = 'all'
        settings['analysis_job'] = 'all'
    if args.source is not None:
        settings['analysis_mode'] = args.source
    if args.job is not None:
        settings['analysis_job'] = args.job
    settings = normalize_settings(settings)
    data = catalog.load(data_path)
    rows, summary = analyze(data, settings, Market(JsonCache(config_path.parent / 'cache')), demo=args.demo,
                            force=args.fresh, progress=lambda s: print(s, file=sys.stderr))
    summary['warnings'] = warnings + summary['warnings']
    for row in rows:
        for entry in row['inputs']:
            entry['stacks'] = [vars(s) for s in entry['stacks']]
    print(json.dumps(dict(summary=summary, results=rows), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Ошибка: {exc}', file=sys.stderr)
        sys.exit(1)
