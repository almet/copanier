from datetime import datetime, timezone, timedelta

import jwt

from . import config


def utcnow():
    return datetime.now(timezone.utc)


def create_token(email):
    return jwt.encode(
        {"sub": str(email), "exp": utcnow() + timedelta(days=7)},
        config.SECRET,
        config.JWT_ALGORITHM,
    )


def read_token(token):
    try:
        return jwt.decode(token, config.SECRET, algorithms=[config.JWT_ALGORITHM])
    except (jwt.DecodeError, jwt.ExpiredSignatureError):
        return {}
