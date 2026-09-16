# -*- coding: utf-8 -*-
"""Fetching a recording from the supplier, safely.

A recording link is a URL that arrives from outside, which makes every fetch a
server-side request forgery risk. The rules here are not optional:

* https only, on an exact host from the connection's allow-list;
* the resolved IP must be public — no private, loopback, link-local or
  multicast destination, and the check is on the ADDRESS, never on how the URL
  looks (the vendor's own sample embeds ``hostname=192.168.2.51`` as a query
  VALUE, which is text, not a network target);
* every redirect is re-validated, and a redirect off the allow-list ends the
  fetch;
* no provider token and no user cookie is ever forwarded;
* bounded timeout, bounded size, and the media type is read from the response
  rather than assumed.

A failure here is recorded on the recording and nowhere else. Call records,
call backs and live calling do not depend on it.
"""

import base64
import hashlib
import ipaddress
import logging
import socket
from urllib.parse import urlsplit

import requests

from odoo import fields, _

_logger = logging.getLogger(__name__)

CONNECT_TIMEOUT = 5.0
READ_TIMEOUT = 30.0
MAX_RECORDING_BYTES = 64 * 1024 * 1024
MAX_REDIRECTS = 3

# Extension -> media type for the formats the supplier is known to produce.
# `.gsm` is here so it is named honestly, NOT so it can be served as MP3.
FORMAT_MIMETYPES = {
    'gsm': 'audio/x-gsm',
    'wav': 'audio/wav',
    'mp3': 'audio/mpeg',
    'ogg': 'audio/ogg',
    'm4a': 'audio/mp4',
}


class RecordingFetchError(Exception):
    pass


def _allowed_hosts(config):
    return {h.strip().lower() for h in
            (config.allowed_recording_hosts or '').split(',') if h.strip()}


def _check_url(url, allowed_hosts):
    """Validate scheme, host and every resolved address. Raises on refusal."""
    parts = urlsplit(url or '')
    if parts.scheme != 'https':
        raise RecordingFetchError('recording links must use https')
    host = (parts.hostname or '').lower()
    if not host:
        raise RecordingFetchError('recording link has no host')
    if allowed_hosts and host not in allowed_hosts:
        raise RecordingFetchError('recording host is not allowed')
    if parts.port and parts.port not in (443,):
        raise RecordingFetchError('recording link uses an unexpected port')
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise RecordingFetchError('recording host could not be resolved') from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if (address.is_private or address.is_loopback or address.is_reserved
                or address.is_link_local or address.is_multicast
                or address.is_unspecified):
            raise RecordingFetchError(
                'recording host resolves to a non-public address')
    return url


def _observe_format(url, response):
    """What the bytes actually are — from the response, then the filename."""
    declared = (response.headers.get('Content-Type') or '').split(';')[0].strip()
    if declared and declared != 'application/octet-stream':
        for suffix, mimetype in FORMAT_MIMETYPES.items():
            if mimetype == declared:
                return suffix, declared
        return (declared.split('/')[-1] or 'bin'), declared
    lowered = (url or '').lower()
    for suffix, mimetype in FORMAT_MIMETYPES.items():
        if '.%s' % suffix in lowered:
            return suffix, mimetype
    return 'bin', declared or 'application/octet-stream'


