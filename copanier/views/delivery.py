from collections import defaultdict
from functools import partial
from roll import HttpError

from debts.solver import order_balance, check_balance, reduce_balance

from .core import app, session, env
from ..models import Delivery, Person, Order, ProductOrder, Groups, SavedConfiguration
from .. import utils, reports, emails, config


@app.listen("startup")
async def on_startup():
    Delivery.init_fs()


@app.route("/", methods=["GET"])
async def home(request, response):
    if not Delivery.is_defined() and not Groups.is_defined():
        response.redirect = app.url_for("onboarding")
        return
    if not request["user"].group_id:
        response.redirect = app.url_for("groups")
        return
    response.html(
        "delivery/list_deliveries.html",
        incoming=Delivery.incoming(),
        former=Delivery.former(),
    )


@app.route("/distribution", methods=["GET"])
async def new_delivery(request, response):
    response.html("delivery/edit_delivery.html", delivery={})

def create_delivery_from_form(form):
    data = {}
    data["from_date"] = f"{form.get('date')} {form.get('from_time')}"
    data["to_date"] = f"{form.get('date')} {form.get('to_time')}"
    for name in Delivery.__dataclass_fields__.keys():
        if name in form:
            data[name] = form.get(name)
    return Delivery(**data)


@app.route("/distribution", methods=["POST"])
async def create_delivery(request, response):
    delivery = create_delivery_from_form(request.form)
    delivery.persist()
    response.message("La distribution a bien été créée!")
    response.redirect = f"/distribution/{delivery.id}"


@app.route("/distribution/{id}/transmettre", methods=["GET"])
async def hand_over_delivery(request, response, id):
    delivery = Delivery.load(id)

    response.html(
        "delivery/handover_delivery.html",
        delivery=delivery,
    )


@app.route("/distribution/{id}/transmettre", methods=["POST"])
async def hand_over_delivery_post(request, response, id):
    old_delivery = Delivery.load(id)

    form = request.form
    new_delivery = create_delivery_from_form(form)
    new_delivery.producers = old_delivery.producers
    new_delivery.products = old_delivery.products

    # Update referent fields
    for producer_id, producer in new_delivery.producers.items():
        producer.referent = form.get(f'producer_{producer_id}_referent_email')
        producer.referent_name = form.get(f'producer_{producer_id}_referent_name')
        producer.referent_tel = form.get(f'producer_{producer_id}_referent_tel')
        new_delivery.producers[producer_id] = producer
    new_delivery.persist()

    # Mark the old delivery as over.
    old_delivery.over = True
    old_delivery.persist()

    emails.send_from_template(
        env,
        "handover_delivery",
        new_delivery.contact,
        f"{config.SITE_NAME} - Passage de flambeau",
        old_delivery.contact,
        delivery=new_delivery,
        email_body = form.get('email_body'),
        hostname=request.host,
        url_for=app.url_for,
        old_delivery=old_delivery
    )
     
    response.message("La distribution à bien été créée et le mail envoyé, merci !")
    response.redirect = f"/distribution/{new_delivery.id}"


@app.route("/distribution/{id}/{producer}/bon-de-commande.pdf", methods=["GET"])
async def pdf_for_producer(request, response, id, producer):
    delivery = Delivery.load(id)
    response.pdf(
        "list_products.html",
        {"list_only": True, "delivery": delivery, "producers": [producer]},
        filename=utils.prefix(f"bon-de-commande-{producer}.pdf", delivery),
    )


@app.route("/distribution/{id}/gérer", methods=["GET"])
async def show_delivery_toolbox(request, response, id):
    delivery = Delivery.load(id)
    response.html(
        "delivery/show_toolbox.html",
        {
            "delivery": delivery,
            "referents": [p.referent for p in delivery.producers.values()],
        },
    )


