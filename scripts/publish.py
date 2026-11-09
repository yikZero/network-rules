#!/usr/bin/env python3
"""Fast-forward a data-only branch; never copy the source workspace into it."""
from pathlib import Path
import argparse, base64, json, os, shutil, subprocess, tempfile, time
import rules

ENV = dict(os.environ)
if os.environ.get('GITHUB_TOKEN'):
    ENV.update(GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',
               GIT_CONFIG_VALUE_0='AUTHORIZATION: basic ' + base64.b64encode(
                   ('x-access-token:' + os.environ['GITHUB_TOKEN']).encode()).decode())

def git(*args, cwd=rules.ROOT):
    return subprocess.run(['git', *args], cwd=cwd, env=ENV, check=True, capture_output=True, text=True).stdout.strip()

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, default=rules.ROOT / 'dist'); args = ap.parse_args()
    out = args.out.resolve(); manifest = json.loads((out / 'manifest.json').read_text())
    expected = set(manifest['files']) | {'manifest.json'}
    actual = {str(p.relative_to(out)) for p in out.rglob('*') if p.is_file()}
    if actual != expected:
        raise ValueError('Unmanifested publication file')
    for name, item in manifest['files'].items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or path.parts[0] not in {'surge', 'sing-box'}:
            raise ValueError('Unexpected publication path')
        data = (out / name).read_bytes()
        if rules.digest(data) != item['sha256'] or len(data) != item['bytes']:
            raise ValueError('Publication content mismatch')
    remote = 'https://github.com/yikZero/network-rules.git'
    if git('remote', 'get-url', 'origin').rstrip('/').removesuffix('.git').lower() != remote.removesuffix('.git').lower():
        raise ValueError('Unexpected publishing repository')
    if git('ls-remote', 'origin', 'refs/heads/main').split()[0] != git('rev-parse', 'HEAD'):
        print('Superseded source revision; no publication')
        raise SystemExit(0)
    ref = git('ls-remote', '--heads', 'origin', 'refs/heads/rules')
    with tempfile.TemporaryDirectory(prefix='network-rules-publish-') as temp:
        target = Path(temp) / 'tree'
        if ref:
            git('clone', '--quiet', '--single-branch', '--branch', 'rules', remote, str(target))
        else:
            target.mkdir(); git('init', '-b', 'rules', cwd=target)
            git('remote', 'add', 'origin', remote, cwd=target)
        old = target / 'manifest.json'
        checked = target / 'checked.json'
        recent = checked.exists() and time.time() - json.loads(checked.read_text())['epoch'] < 28 * 86400
        if old.exists() and json.loads(old.read_text()).get('revision') == manifest['revision'] and recent:
            print('No matching-data changes'); raise SystemExit(0)
        for item in target.iterdir():
            if item.name != '.git':
                shutil.rmtree(item) if item.is_dir() else item.unlink()
        for name in sorted(expected):
            destination = target / name; destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(out / name, destination)
        (target / 'checked.json').write_text(json.dumps({'epoch': int(time.time())}) + '\n')
        git('config', 'user.name', 'github-actions[bot]', cwd=target)
        git('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com', cwd=target)
        git('add', '--all', cwd=target)
        git('commit', '-m', 'Publish matching data ' + manifest['version'], cwd=target)
        revision = manifest['revision']
        if revision != 'rules-' + manifest['version']:
            raise ValueError('Unexpected publication revision')
        exists = git('ls-remote', '--tags', 'origin', 'refs/tags/' + revision, cwd=target)
        if exists:
            git('push', 'origin', 'HEAD:refs/heads/rules', cwd=target)
        else:
            git('tag', revision, cwd=target)
            git('push', '--atomic', 'origin', 'HEAD:refs/heads/rules', 'refs/tags/' + revision, cwd=target)
        print('Published ' + manifest['version'])
