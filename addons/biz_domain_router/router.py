"""Exact host mappings in a root-owned file; never trust a database header."""
import json
import os
import re
import stat

MAP_PATH = '/etc/carejiox-domains.json'
HOST = re.compile(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+\Z')
SLUG = re.compile(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z')
_cache = None
_stamp = None


def domain_map(path=MAP_PATH):
    global _cache, _stamp
    info = os.stat(path, follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError('Domain map must be a root-owned, non-writable regular file')
    stamp = (path, info.st_ino, info.st_mtime_ns, info.st_size)
    if stamp != _stamp:
        with open(path, encoding='utf-8') as source:
            data = json.load(source)
        if not isinstance(data, dict) or any(not isinstance(k,str) or not HOST.fullmatch(k) or not isinstance(v,str) or not SLUG.fullmatch(v) or v.endswith('-staging') for k,v in data.items()):
            raise ValueError('Invalid domain map')
        _cache, _stamp = data, stamp
    return _cache


def select_database(dbs, host, mappings, fallback):
    host = (host or '').lower().split(':',1)[0].rstrip('.')
    if host in mappings:
        target = mappings[host]
        return [db for db in dbs if db == target]
    return fallback(dbs, host)