@app.route("/distribution/{id}/envoi-email-referentes", methods=["GET", "POST"])
async def send_referent_emails(request, response, id):
    delivery = Delivery.load(id)
    if request.method == "POST":
        email_body = request.form.get("email_body")
        email_subject = request.form.get("email_subject")
        sent_mails = 0
        for referent in delivery.get_referents():
            producers = delivery.get_producers_for_referent(referent)
            attachments = []
            for producer in producers:
                if delivery.producers[producer].has_active_products(delivery):
                    pdf_file = response.render_pdf(
                        "list_products.html",
                        {
                            "list_only": True,
                            "delivery": delivery,
                            "producers": [producer],
                        },
                    )

                    attachments.append(
                        (
                            utils.prefix(f"{producer}.pdf", delivery),
                            pdf_file,
                            "application/pdf",
                        )
                    )

            if attachments:
                sent_mails = sent_mails + 1
                emails.send(
                    referent,
                    email_subject,
                    email_body,
                    copy=delivery.contact,
                    attachments=attachments,
                )
        response.message(f"Un mail à été envoyé aux {sent_mails} référent⋅e⋅s")
        response.redirect = f"/distribution/{id}/gérer"

    response.html("delivery/prepare_referent_email.html", {"delivery": delivery})


@app.route("/distribution/{id}/exporter", methods=["GET"])
async def export_products(request, response, id):
    delivery = Delivery.load(id)
    response.xlsx(reports.products(delivery))


@app.route("/distribution/{id}/edit", methods=["GET"])
async def edit_delivery(request, response, id):
    delivery = Delivery.load(id)
    response.html("delivery/edit_delivery.html", {"delivery": delivery})


@app.route("/distribution/{id}/edit", methods=["POST"])
async def post_delivery(request, response, id):
    delivery = Delivery.load(id)
    form = request.form
    delivery.from_date = f"{form.get('date')} {form.get('from_time')}"
    delivery.to_date = f"{form.get('date')} {form.get('to_time')}"
    for name in Delivery.__dataclass_fields__.keys():
        if name in form:
            setattr(delivery, name, form.get(name))
    delivery.persist()
    response.message("La distribution a bien été mise à jour!")
    response.redirect = f"/distribution/{delivery.id}"


@app.route("/distribution/{id}", methods=["GET"])
async def show_delivery(request, response, id):
    delivery = Delivery.load(id)
    response.html("delivery/show_delivery.html", {"delivery": delivery})


@app.route("/distribution/{id}/commander", methods=["POST", "GET"])
async def place_order(request, response, id):
    delivery = Delivery.load(id)
    # email = request.query.get("email", None)
    user = session.user.get(None)
    orderer = request.query.get("orderer", None)
    if orderer:
        orderer = Person(email=orderer, group_id=orderer)

    delivery_url = f"/distribution/{delivery.id}"
    if not orderer and user:
        orderer = user

    if not orderer:
        response.message("Impossible de comprendre pour qui passer commande…", "error")
        response.redirect = delivery_url
        return

    if request.method == "POST":
        # When the delivery is closed, only staff can access.
        if delivery.status == delivery.CLOSED and not (user and user.is_staff):
            response.message("La distribution est fermée", "error")
            response.redirect = delivery_url
            return

        form = request.form
        order = Order(phone_number=form.get("phone_number", ""))
        for product in delivery.products:
            try:
                wanted = form.int(f"wanted:{product.ref}", 0)
            except HttpError:
                continue
            try:
                adjustment = form.int(f"adjustment:{product.ref}", 0)
            except HttpError:
                adjustment = 0
            if wanted or adjustment:
                order.products[product.ref] = ProductOrder(
                    wanted=wanted, adjustment=adjustment
                )

        if not delivery.orders:
            delivery.orders = {}

        if not order.products:
            if orderer.id in delivery.orders:
                del delivery.orders[orderer.id]
                delivery.persist()
            response.message("La commande est vide.", status="warning")
            response.redirect = delivery_url
            return
        delivery.orders[orderer.id] = order
        delivery.persist()

        if user and orderer.id == user.id:
            # Send the emails to everyone in the group.
            groups = request["groups"].groups
            if orderer.group_id in groups.keys():
                for email in groups[orderer.group_id].members:
                    emails.send_order(
                        request,
                        env,
                        person=Person(email=email),
                        delivery=delivery,
                        order=order,
                        group_id=orderer.group_id,
                        url_for=app.url_for,
                    )
            else:
                emails.send_order(
                    request,
                    env,
                    person=Person(email=orderer.email),
                    delivery=delivery,
                    order=order,
                    group_id=orderer.email,
                    url_for=app.url_for,
                )
        response.message(
            f"La commande pour « {orderer.name} » a bien été prise en compte, "
            "on a envoyé un récap par email 😘"
        )
        response.redirect = f"/distribution/{delivery.id}"
    else:
        order = delivery.orders.get(orderer.id) or Order()
        force_adjustment = "adjust" in request.query and user and user.is_staff
        response.html(
            "delivery/place_order.html",
            delivery=delivery,
            person=orderer,
            order=order,
            force_adjustment=force_adjustment,
        )


