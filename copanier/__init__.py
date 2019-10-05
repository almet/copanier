import csv
from collections import defaultdict
from pathlib import Path
from functools import partial

import ujson as json
import minicli
from jinja2 import Environment, PackageLoader, select_autoescape
from roll import Roll as BaseRoll, Response as RollResponse, HttpError
from roll.extensions import traceback, simple_server, static
from slugify import slugify

from debts.solver import order_balance, check_balance, reduce_balance
from weasyprint import HTML

from . import config, reports, session, utils, emails, loggers, imports
from .models import Delivery, Order, Person, Product, ProductOrder, Groups, Group


class Response(RollResponse):
    def render_template(self, template_name, *args, **kwargs):
        context = app.context()
        context.update(kwargs)
        context["request"] = self.request
        context["config"] = config
        context["request"] = self.request
        if self.request.cookies.get("message"):
            context["message"] = json.loads(self.request.cookies["message"])
            self.cookies.set("message", "")
        return env.get_template(template_name).render(*args, **context)

    def html(self, template_name, *args, **kwargs):
        self.headers["Content-Type"] = "text/html; charset=utf-8"
        self.body = self.render_template(template_name, *args, **kwargs)

    def render_pdf(self, template_name, *args, **kwargs):
        html = self.render_template(template_name, *args, **kwargs)

        static_folder = Path(__file__).parent / "static"
        stylesheets = [
            static_folder / "app.css",
            static_folder / "icomoon.css",
            static_folder / "page.css",
        ]
        if "css" in kwargs:
            stylesheets.append(static_folder / kwargs["css"])

        return HTML(string=html).write_pdf(stylesheets=stylesheets)

    def pdf(self, template_name, *args, **kwargs):
        self.body = self.render_pdf(template_name, *args, **kwargs)
        mimetype = "application/pdf"
        filename = kwargs.get("filename", "file.pdf")
        self.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        self.headers["Content-Type"] = f"{mimetype}; charset=utf-8"

    def xlsx(self, body, filename=f"{config.SITE_NAME}.xlsx"):
        self.body = body
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        self.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        self.headers["Content-Type"] = f"{mimetype}; charset=utf-8"

    def redirect(self, location):
        self.status = 302
        self.headers["Location"] = location

    redirect = property(None, redirect)

    def message(self, text, status="success"):
        self.cookies.set("message", json.dumps((text, status)))


class Roll(BaseRoll):
    Response = Response

    _context_func = []

    def context(self):
        context = {}
        for func in self._context_func:
            context.update(func())
        return context

    def register_context(self, func):
        self._context_func.append(func)


env = Environment(
    loader=PackageLoader("copanier", "templates"),
    autoescape=select_autoescape(["copanier"]),
)


def date_filter(value):
    return value.strftime(r"%A %d&nbsp;%B")


def time_filter(value):
    return value.strftime(r"%H:%M")


env.filters["date"] = date_filter
env.filters["time"] = time_filter

app = Roll()
traceback(app)


def staff_only(view):
    async def decorator(request, response, *args, **kwargs):
        user = session.user.get(None)
        if not user or not user.is_staff:
            response.message("Désolé, c'est réservé au staff par ici", "warning")
            response.redirect = request.headers.get("REFERRER", "/")
            return
        return await view(request, response, *args, **kwargs)

    return decorator


@app.listen("request")
async def auth_required(request, response):
    # Should be handler Roll side?
    # In dev mode, we serve the static, but we don't have yet a way to mark static
    # route as unprotected.
    if request.path.startswith("/static/"):
        return
    if request.route.payload and not request.route.payload.get("unprotected"):
        token = request.cookies.get("token")
        email = None
        if token:
            decoded = utils.read_token(token)
            email = decoded.get("sub")
        if not email:
            response.redirect = f"/sésame?next={request.path}"
            return response

        groups = Groups.load()
        request["groups"] = groups

        group = groups.get_user_group(email)
        user_info = {"email": email}
        if group:
            user_info.update(dict(group_id=group.id, group_name=group.name))
        user = Person(**user_info)
        request["user"] = user
        session.user.set(user)


@app.listen("request")
async def attach_request(request, response):
    response.request = request


@app.listen("request")
async def log_request(request, response):
    if request.method == "POST":
        message = {
            "date": utils.utcnow().isoformat(),
            "data": request.form,
            "user": request.get("user"),
        }
        loggers.request_logger.info(
            json.dumps(message, sort_keys=True, ensure_ascii=False)
        )


