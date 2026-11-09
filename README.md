# Network Rules

Generic service matching data for Surge and sing-box. The same reviewed sources
generate policy-free Surge lists, sing-box JSON and binary SRS files.

This repository contains classification data, not browsing logs. It does not
contain proxy nodes, subscriptions, credentials, device profiles, device-specific
addresses or private service endpoints. Generic reserved ranges occur only in
validation code and tests. A list can still indicate service interests;
do not treat public classification data as private.

## Maintenance

- Edit `sources/*.json` for owned service lists and overrides.
- `upstreams.json` selects third-party lists; `upstream/` contains offline snapshots.
- `scripts/check.py` checks the public-data contract, semantic round trips, DNS
  projections, platform flags and rejection of unsupported input.
- Policies, DNS selection, ordering and device differences belong to consumers.
- AI domains stay domain-only. General proxy overrides are a separate set.

```sh
python3 scripts/check.py
python3 scripts/build.py --sing-box /path/to/sing-box-1.14.4
```

The compiler is pinned to 1.14.4. Actions verifies downloaded tool checksums and
scans Git history with Gitleaks. Only the publication job has repository write
permission; pull requests cannot publish.

## Publication

Actions runs on source changes, manually, and daily at 04:13 Asia/Singapore.
The scheduled publication resolves each selected upstream to a commit, validates
its data, compiles both formats, and publishes a data-only `rules` branch.
Unchanged matching data normally produces no publication commit. A check marker
is renewed at most once every 28 days to keep scheduled repository activity alive.

Manifest:
<https://raw.githubusercontent.com/yikZero/network-rules/rules/manifest.json>

Examples:

- `surge/ai.list`
- `surge/proxy-overrides.list`
- `sing-box/ai.srs`
- `sing-box/google-meet.srs` and `sing-box/google-meet-dns.srs`

Consumers download the manifest from the `rules` branch, then use its immutable
`revision` tag for every file and verify sizes and SHA-256 hashes before
applying them. Keep the previous working version when download or validation
fails. Each device has its own update cycle; publication is not a simultaneous
device configuration deployment.

The tag and publication branch are pushed atomically. Consumers need no GitHub
API call or access token to fetch a consistent snapshot.

Unknown upstream syntax fails publication. Changes to source classification,
compiler versions and policy ordering require review. This pipeline does not
connect to private networks or deploy device configuration.

## Sources

Selected third-party service data comes from
[blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script).
Each publication records the upstream repository, path, commit and content hash.
Other providers and large filtering lists remain independent until explicitly
added and validated; this repository does not mirror their entire catalogs.