@app.route("/distribution/{id}/résumé-de-commandes", methods=["GET"])
async def show_orders_summary(request, response, id):
    delivery = Delivery.load(id)
    response.pdf(
        "delivery/show_orders_summary.html",
        {"delivery": delivery},
        css="order-summary.css",
        filename=utils.prefix("résumé-de-commandes.pdf", delivery),
    )

@app.route("/distribution/{id}/résumé-de-commandes.html", methods=["GET"])
async def show_orders_summary(request, response, id):
    delivery = Delivery.load(id)
    response.html(
        "delivery/show_orders_summary.html",
        delivery=delivery,
        display_prices=True
    )

@app.route("/distribution/{id}/rapport-complet.xlsx", methods=["GET"])
async def generate_report(request, response, id):
    delivery = Delivery.load(id)
    date = delivery.to_date.strftime("%Y-%m-%d")
    response.xlsx(
        reports.full(delivery),
        filename=f"{config.SITE_NAME}-{date}-rapport-complet.xlsx",
    )


@app.route("/distribution/{id}/ajuster/{ref}", methods=["GET", "POST"])
async def adjust_product(request, response, id, ref):
    delivery = Delivery.load(id)
    delivery_url = f"/distribution/{delivery.id}"
    product = None
    for product in delivery.products:
        if product.ref == ref:
            break
    else:
        response.message(f"Référence inconnue: {ref}")
        response.redirect = delivery_url
        return
    if request.method == "POST":
        form = request.form
        for email, order in delivery.orders.items():
            choice = order[product]
            choice.adjustment = form.int(email, 0)
            order[product] = choice
        delivery.persist()
        response.message(f"Le produit «{product.ref}» a bien été ajusté!")
        response.redirect = delivery_url
    else:
        response.html(
            "delivery/adjust_product.html", {"delivery": delivery, "product": product}
        )


@app.route("/distribution/{id}/paiements", methods=["GET"])
async def compute_payments(request, response, id):
    delivery = Delivery.load(id)
    groups = request["groups"]

    balance = []
    for group_id, order in delivery.orders.items():
        balance.append(
            (group_id, order.total(delivery.products, delivery, group_id) * -1)
        )

    producer_groups = {}

    for producer in delivery.producers.values():
        group = groups.get_user_group(producer.referent)
        # When a group contains multiple producer contacts,
        # the first one is elected to receive the money,
        # and all the other ones are separated in the table.
        group_id = None
        if hasattr(group, "id"):
            if (
                group.id not in producer_groups
                or producer_groups[group.id] == producer.referent_name
            ):
                producer_groups[group.id] = producer.referent_name
                group_id = group.id
        if not group_id:
            group_id = producer.referent_name

        amount = delivery.total_for_producer(producer.id)
        print(producer.id, amount)
        if amount:
            balance.append((group_id, amount))

    debiters, crediters = order_balance(balance)
    results = reduce_balance(debiters[:], crediters[:])

    results_dict = defaultdict(partial(defaultdict, float))

    for debiter, amount, crediter in results:
        results_dict[debiter][crediter] = amount

    template_name = "delivery/compute_balance.html"
    template_args = {
        "delivery": delivery,
        "debiters": debiters,
        "crediters": crediters,
        "results": results_dict,
        "debiters_groups": groups.groups,
        "crediters_groups": producer_groups,
    }

    response.html(template_name, template_args)