@app.listen("startup")
async def on_startup():
    configure()
    Delivery.init_fs()
    Groups.init_fs()


@app.route("/sésame", methods=["GET"], unprotected=True)
async def sesame(request, response):
    response.html("sesame.html")


@app.route("/sésame", methods=["POST"], unprotected=True)
async def send_sesame(request, response):
    email = request.form.get("email")
    token = utils.create_token(email)
    try:
        emails.send_from_template(
            env,
            "access_granted",
            email,
            f"Sésame {config.SITE_NAME}",
            hostname=request.host,
            token=token.decode(),
        )
    except RuntimeError:
        response.message("Oops, impossible d'envoyer le courriel…", status="error")
    else:
        response.message(f"Un sésame vous a été envoyé à l'adresse '{email}'")
    response.redirect = "/"


@app.route("/sésame/{token}", methods=["GET"], unprotected=True)
async def set_sesame(request, response, token):
    decoded = utils.read_token(token)
    if not decoded:
        response.message("Sésame invalide :(", status="error")
    else:
        response.message("Yay! Le sésame a fonctionné. Bienvenue à bord! :)")
        response.cookies.set(
            name="token", value=token, httponly=True, max_age=60 * 60 * 24 * 7
        )
    response.redirect = "/"


@app.route("/déconnexion", methods=["GET"])
async def logout(request, response):
    response.cookies.set(name="token", value="", httponly=True)
    response.redirect = "/"


@app.route("/", methods=["GET"])
async def home(request, response):
    if not request["user"].group_id:
        response.redirect = "/groupes"
        return
    response.html(
        "home.html",
        incoming=Delivery.incoming(),
        former=Delivery.former(),
        archives=list(Delivery.all(is_archived=True)),
    )


@app.route("/groupes", methods=["GET"])
async def handle_groups(request, response):
    response.html("groups.html", {"groups": request["groups"]})


@app.route("/groupes/{id}/rejoindre", method=["GET"])
async def join_group(request, response, id):
    user = session.user.get(None)
    group = request["groups"].add_user(user.email, id)
    request["groups"].persist()
    redirect = "/" if not request["user"].group_id else "/groupes"

    response.message(f"Vous avez bien rejoint le groupe '{group.name}'")
    response.redirect = redirect


@app.route("/groupes/créer", methods=["GET", "POST"])
async def create_group(request, response):
    group = None
    if request.method == "POST":
        form = request.form
        members = []
        if form.get("members"):
            members = [m.strip() for m in form.get("members").split(",")]

        if not request["user"].group_id and request["user"].email not in members:
            members.append(request["user"].email)

        group = Group.create(
            id=slugify(form.get("name")), name=form.get("name"), members=members
        )
        request["groups"].add_group(group)
        request["groups"].persist()
        response.message(f"Le groupe {group.name} à bien été créé")
        response.redirect = "/"
    response.html("edit_group.html", group=group)


@app.route("/groupes/{id}/éditer", methods=["GET", "POST"])
async def edit_group(request, response, id):
    assert id in request["groups"].groups, "Impossible de trouver le groupe"
    group = request["groups"].groups[id]
    if request.method == "POST":
        form = request.form
        members = []
        if form.get("members"):
            members = [m.strip() for m in form.get("members").split(",")]
        group.members = members
        group.name = form.get("name")
        request["groups"].groups[id] = group
        request["groups"].persist()
        response.redirect = "/groupes"
    response.html("edit_group.html", group=group)


@app.route("/groupes/{id}/supprimer", methods=["GET"])
async def delete_group(request, response, id):
    assert id in request["groups"].groups, "Impossible de trouver le groupe"
    deleted = request["groups"].groups.pop(id)
    request["groups"].persist()
    response.message(f"Le groupe {deleted.name} à bien été supprimé")
    response.redirect = "/groupes"


@app.route("/archives", methods=["GET"])
async def view_archives(request, response):
    response.html("archive.html", {"deliveries": Delivery.all(is_archived=True)})


@app.route("/livraison/archive/{id}", methods=["GET"])
async def view_archive(request, response, id):
    delivery = Delivery.load(f"archive/{id}")
    response.html("delivery.html", {"delivery": delivery})


@app.route("/livraison/{id}/archiver", methods=["GET"])
@staff_only
async def archive_delivery(request, response, id):
    delivery = Delivery.load(id)
    delivery.archive()
    response.message("La livraison a été archivée")
    response.redirect = f"/livraison/{delivery.id}"


