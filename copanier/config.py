import locale
import os
from pathlib import Path

DATA_ROOT = Path(__file__).parent.parent / "db"
LOG_ROOT = Path("/tmp")
SECRET = "sikretfordevonly"
JWT_ALGORITHM = "HS256"
SEND_EMAILS = False
SMTP_HOST = "mail.gandi.net"
SMTP_PASSWORD = ""
SMTP_LOGIN = ""
FROM_EMAIL = "copanier@epinamap.org"
STAFF = ["yohanboniface@free.fr", "anne.mattler@wanadoo.fr"]
LOCALE = "fr_FR.UTF-8"


def init():
    for key, value in globals().items():
        if key.isupper():
            env_key = "COPANIER_" + key
            typ = type(value)
            if env_key in os.environ:
                globals()[key] = typ(os.environ[env_key])
    locale.setlocale(locale.LC_ALL, LOCALE)


init()
