import os
from pathlib import Path

getenv = os.environ.get

DATA_ROOT = Path(__file__).parent.parent / "db"
SECRET = "sikretfordevonly"
# JWT_ALGORITHM = "HS256"
SEND_EMAILS = False
SMTP_HOST = "smtp.gmail.com"
SMTP_PASSWORD = ""
FROM_EMAIL = "contact@epinamap.org"


def init():
    for key, value in globals().items():
        if key.isupper():
            env_key = "KABA_" + key
            typ = type(value)
            if env_key in os.environ:
                globals()[key] = typ(os.environ[env_key])


init()
