import smtplib
from email.message import EmailMessage

from . import config


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


def send_from_template(env, template, to, subject, **params):
    params["config"] = config
    html = env.get_template(f"emails/{template}.html").render(**params)
    txt = env.get_template(f"emails/{template}.txt").render(**params)
    send(to, subject, body=txt, html=html)


def send_order(request, env, person, delivery, order):
    send_from_template(
        env,
        "order_summary",
        person.email,
        f"{config.SITE_NAME} : résumé de la commande {delivery.name}",
        order=order,
        delivery=delivery,
        request=request
    )
