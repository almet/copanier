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
STAFF = []
LOCALE = "fr_FR.UTF-8"
SITE_NAME = "Copanier"
SITE_DESCRIPTION = "Les paniers piano d'Épinamap"
EMAIL_SIGNATURE = "Les gentils copains d'Épinamap"


def init():
    for key, value in globals().items():
        if key.isupper():
            env_key = "COPANIER_" + key
            typ = type(value)
            if typ == list:
                typ = lambda x: x.split()
            if env_key in os.environ:
                globals()[key] = typ(os.environ[env_key])
    locale.setlocale(locale.LC_ALL, LOCALE)


init()
