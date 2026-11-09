#!/usr/bin/env python3
"""Publication contract tests, including privacy and format parity."""
import copy, ipaddress, json, subprocess, unittest
import rules

class PublicationTests(unittest.TestCase):
    def test_public_author_metadata_uses_noreply(self):
        values=subprocess.check_output(['git','log','--all','--format=%ae%n%ce'],cwd=rules.ROOT,text=True).splitlines()
        current=subprocess.check_output(['git','var','GIT_AUTHOR_IDENT'],cwd=rules.ROOT,text=True).split('<',1)[1].split('>',1)[0]
        self.assertTrue(all(value.endswith('@users.noreply.github.com') or value=='noreply@github.com' for value in values+[current]),'Use a GitHub noreply author before committing public changes')

    def test_owned_sources_are_publishable(self):
        docs, _ = rules.documents()
        self.assertEqual(set(docs), {'ai', 'proxy-overrides', 'direct', 'proxy', 'bulk',
                                    'google-meet', 'work', 'design', 'dropbox'})
        for name, doc in docs.items():
            exported = rules.parse_surging(rules.surge(doc))
            flatten = lambda d: {(k, v) for row in d['rules'] for k, values in row.items() for v in values}
            self.assertEqual(flatten(exported), flatten(doc), name)
            self.assertEqual(exported.get('surge_options', {}), doc.get('surge_options', {}), name)

    def test_public_data_cannot_contain_config_or_network_identity(self):
        examples = [
            {'domain': ['router.lan']}, {'domain_suffix': ['office.internal.example']},
            {'ip_cidr': ['192.168.1.0/24']}, {'ip_cidr': ['100.64.0.0/10']},
            {'ip_cidr': ['127.0.0.0/8']}, {'ip_cidr': ['fc00::/7']},
            {'ip_cidr': ['8.0.0.0/6']},
            {'domain': ['https://example.org/path?token=example']},
            {'domain': ['example.org'], 'outbound': 'DIRECT'},
            {'source_ip_cidr': ['192.168.1.1/32']},
        ]
        for row in examples:
            with self.subTest(row=row), self.assertRaises(ValueError):
                rules.validate({'version': 3, 'rules': [row]})
        with self.assertRaises(ValueError):
            rules.validate({'version': 3, 'rules': [{'domain': ['example.org']}], 'secret': 'example'})

    def test_unknown_upstream_syntax_fails_closed(self):
        for line in ['PROCESS-NAME,example', 'DOMAIN,example.org,Proxy',
                     'DOMAIN,example.org,unknown-option', '<html>error</html>', '']:
            with self.subTest(line=line), self.assertRaises(ValueError):
                rules.parse_surging(line)

    def test_dns_variant_does_not_inherit_ip_conditions(self):
        docs, _ = rules.documents()
        main = rules.native(docs['google-meet']); dns = rules.native(docs['google-meet'], dns=True)
        self.assertTrue(any('ip_cidr' in row for row in main['rules']))
        self.assertTrue(all('ip_cidr' not in row for row in dns['rules']))

    def test_platform_options_are_preserved(self):
        doc = rules.parse_surging('IP-CIDR,8.8.8.0/24,no-resolve\nDOMAIN,example.org,extended-matching\n')
        text = rules.surge(doc)
        self.assertIn('8.8.8.0/24,no-resolve', text)
        self.assertIn('example.org,extended-matching', text)
        with self.assertRaises(ValueError):
            rules.parse_surging('DOMAIN,example.org\nDOMAIN,example.org,extended-matching')

    def test_ai_source_stays_domain_only_and_exceptions_stay_separate(self):
        docs, _ = rules.documents(); ai = docs['ai']; overrides = docs['proxy-overrides']
        self.assertTrue(all(set(row) <= {'domain', 'domain_suffix'} for row in ai['rules']))
        self.assertTrue(any('cindy.cn' in row.get('domain_suffix', []) for row in overrides['rules']))
        self.assertFalse(any('cindy.cn' in row.get('domain_suffix', []) for row in ai['rules']))
        self.assertFalse(any('openai' in row.get('domain_keyword', []) for row in ai['rules']))

if __name__ == '__main__':
    unittest.main(verbosity=2)