@app.route("/livraison/archive/{id}/désarchiver", methods=["GET"])
@staff_only
async def unarchive_delivery(request, response, id):
    delivery = Delivery.load(f"archive/{id}")
    delivery.unarchive()
    response.message("La livraison a été désarchivée")
    response.redirect = f"/livraison/{delivery.id}"


@app.route("/livraison", methods=["GET"])
async def new_delivery(request, response):
    response.html("edit_delivery.html", delivery={})


@app.route("/livraison", methods=["POST"])
@staff_only
async def create_delivery(request, response):
    form = request.form
    data = {}
    data["from_date"] = f"{form.get('date')} {form.get('from_time')}"
    data["to_date"] = f"{form.get('date')} {form.get('to_time')}"
    for name in Delivery.__dataclass_fields__.keys():
        if name in form:
            data[name] = form.get(name)
    delivery = Delivery(**data)
    delivery.persist()
    response.message("La livraison a bien été créée!")
    response.redirect = f"/livraison/{delivery.id}"


@app.route("/livraison/{id}/importer/produits", methods=["POST"])
@staff_only
async def import_products(request, response, id):
    delivery = Delivery.load(id)
    delivery.products = []
    data = request.files.get("data")
    error_path = f"/livraison/{delivery.id}/edit"

    if data.filename.endswith(".xlsx"):
        try:
            imports.products_and_producers_from_xlsx(delivery, data)
        except ValueError as err:
            message = f"Impossible d'importer le fichier. {err.args[0]}"
            response.message(message, status="error")
            response.redirect = error_path
            return
    else:
        response.message("Format de fichier inconnu", status="error")
        response.redirect = error_path
        return
    response.message("Les produits et producteur⋅ice⋅s ont bien été mis à jour!")
    response.redirect = f"/livraison/{delivery.id}"


@app.route("/livraison/{id}/producteurices")
@app.route("/livraison/{id}/producteurices.pdf")
async def list_producers(request, response, id):
    delivery = Delivery.load(id)
    template_name = "list_products.html"
    template_params = {
        "edit_mode": True,
        "list_only": True,
        "delivery": delivery,
        "referent": request.query.get("referent", None),
    }

    if request.url.endswith(b".pdf"):
        template_params["edit_mode"] = False
        response.pdf(
            template_name,
            template_params,
            filename=utils.prefix("producteurices.pdf", delivery),
        )
    else:
        response.html(template_name, template_params)


@app.route("/livraison/{id}/{producer}/bon-de-commande.pdf", methods=["GET"])
async def pdf_for_producer(request, response, id, producer):
    delivery = Delivery.load(id)
    date = delivery.to_date.strftime("%Y-%m-%d")
    response.pdf(
        "list_products.html",
        {"list_only": True, "delivery": delivery, "producers": [producer]},
        filename=utils.prefix(f"bon-de-commande-{producer}.pdf", delivery),
    )


@app.route("/livraison/{delivery_id}/{producer_id}/éditer", methods=["GET", "POST"])
async def edit_producer(request, response, delivery_id, producer_id):
    delivery = Delivery.load(delivery_id)
    producer = delivery.producers.get(producer_id)
    if request.method == "POST":
        form = request.form
        producer.referent = form.get("referent")
        producer.referent_tel = form.get("referent_tel")
        producer.description = form.get("description")
        producer.contact = form.get("contact")
        delivery.producers[producer_id] = producer
        delivery.persist()

    response.html(
        "edit_producer.html",
        {
            "delivery": delivery,
            "producer": producer,
            "products": delivery.get_products_by(producer.id),
        },
    )


@app.route(
    "/livraison/{delivery_id}/{producer_id}/{product_ref}/éditer",
    methods=["GET", "POST"],
)
async def edit_product(request, response, delivery_id, producer_id, product_ref):
    delivery = Delivery.load(delivery_id)
    product = delivery.get_product(product_ref)

    if request.method == "POST":
        form = request.form
        product.name = form.get("name")
        product.price = form.float("price")
        product.unit = form.get("unit")
        product.description = form.get("description")
        product.url = form.get("url")
        if form.get("packing"):
            product.packing = form.int("packing")
        else:
            product.packing = None
        if "rupture" in form:
            product.rupture = form.get("rupture")
        else:
            product.rupture = None
        delivery.persist()
        response.message("Le produit à bien été modifié")
        response.redirect = f"/livraison/{delivery_id}/{producer_id}/éditer"

    response.html("edit_product.html", {"delivery": delivery, "product": product})


