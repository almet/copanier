from emails import Message
import email.utils as utils

from . import config


def send(to, subject, body, html=None, copy=None, attachments=None, mail_from=None):
    if not attachments:
        attachments = []

    # compute a message id, this is good for spam score
    mid = utils.make_msgid(domain=config.FROM_EMAIL.partition('@')[2])
    message = Message(
        text=body, html=html, subject=subject, mail_from=config.FROM_EMAIL, message_id=mid
    )

    for filename, attachment, mime in attachments:
        message.attach(filename=filename, data=attachment, mime=f"{mime} charset=utf-8")

    if not config.SEND_EMAILS:
        body = body.replace("https", "http")
        return print("Sending email", str(body.encode('utf-8')), flush=True)

    # If the DOMAIN configuration parameter is configured, take it as HELO parameter
    # Else, take None, the sender's fqdn will be computed by the library
    # cf. https://docs.python.org/3/library/smtplib.html
    domain = config.DOMAIN
    if domain == "":
        domain = None

    # if no SMTP_LOGIN specified, don't create user and password fields, as the smtp server don't want them !
    if config.SMTP_LOGIN=="":
        smtp={
            "host": config.SMTP_HOST,
            "port": "25",
            "ssl": False,
            "local_hostname": domain
        }

    else:
        smtp={
            "host": config.SMTP_HOST,
            "user": config.SMTP_LOGIN,
            "password": config.SMTP_PASSWORD,
            "port": "25",
            "ssl": False,
            "local_hostname": domain
        }

    message.send(
        to=to,
        mail_from=mail_from,
        smtp=smtp
    )


def send_from_template(env, template, to, subject, mail_from=None, **params):
    params["config"] = config
    html = env.get_template(f"emails/{template}.html").render(**params)
    txt = env.get_template(f"emails/{template}.txt").render(**params)
    send(to, subject, body=txt, html=html, mail_from=mail_from)


def send_order(request, env, person, delivery, order, group_id, **kwargs):
    send_from_template(
        env,
        "order_summary",
        person.email,
        f"{config.SITE_NAME} : résumé de la commande {delivery.name}",
        display_prices=True,
        order=order,
        delivery=delivery,
        request=request,
        group_id=group_id,
        **kwargs,
    )
