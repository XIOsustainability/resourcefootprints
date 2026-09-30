#!/usr/bin/env python3
"""Ping IndexNow so Bing, Yandex and Seznam re-crawl straight after a deploy.

    python ping_indexnow.py                 # ping the standard page set
    python ping_indexnow.py /explorer       # ping specific paths

Google does NOT participate in IndexNow; it still needs Search Console.

The key is not a secret: IndexNow verifies ownership by requiring the key to
be published at https://resourcefootprints.com/<key>.txt. The file in site/
named <32 hex chars>.txt IS the key, and is the single source of truth here.
Deleting it breaks verification.
"""
import glob
import json
import os
import re
import sys
import urllib.error
import urllib.request

HOST = 'resourcefootprints.com'
DEFAULT = ['/', '/explorer', '/coverage']


def load_key():
    for path in glob.glob(os.path.join('site', '*.txt')):
        stem = os.path.splitext(os.path.basename(path))[0]
        if re.fullmatch(r'[0-9a-f]{32}', stem):
            return stem
    raise SystemExit('No IndexNow key file found in site/ (expected <32 hex>.txt)')


KEY = load_key()


def ping(paths):
    urls = ['https://%s%s' % (HOST, p) for p in paths]
    body = {
        'host': HOST,
        'key': KEY,
        'keyLocation': 'https://%s/%s.txt' % (HOST, KEY),
        'urlList': urls,
    }
    req = urllib.request.Request(
        'https://api.indexnow.org/IndexNow',
        data=json.dumps(body).encode('utf-8'),
        headers={'Content-Type': 'application/json; charset=utf-8'},
        method='POST')
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print('IndexNow %s for %d URL(s)' % (r.status, len(urls)))
            for u in urls:
                print('   ', u)
    except urllib.error.HTTPError as e:
        # 202 Accepted is success; 4xx usually means the key file is unreachable
        print('IndexNow HTTP %s: %s' % (e.code, e.read().decode('utf-8', 'replace')[:300]))


if __name__ == '__main__':
    ping(sys.argv[1:] or DEFAULT)