def fetch_recording(recording):
    """Fetch and store one recording. Returns a small result dict.

    Never raises to the caller: a recording problem is reported, recorded and
    contained.
    """
    config = recording.call_log_id.voip_config_id
    if not config.recording_access_enabled:
        return {'ok': False,
                'message': _('Recording access is switched off.')}

    url = recording._best_source_url()
    if not url:
        recording.sudo().write({'state': 'unavailable'})
        return {'ok': False, 'message': _('No recording link was supplied.')}

    allowed = _allowed_hosts(config)
    session = requests.Session()
    session.max_redirects = 0
    recording.sudo().write({'state': 'downloading', 'download_error': False})

    current = url
    try:
        for _hop in range(MAX_REDIRECTS + 1):
            _check_url(current, allowed)
            response = session.get(
                current,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                allow_redirects=False,
                stream=True,
                verify=True,
                # No Authorization, no cookies. The supplier has not said
                # their recording host wants our API token, and sending a
                # credential to a host that did not ask is how one leaks.
                headers={'Accept': '*/*'},
            )
            if response.status_code in (301, 302, 303, 307, 308):
                current = response.headers.get('Location') or ''
                if not current.startswith('https://'):
                    raise RecordingFetchError('redirect left https')
                continue
            break
        else:
            raise RecordingFetchError('too many redirects')

        if response.status_code == 404:
            recording.sudo().write({
                'state': 'unavailable',
                'download_error': _('The supplier no longer has this '
                                    'recording.')})
            return {'ok': False,
                    'message': _('The supplier no longer has this recording.')}
        if response.status_code >= 400:
            raise RecordingFetchError('supplier answered %s'
                                      % response.status_code)

        chunks, size = [], 0
        for chunk in response.iter_content(64 * 1024):
            size += len(chunk)
            if size > MAX_RECORDING_BYTES:
                raise RecordingFetchError('recording is too large')
            chunks.append(chunk)
        payload = b''.join(chunks)
        if not payload:
            raise RecordingFetchError('the supplier sent an empty file')

        suffix, mimetype = _observe_format(current, response)
        if mimetype.startswith('text/') or mimetype == 'text/html':
            # A playback wrapper, not audio. Say so rather than storing HTML
            # under an audio filename.
            recording.sudo().write({
                'state': 'unavailable',
                'mimetype': mimetype,
                'file_format': suffix,
                'download_error': _(
                    'That link returns a web page, not an audio file.')})
            return {'ok': False, 'message': _(
                'That link returns a web page, not an audio file.')}

        filename = '%s.%s' % (
            recording.call_log_id.call_id or recording.id, suffix)
        vals = {
            'recording_file': base64.b64encode(payload),
            'recording_filename': filename,
            'file_size_bytes': size,
            'file_format': suffix,
            'mimetype': mimetype,
            'checksum': hashlib.sha256(payload).hexdigest(),
            'is_downloaded': True,
            'downloaded_date': fields.Datetime.now(),
            'download_error': False,
            'state': 'available',
        }
        days = config.recording_retention_days or 0
        if days > 0:
            from datetime import timedelta
            vals['retention_deadline'] = fields.Datetime.now() + timedelta(days=days)
        recording.sudo().write(vals)
        config.sudo().write({
            'total_recordings_synced': (config.total_recordings_synced or 0) + 1,
        })
        if not config.ready_recording_at:
            config.sudo().write({'ready_recording_at': fields.Datetime.now()})
        return {'ok': True, 'mimetype': mimetype, 'bytes': size}

    except RecordingFetchError as exc:
        _logger.warning('Recording %s refused: %s', recording.id, exc)
        recording.sudo().write({'state': 'error',
                                'download_error': str(exc)[:500]})
        return {'ok': False, 'message': _(
            'The recording could not be fetched (%s).') % exc}
    except requests.exceptions.RequestException as exc:
        _logger.warning('Recording %s fetch failed: %s', recording.id,
                        type(exc).__name__)
        recording.sudo().write({
            'state': 'error',
            'download_error': type(exc).__name__})
        return {'ok': False,
                'message': _('The supplier could not be reached.')}


def stream_recording(recording, range_header=None):
    """Yield ``(status, headers, body_iterable)`` for an authorised request.

    Serves the stored copy when there is one. Otherwise proxies the supplier
    through the same validation as a fetch — so a caller never receives, and
    never sees, a token-bearing provider URL.
    """
    if recording.is_downloaded and recording.recording_file:
        payload = base64.b64decode(recording.sudo().recording_file)
        return _range_response(payload,
                               recording.mimetype or 'application/octet-stream',
                               recording.recording_filename or 'recording',
                               range_header)

    config = recording.call_log_id.voip_config_id
    url = recording._best_source_url()
    if not url:
        raise RecordingFetchError('no recording link')
    _check_url(url, _allowed_hosts(config))

    headers = {'Accept': '*/*'}
    if range_header:
        headers['Range'] = range_header
    response = requests.get(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                            stream=True, allow_redirects=False, verify=True,
                            headers=headers)
    if response.status_code in (301, 302, 303, 307, 308):
        raise RecordingFetchError('supplier redirected the stream')
    if response.status_code >= 400:
        raise RecordingFetchError('supplier answered %s' % response.status_code)
    _suffix, mimetype = _observe_format(url, response)
    out_headers = [('Content-Type', mimetype),
                   ('Cache-Control', 'no-store, private'),
                   ('Accept-Ranges', 'bytes')]
    if response.headers.get('Content-Length'):
        out_headers.append(('Content-Length',
                            response.headers['Content-Length']))
    if response.headers.get('Content-Range'):
        out_headers.append(('Content-Range', response.headers['Content-Range']))
    return (response.status_code, out_headers,
            response.iter_content(64 * 1024))


def _range_response(payload, mimetype, filename, range_header):
    """HTTP Range over stored bytes, so seeking in the player works."""
    total = len(payload)
    base_headers = [
        ('Content-Type', mimetype),
        ('Cache-Control', 'no-store, private'),
        ('Accept-Ranges', 'bytes'),
        ('Content-Disposition', 'inline; filename="%s"' % filename),
    ]
    if not range_header or not range_header.startswith('bytes='):
        return 200, base_headers + [('Content-Length', str(total))], [payload]
    try:
        spec = range_header[len('bytes='):].split(',')[0].strip()
        start_text, _, end_text = spec.partition('-')
        start = int(start_text) if start_text else 0
        end = int(end_text) if end_text else total - 1
    except (TypeError, ValueError):
        return 200, base_headers + [('Content-Length', str(total))], [payload]
    if start >= total or start < 0:
        return (416, base_headers + [('Content-Range', 'bytes */%s' % total)],
                [b''])
    end = min(end, total - 1)
    chunk = payload[start:end + 1]
    return (206, base_headers + [
        ('Content-Length', str(len(chunk))),
        ('Content-Range', 'bytes %s-%s/%s' % (start, end, total)),
    ], [chunk])
