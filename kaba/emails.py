import smtplib
from email.message import EmailMessage

from . import config


ACCESS_GRANTED = """Hey ho!

Voici le sésame:

https://{hostname}/sésame/{token}

Les gentils copains d'Épinamap
"""


def send(to, subject, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = config.FROM_EMAIL
    msg["To"] = to
    if not config.SEND_EMAILS:
        return print("Sending email", str(msg))
    try:
        server = smtplib.SMTP_SSL(config.SMTP_HOST)
        server.login(config.SMTP_LOGIN, config.SMTP_PASSWORD)
        server.send_message(msg)
    except smtplib.SMTPException:
        raise RuntimeError
    finally:
        server.quit()
