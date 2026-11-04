"""Read or tidy live data as a test user, outside the recording (look up record ids,
archive practice records). Passwords come from accounts.local.json.

  import sys; sys.path.insert(0, 'tools/uat-video'); from rpc import as_user, kw
  as_user('uat_owner')
  kw('crm.lead', 'write', [[4067], {'active': False}])
"""
import http.cookiejar
import json
import os
import urllib.request

URL = 'https://carejiox.com'
DB = 'carejiox'
_cj = http.cookiejar.CookieJar()
_op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cj))


def call(path, params):
    req = urllib.request.Request(
        URL + path,
        json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': params}).encode(),
        {'Content-Type': 'application/json'})
    d = json.load(_op.open(req))
    if 'error' in d:
        return ('ERR', d['error']['data'].get('message', d['error']))
    return d.get('result')


def login(user, password):
    return call('/web/session/authenticate', {'db': DB, 'login': user, 'password': password})


def as_user(user):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'accounts.local.json')) as fh:
        return login(user, json.load(fh)[user])


def kw(model, method, args=None, kwargs=None):
    return call('/web/dataset/call_kw', {
        'model': model, 'method': method, 'args': args or [], 'kwargs': kwargs or {}})
