from emails import Message

from . import config


def send(to, subject, body, html=None, copy=None, attachments=None):
    if not attachments:
        attachments = []

    message = Message(
        text=body, html=html, subject=subject, mail_from=config.FROM_EMAIL
    )

    for filename, attachment, mime in attachments:
        message.attach(filename=filename, data=attachment, mime=f"{mime} charset=utf-8")

    config.SEND_EMAILS = False
    if not config.SEND_EMAILS:
        body = body.replace("https", "http")
        return print("Sending email", str(body))

    message.send(
        to=to,
        smtp={
            "host": config.SMTP_HOST,
            "user": config.SMTP_LOGIN,
            "password": config.SMTP_PASSWORD,
            "port": "465",
            "ssl": True,
        },
    )


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
        request=request,
    )