@app.route(
    "/livraison/{delivery_id}/{producer_id}/ajouter-produit", methods=["GET", "POST"]
)
async def create_product(request, response, delivery_id, producer_id):
    delivery = Delivery.load(delivery_id)
    product = Product(name="", ref="", price=0)

    if request.method == "POST":
        product.producer = producer_id
        form = request.form
        product.update_from_form(form)
        product.ref = slugify(f"{producer_id}-{product.name}")

        delivery.products.append(product)
        delivery.persist()
        response.message("Le produit à bien été créé")
        response.redirect = (
            f"/livraison/{delivery_id}/producteurice/{producer_id}/éditer"
        )

    response.html(
        "edit_product.html",
        {"delivery": delivery, "producer_id": producer_id, "product": product},
    )


@app.route("/livraison/{id}/gérer", methods=["GET"])
async def delivery_toolbox(request, response, id):
    delivery = Delivery.load(id)
    response.html(
        "delivery_toolbox.html",
        {
            "delivery": delivery,
            "referents": [p.referent for p in delivery.producers.values()],
        },
    )


@app.route("/livraison/{id}/envoi-email-referentes", methods=["GET", "POST"])
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
        response.redirect = f"/livraison/{id}/gérer"

    response.html("prepare_referent_email.html", {"delivery": delivery})


@app.route("/livraison/{id}/exporter", methods=["GET"])
async def export_products(request, response, id):
    delivery = Delivery.load(id)
    response.xlsx(reports.products(delivery))


@app.route("/livraison/archive/{id}/exporter/produits", methods=["GET"])
async def export_archived_products(request, response, id):
    delivery = Delivery.load(f"archive/{id}")
    response.xlsx(reports.products(delivery))


@app.route("/livraison/{id}/edit", methods=["GET"])
@staff_only
async def edit_delivery(request, response, id):
    delivery = Delivery.load(id)
    response.html("edit_delivery.html", {"delivery": delivery})


@app.route("/livraison/{id}/edit", methods=["POST"])
@staff_only
async def post_delivery(request, response, id):
    delivery = Delivery.load(id)
    form = request.form
    delivery.from_date = f"{form.get('date')} {form.get('from_time')}"
    delivery.to_date = f"{form.get('date')} {form.get('to_time')}"
    for name in Delivery.__dataclass_fields__.keys():
        if name in form:
            setattr(delivery, name, form.get(name))
    delivery.persist()
    response.message("La livraison a bien été mise à jour!")
    response.redirect = f"/livraison/{delivery.id}"


@app.route("/livraison/{id}", methods=["GET"])
async def view_delivery(request, response, id):
    delivery = Delivery.load(id)
    response.html("delivery.html", {"delivery": delivery})


@app.route("/livraison/{id}/commander", methods=["POST", "GET"])
async def place_order(request, response, id):
    delivery = Delivery.load(id)
    # email = request.query.get("email", None)
    user = session.user.get(None)
    orderer = request.query.get("orderer", None)
    if orderer:
        orderer = Person(email=orderer, group_id=orderer)

    delivery_url = f"/livraison/{delivery.id}"
    if not orderer and user:
        orderer = user

    if not orderer:
        response.message("Impossible de comprendre pour qui passer commande…", "error")
        response.redirect = delivery_url
        return

    if request.method == "POST":
        # When the delivery is closed, only staff can access.
        if delivery.status == delivery.CLOSED and not (user and user.is_staff):
            response.message("La livraison est fermée", "error")
            response.redirect = delivery_url
            return

        form = request.form
        order = Order()
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
                    )
            else:
                emails.send_order(
                    request,
                    env,
                    person=Person(email=orderer.email),
                    delivery=delivery,
                    order=order,
                )
        response.message(
            f"La commande pour « {orderer.name} » a bien été prise en compte!"
        )
        response.redirect = f"/livraison/{delivery.id}"
    else:
        order = delivery.orders.get(orderer.id) or Order()
        force_adjustment = "adjust" in request.query and user and user.is_staff
        response.html(
            "place_order.html",
            delivery=delivery,
            person=orderer,
            order=order,
            force_adjustment=force_adjustment,
        )


