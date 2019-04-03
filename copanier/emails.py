import smtplib
from email.message import EmailMessage

from . import config


ACCESS_GRANTED = """Hey ho!

Voici le sésame:

https://{hostname}/sésame/{token}

Les gentils copains d'Épinamap
"""


def send(to, subject, body, html=None):
    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = config.FROM_EMAIL
    msg["To"] = to
    msg["Bcc"] = config.FROM_EMAIL
    if html:
        msg.add_alternative(html, subtype="html")
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


def send_order(request, env, person, delivery, order):
    html = env.get_template("emails/order_summary.html").render(
        order=order, delivery=delivery, request=request
    )
    txt = env.get_template("emails/order_summary.txt").render(
        order=order, delivery=delivery, request=request
    )
    send(
        person.email,
        f"Copanier: résumé de la commande {delivery.producer}",
        body=txt,
        html=html,
    )
