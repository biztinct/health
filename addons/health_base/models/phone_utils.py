import re

from odoo import _
from odoo.exceptions import ValidationError


def normalize_vn_phone(value):
    """Normalize a Vietnamese phone number.

    Rules (per business requirement):
      - Strip spaces, dashes, dots, parentheses and a leading ``+84``/``84``
        country code (``84xxxxxxxxx`` becomes ``0xxxxxxxxx``).
      - If the result is 9 digits (no leading 0), prepend ``0`` -> 10 digits.
      - If the result is 10 digits starting with ``0``, keep it.
      - Anything else is rejected with a clear ValidationError.

    Empty / falsy values are returned unchanged (the field stays empty).
    """
    if not value:
        return value

    # Keep only digits; this also drops spaces, dashes, dots, parens and the
    # leading '+' of an international prefix.
    digits = re.sub(r'\D', '', value)

    # Strip the Vietnam country code (with or without the '+').
    #   84 + 9 national digits  -> 0 + 9 digits
    #   84 + 0 + 9 national      -> drop the 84
    if digits.startswith('84') and len(digits) in (11, 12):
        rest = digits[2:]
        digits = rest if rest.startswith('0') else '0' + rest

    if digits.startswith('0'):
        # Entered WITH a leading zero -> must be exactly 10 digits, and the
        # digit right after the single trunk 0 must be non-zero. This rejects
        # padding zeros such as 0002558888 (3 zeros) or 0012345678, and any
        # 9-digit value that already starts with 0 (e.g. 002558888).
        if len(digits) == 10 and digits[1] != '0':
            return digits
    else:
        # Entered WITHOUT a leading zero -> must be exactly 9 digits; prepend
        # the trunk 0 to make a valid 10-digit number.
        if len(digits) == 9:
            return '0' + digits

    raise ValidationError(_(
        "Invalid phone number: '%s'. Enter a 9-digit number (a leading 0 is "
        "added automatically) or a 10-digit number starting with a single 0."
    ) % value)