@app.route("/livraison/{id}/émargement", methods=["GET"])
async def signing_sheet(request, response, id):
    delivery = Delivery.load(id)
    response.pdf(
        "signing_sheet.html",
        {"delivery": delivery},
        css="signing-sheet.css",
        filename=utils.prefix("commandes-par-groupe.pdf", delivery),
    )


@app.route("/livraison/{id}/importer/commande", methods=["POST"])
@staff_only
async def import_commande(request, response, id):
    email = request.form.get("email")
    order = Order()
    reader = csv.DictReader(
        request.files.get("data").read().decode().splitlines(), delimiter=";"
    )
    for row in reader:
        wanted = int(row["wanted"] or 0)
        if wanted:
            order.products[row["ref"]] = ProductOrder(wanted=wanted)
    delivery = Delivery.load(id)
    delivery.orders[email] = order
    delivery.persist()
    response.message(f"Yallah! La commande de {email} a bien été importée !")
    response.redirect = f"/livraison/{delivery.id}"


@app.route("/livraison/{id}/importer/commandes", methods=["POST"])
@staff_only
async def import_multiple_commands(request, response, id):
    reader = csv.DictReader(
        request.files.get("data").read().decode().splitlines(), delimiter=";"
    )
    orders = defaultdict(Order)

    current_ref = None
    for row in reader:
        for label, value in row.items():
            if label == "ref":
                current_ref = value
            else:
                wanted = int(value or 0)
                if wanted:
                    orders[label].products[current_ref] = ProductOrder(wanted=wanted)
    delivery = Delivery.load(id)
    for email, order in orders.items():
        delivery.orders[email] = order
    delivery.persist()
    response.message(f"Yes ! Les commandes ont bien été importées !")
    response.redirect = f"/livraison/{delivery.id}"


@app.route("/livraison/{id}/rapport-complet.xlsx", methods=["GET"])
async def xls_full_report(request, response, id):
    delivery = Delivery.load(id)
    date = delivery.to_date.strftime("%Y-%m-%d")
    response.xlsx(
        reports.full(delivery),
        filename=f"{config.SITE_NAME}-{date}-rapport-complet.xlsx",
    )


@app.route("/livraison/{id}/ajuster/{ref}", methods=["GET", "POST"])
@staff_only
async def adjust_product(request, response, id, ref):
    delivery = Delivery.load(id)
    delivery_url = f"/livraison/{delivery.id}"
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
        response.html("adjust_product.html", {"delivery": delivery, "product": product})


@app.route("/livraison/{id}/solde", methods=["GET"])
@app.route("/livraison/{id}/solde.pdf", methods=["GET"])
@staff_only
async def delivery_balance(request, response, id):
    delivery = Delivery.load(id)
    groups = request["groups"]

    balance = []
    for group_id, order in delivery.orders.items():
        balance.append((group_id, order.total(delivery.products) * -1))

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
        if amount:
            balance.append((group_id, amount))

    debiters, crediters = order_balance(balance)
    check_balance(debiters, crediters)
    results = reduce_balance(debiters[:], crediters[:])

    results_dict = defaultdict(partial(defaultdict, float))

    for debiter, amount, crediter in results:
        results_dict[debiter][crediter] = amount

    template_name = "delivery_balance.html"
    template_args = {
        "delivery": delivery,
        "debiters": debiters,
        "crediters": crediters,
        "results": results_dict,
        "debiters_groups": groups.groups,
        "crediters_groups": producer_groups,
    }

    if request.url.endswith(b".pdf"):
        date = delivery.to_date.strftime("%Y-%m-%d")
        response.pdf(
            template_name,
            template_args,
            filename=utils.prefix("répartition-des-chèques.pdf", delivery),
        )
    else:
        response.html(template_name, template_args)


def configure():
    config.init()


@minicli.cli()
def shell():
    """Run an ipython in app context."""
    try:
        from IPython import start_ipython
    except ImportError:
        print('IPython is not installed. Type "pip install ipython"')
    else:
        start_ipython(
            argv=[],
            user_ns={
                "app": app,
                "Product": Product,
                "Person": Person,
                "Order": Order,
                "Delivery": Delivery,
            },
        )


@minicli.cli
def serve(reload=False):
    """Run a web server (for development only)."""
    if reload:
        import hupper

        hupper.start_reloader("copanier.serve")
    static(app, root=Path(__file__).parent / "static")
    simple_server(app, port=2244)


def main():
    minicli.run()
