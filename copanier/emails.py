import smtplib
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.base import MIMEBase
from email import encoders

from . import config


def send(to, subject, body, html=None, copy=None, attachments=None):
    if not attachments:
        attachments = []

    msg = MIMEMultipart()
    msg.attach(MIMEText(body, "plain"))
    if html:
        msg.attach(MIMEText(html, "html"))
    msg["Subject"] = subject
    msg["From"] = config.FROM_EMAIL
    msg["To"] = to
    msg["Bcc"] = copy if copy else config.FROM_EMAIL
    
    for file_name, attachment in attachments:
        part = MIMEBase('application','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet; charset=utf-8')
        part.set_payload(attachment)
        part.add_header('Content-Disposition',
                        'attachment',
                        filename=file_name)
        encoders.encode_base64(part)
        msg.attach(part)
    if not config.SEND_EMAILS:
        return print("Sending email", str(body))
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
        display_prices=True,
        order=order,
        delivery=delivery,
        request=request
    )
