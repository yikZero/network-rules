#!/usr/bin/env python3
"""Build only reviewed matching data; no profiles or credentials are accepted."""
from pathlib import Path
import argparse, json, shutil, subprocess
import rules

def build(out, binary, refresh=False):
    version = subprocess.check_output([str(binary), 'version'], text=True).splitlines()[0]
    if version != 'sing-box version ' + rules.CORE_VERSION:
        raise ValueError('Use the pinned compiler version')
    docs, provenance = rules.documents(refresh)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    sets = {}
    for name, doc in sorted(docs.items()):
        surge_path = out / 'surge' / (name + '.list'); surge_path.parent.mkdir(exist_ok=True)
        surge_path.write_text(rules.surge(doc))
        exported = {}
        for flavor, document in [('route', rules.native(doc)), ('dns', rules.native(doc, dns=True))]:
            if flavor == 'dns' and document == rules.native(doc):
                exported[flavor] = exported['route']; continue
            stem = name + ('-dns' if flavor == 'dns' else '')
            path = out / 'sing-box' / (stem + '.json'); path.parent.mkdir(exist_ok=True)
            path.write_bytes(rules.encoded(document))
            srs = path.with_suffix('.srs')
            subprocess.run([str(binary), 'rule-set', 'compile', '--output', str(srs), str(path)], check=True, capture_output=True)
            exported[flavor] = {'source': str(path.relative_to(out)), 'binary': str(srs.relative_to(out))}
        sets[name] = {'surge': str(surge_path.relative_to(out)), **exported,
                      'entries': sum(len(v) for row in doc['rules'] for v in row.values())}
    files = {str(p.relative_to(out)): {'sha256': rules.digest(p.read_bytes()), 'bytes': p.stat().st_size}
             for p in sorted(out.rglob('*')) if p.is_file()}
    version = rules.digest(rules.encoded({'files': files, 'compiler': rules.CORE_VERSION}))[:24]
    manifest = {'schema': 1, 'version': version, 'revision': 'rules-' + version, 'compiler': rules.CORE_VERSION,
                'sets': sets, 'files': files, 'upstreams': provenance}
    (out / 'manifest.json').write_bytes(rules.encoded(manifest))
    return manifest

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, default=rules.ROOT / 'dist')
    ap.add_argument('--sing-box', required=True, type=Path)
    ap.add_argument('--refresh-upstreams', action='store_true')
    args = ap.parse_args(); out = args.out.resolve()
    if out != rules.ROOT / 'dist':
        raise ValueError('Build output must be the ignored dist/ directory')
    result = build(out, args.sing_box.resolve(), args.refresh_upstreams)
    print(json.dumps({'version': result['version'], 'sets': len(result['sets']), 'files': len(result['files'])}))
