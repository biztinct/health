# -*- coding: utf-8 -*-
"""What may leave this server, and to whom.

Every prompt this system sends to a language model passes through
:func:`check`. It answers one question: *is it lawful and safe for THIS text
to reach THIS provider?*

The model is deliberately simple, because a policy nobody can hold in their
head is a policy nobody applies.

Two independent gates
---------------------

**1. Declared classification (primary).** The caller says what kind of material
it is building a prompt from. This is structural: it is decided where the
prompt is assembled, by the person who knows what went into it, and it is
checked by a test that every call site declares something.

    SCHEMA     field names, labels, help text, our own authored content.
               Describes the system, not the people in it.
    AGGREGATE  counts and totals with no identifiers attached.
    RECORDS    anything drawn from rows about a person.

RECORDS may only reach a LOCAL provider. Everything else may go anywhere.

**2. Pattern backstop (secondary).** A scanner for high-signal identifiers —
phone numbers, emails, national ID numbers, encrypted-PHI tokens. If one of
those appears in a prompt that claimed to be SCHEMA, the declaration was wrong
and we refuse rather than believe it.

What this does NOT do, stated plainly
-------------------------------------

The backstop cannot detect a personal name. "Why has Nguyễn Thị Hoa not paid"
is indistinguishable from ordinary prose by any rule we could write, and a
name-detector tuned tightly enough to catch it would refuse half the Vietnamese
language. So:

* Free-typed user questions are scrubbed and scanned, never *proven* clean.
* The structural gate — not the scanner — is what actually protects records.
* If a surface must accept free text ABOUT a specific person, that surface
  belongs on a local provider. There is no clever middle option.

Saying so here is the point. A guard that overstates its reach is worse than
none, because people then stop thinking.

Local is about the NETWORK, not the software
--------------------------------------------

A self-hosted model is only local if it is reachable without leaving
infrastructure you control. Ollama on this box is local; the same Mistral build
behind somebody else's public endpoint is not, and it is the endpoint that
decides. :func:`is_local_provider` reads the host, not the vendor name.
"""
import hashlib
import ipaddress
import re
from urllib.parse import urlparse

# ---------------------------------------------------------------- classes
SCHEMA = 'schema'
AGGREGATE = 'aggregate'
RECORDS = 'records'

CLASSIFICATIONS = (SCHEMA, AGGREGATE, RECORDS)

# Classes that may cross to a provider we do not run.
EXPORTABLE = (SCHEMA, AGGREGATE)


class EgressRefused(Exception):
    """Raised instead of sending. Callers degrade; they never bypass."""

    def __init__(self, reason, detail=''):
        self.reason = reason
        self.detail = detail
        super().__init__('%s%s' % (reason, ': %s' % detail if detail else ''))


# ------------------------------------------------------------ locality
# Vendors whose endpoint is by definition not ours. Listing them explicitly
# beats inferring, because a new vendor should fail CLOSED — an unknown
# provider type is treated as remote below.
REMOTE_VENDORS = {'openai', 'anthropic', 'gemini', 'google', 'azure_openai',
                  'cohere', 'mistral_cloud', 'deepseek', 'grok'}

# Vendors that CAN be local — but only if the endpoint says so.
SELF_HOSTABLE = {'llama', 'mistral', 'ollama', 'vllm', 'localai', 'llamacpp'}


def is_local_provider(provider_type, endpoint=None):
    """True only if the model runs somewhere we control.

    Unknown provider types are remote. That is the safe direction: a new
    integration that nobody taught this function about must not silently
    inherit permission to receive patient records.
    """
    ptype = (provider_type or '').strip().lower()
    if ptype in REMOTE_VENDORS:
        return False
    if ptype not in SELF_HOSTABLE:
        return False
    return _host_is_private(endpoint)


def _host_is_private(endpoint):
    if not endpoint:
        return False
    host = (urlparse(endpoint).hostname or '').strip().lower()
    if not host:
        return False
    if host in ('localhost', 'localhost.localdomain'):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # A bare hostname we cannot resolve to a private address is treated as
        # public. Resolving it here would make the decision depend on DNS at
        # call time, which is not a property you want a privacy gate to have.
        return host.endswith('.internal') or host.endswith('.local')
    return ip.is_loopback or ip.is_private


# ------------------------------------------------------------- backstop
# High signal, low false positive. Each one is an identifier, not a hint.
_PATTERNS = (
    ('phi_token', re.compile(r'enc\$1\$[A-Za-z0-9+/=]{16,}')),
    ('email', re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b')),
    # Vietnamese mobile, written locally (0…) or internationally (+84…).
    ('phone_vn', re.compile(r'(?:\+?84|0)(?:3|5|7|8|9)\d{8}\b')),
    # CCCD / national ID: exactly 12 digits standing alone.
    ('national_id', re.compile(r'(?<!\d)\d{12}(?!\d)')),
    # Any other long digit run — account numbers, card numbers, ids.
    ('long_number', re.compile(r'(?<!\d)\d{9,}(?!\d)')),
)


def scan(text):
    """Identifier-shaped things found in ``text``. Names are NOT detectable."""
    found = []
    for name, pattern in _PATTERNS:
        if pattern.search(text or ''):
            found.append(name)
    return found


def redact(text):
    """Replace identifier-shaped things with their kind.

    Used on free-typed questions before they are sent. Reduces exposure; does
    not prove absence — see the module docstring.
    """
    out = text or ''
    for name, pattern in _PATTERNS:
        out = pattern.sub('[%s]' % name, out)
    return out


# --------------------------------------------------------------- gate
def check(prompt, classification, provider_type, endpoint=None):
    """Raise :class:`EgressRefused` unless this prompt may reach this provider.

    Returns a dict describing the decision, for the caller to log.
    """
    if classification not in CLASSIFICATIONS:
        raise EgressRefused(
            'undeclared_classification',
            'got %r, expected one of %s' % (classification,
                                            ', '.join(CLASSIFICATIONS)))

    local = is_local_provider(provider_type, endpoint)

    if classification == RECORDS and not local:
        raise EgressRefused(
            'records_to_remote_provider',
            'provider %r at %r is not local' % (provider_type, endpoint or '-'))

    hits = scan(prompt)
    if hits and not local:
        # The declaration and the content disagree. Believe the content.
        raise EgressRefused('identifier_in_exportable_prompt',
                            'found %s' % ', '.join(hits))

    return {
        'classification': classification,
        'provider_type': provider_type or '',
        'local': local,
        'prompt_sha256': hashlib.sha256((prompt or '').encode()).hexdigest(),
        'prompt_chars': len(prompt or ''),
        'findings': ','.join(hits),
    }
