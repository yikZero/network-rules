"""Strict, policy-free common subset for public rule publication."""
from pathlib import Path
import hashlib, ipaddress, json, os, re, urllib.request

ROOT = Path(__file__).resolve().parents[1]
CORE_VERSION = json.loads((ROOT / 'tools.json').read_text())['sing-box']['version']
KINDS = {'domain': 'DOMAIN', 'domain_suffix': 'DOMAIN-SUFFIX',
         'domain_keyword': 'DOMAIN-KEYWORD', 'ip_cidr': 'IP-CIDR'}
PRIVATE_LABEL = re.compile(r'(^|[.-])(internal|intranet|corp|lan|local|localhost|private|home)([.-]|$)', re.I)
SLUG = re.compile(r'[a-z][a-z0-9-]{0,63}\Z')
PRIVATE_NETWORKS = tuple(map(ipaddress.ip_network, [
    '0.0.0.0/8', '10.0.0.0/8', '100.64.0.0/10', '127.0.0.0/8',
    '169.254.0.0/16', '172.16.0.0/12', '192.168.0.0/16',
    '::/128', '::1/128', 'fc00::/7', 'fe80::/10']))

def digest(data):
    return hashlib.sha256(data).hexdigest()

def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()

def validate(document):
    if set(document) - {'version', 'rules', 'surge_options'} or document.get('version') != 3:
        raise ValueError('Unsupported source document')
    if not isinstance(document.get('rules'), list) or not document['rules']:
        raise ValueError('Empty rule source')
    seen = set()
    for rule in document['rules']:
        if len(rule) != 1 or not set(rule) <= KINDS.keys():
            raise ValueError('Unsupported or ambiguous rule condition')
        for kind, values in rule.items():
            if not isinstance(values, list) or not values:
                raise ValueError('Empty rule condition')
            for value in values:
                if not isinstance(value, str) or (kind, value) in seen:
                    raise ValueError('Invalid or duplicate rule')
                seen.add((kind, value))
                if kind == 'ip_cidr':
                    network = ipaddress.ip_network(value, strict=True)
                    if not network.is_global or any(network.version == private.version and network.overlaps(private) for private in PRIVATE_NETWORKS):
                        raise ValueError('Non-public network in public data')
                elif (not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', value)
                      or PRIVATE_LABEL.search(value)
                      or (kind != 'domain_keyword' and ('.' not in value or '..' in value))):
                    raise ValueError('Private or invalid hostname in public data')
                elif re.fullmatch(r'[0-9.]+', value):
                    raise ValueError('Literal address in domain rule')
    for key, options in document.get('surge_options', {}).items():
        kind, sep, value = key.partition(':')
        if not sep or (kind, value) not in seen or not isinstance(options, list):
            raise ValueError('Unbound platform option')
        allowed = {'no-resolve'} if kind == 'ip_cidr' else {'extended-matching'}
        if not options or not set(options) <= allowed or len(set(options)) != len(options):
            raise ValueError('Unsupported platform option')
    return document

def native(document, dns=False):
    validate(document)
    rules = [rule for rule in document['rules'] if not (dns and 'ip_cidr' in rule)]
    if not rules:
        raise ValueError('Empty generated DNS list')
    return {'version': 3, 'rules': rules}

def surge(document):
    validate(document)
    lines = ['# Generated matching data; contains no policy or device configuration.']
    for rule in document['rules']:
        for kind, values in rule.items():
            for value in values:
                label = 'IP-CIDR6' if kind == 'ip_cidr' and ':' in value else KINDS[kind]
                options = document.get('surge_options', {}).get(kind + ':' + value, [])
                lines.append(','.join([label, value] + options))
    return '\n'.join(lines) + '\n'

def parse_surging(text):
    """Reject unknown syntax instead of silently losing matching semantics."""
    inverse = {v: k for k, v in KINDS.items()}
    inverse['IP-CIDR6'] = 'ip_cidr'
    rules = []; options = {}; seen = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(('#', '//', ';')):
            continue
        fields = [x.strip() for x in line.split(',')]
        if len(fields) < 2 or fields[0] not in inverse:
            raise ValueError('Unsupported upstream rule syntax')
        kind = inverse[fields[0]]; value = fields[1].lower(); entry = (kind, value)
        flags = fields[2:]
        if entry in seen:
            if options.get(kind + ':' + value, []) != flags:
                raise ValueError('Conflicting duplicate options')
            continue
        seen.add(entry); rules.append({kind: [value]})
        if flags:
            options[kind + ':' + value] = flags
    result = {'version': 3, 'rules': rules}
    if options:
        result['surge_options'] = options
    return validate(result)

def fetch(url, limit=1024 * 1024, github_token=False):
    headers = {'User-Agent': 'network-rules-builder/1'}
    if github_token and os.environ.get('GITHUB_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
        if not response.url.startswith('https://'):
            raise ValueError('Insecure download redirect')
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Oversized upstream')
    return data

def documents(refresh=False):
    result = {p.stem: validate(json.loads(p.read_text())) for p in sorted((ROOT / 'sources').glob('*.json'))}
    provenance = {}
    commits = {}
    for item in json.loads((ROOT / 'upstreams.json').read_text())['sources']:
        name = item['id']
        if not SLUG.fullmatch(name) or name in result:
            raise ValueError('Invalid upstream ID')
        repository = item['repository']; ref = item['ref']; path = item['path']
        # The catalog is code-reviewed; this fetcher accepts only the selected public provider.
        if repository != 'blackmatrix7/ios_rule_script' or ref != 'master' or not path.startswith('rule/Surge/') or '..' in Path(path).parts:
            raise ValueError('Unapproved upstream location')
        if refresh:
            if repository not in commits:
                commits[repository] = json.loads(fetch('https://api.github.com/repos/' + repository + '/commits/' + ref, github_token=True))['sha']
            commit = commits[repository]
            if not re.fullmatch('[a-f0-9]{40}', commit):
                raise ValueError('Invalid upstream revision')
            raw = fetch('https://raw.githubusercontent.com/' + repository + '/' + commit + '/' + path)
            doc = parse_surging(raw.decode('utf-8-sig'))
            record = {'repository': repository, 'path': path, 'commit': commit, 'sha256': digest(raw)}
        else:
            snapshot = json.loads((ROOT / 'upstream' / (name + '.json')).read_text())
            doc = validate(snapshot['document']); record = snapshot['provenance']
        if sum(len(v) for rule in doc['rules'] for v in rule.values()) < item['min_rules']:
            raise ValueError('Upstream list unexpectedly short')
        result[name] = doc; provenance[name] = record
    return result, provenance
