#!/usr/bin/env python3
"""Install checksum-pinned executables without executing downloaded scripts."""
from pathlib import Path
import argparse, hashlib, io, json, platform, tarfile, urllib.request

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True); args = ap.parse_args()
    catalog = json.loads((Path(__file__).resolve().parents[1] / 'tools.json').read_text())
    target = platform.system().lower() + '-' + platform.machine().lower()
    args.out.mkdir(parents=True, exist_ok=True)
    for name, entries in catalog.items():
        record = entries[target]
        with urllib.request.urlopen(record['url'], timeout=90) as response:
            data = response.read(64 * 1024 * 1024 + 1)
        if hashlib.sha256(data).hexdigest() != record['sha256']:
            raise ValueError('Tool checksum mismatch: ' + name)
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            member = next(m for m in archive.getmembers() if m.isfile() and Path(m.name).name == name)
            path = args.out / name; path.write_bytes(archive.extractfile(member).read()); path.chmod(0o755)
        print('Verified ' + name + ' ' + entries['version'])
