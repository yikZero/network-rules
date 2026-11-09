# Public rules repository

- This repository is public. Publish only generic matching data and build code.
- Never copy device profiles, credentials, VPN endpoints, private network addresses,
  personal domains, company-specific domains, logs or private-repository snapshots here.
- Edit `sources/*.json` for owned lists. `upstreams.json` is the only upstream catalog.
- Preserve list boundaries and Surge options. Policies, DNS choices and ordering belong
  to the private consumer configuration, not a public list.
- Run `python3 scripts/check.py` and build with the pinned sing-box compiler before publishing.
- Publish only the allowlisted `dist/` tree. Keep branch publication serialized and
  retain previous commits so consumers can pin a complete, verified version.
- Rule publication does not deploy device configuration or change proxy nodes.
