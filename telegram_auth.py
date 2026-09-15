"""Telegram Mini App HMAC validation. Raw initData must never be logged/stored."""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


class AuthError(ValueError):
    pass


def verify_init_data(raw, bot_token, max_age=3600, now=None):
    try:
        if not raw or len(raw) > 16384 or not bot_token:
            raise ValueError()
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True)
        fields = dict(pairs)
        if len(fields) != len(pairs):
            raise ValueError()
        supplied = fields.pop("hash")
        check = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
        secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, supplied):
            raise ValueError()
        age = (time.time() if now is None else now) - int(fields["auth_date"])
        if not 0 <= age <= max_age:
            raise ValueError()
        user = json.loads(fields["user"])
        user_id = user.get("id")
        if type(user_id) is not int or user_id <= 0:
            raise ValueError()
        return user_id
    except (ValueError, TypeError, KeyError, AttributeError):
        raise AuthError("Откройте меню заново через новую кнопку /app в личном чате с ботом.") from None
