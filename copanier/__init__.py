import csv
from pathlib import Path

import ujson as json
import minicli
from jinja2 import Environment, PackageLoader, select_autoescape
from roll import Roll, Response, HttpError
from roll.extensions import traceback, simple_server, static

from . import config, reports, session, utils, emails, loggers, imports
from .models import Delivery, Order, Person, Product, ProductOrder


class Response(Response):
    def html(self, template_name, *args, **kwargs):
        self.headers["Content-Type"] = "text/html; charset=utf-8"
        context = app.context()
        context.update(kwargs)
        context["request"] = self.request
        if self.request.cookies.get("message"):
            context["message"] = json.loads(self.request.cookies["message"])
            self.cookies.set("message", "")
        context["config"] = config
        self.body = env.get_template(template_name).render(*args, **context)

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


class Roll(Roll):
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
        user = Person(email=email)
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


@app.route("/sésame", methods=["GET"], unprotected=True)
async def sesame(request, response):
    response.html("sesame.html")


@app.route("/sésame", methods=["POST"])
async def send_sesame(request, response, unprotected=True):
    email = request.form.get("email")
    token = utils.create_token(email)
    emails.send_from_template(
        env,
        "access_granted",
        email,
        f"Sésame {config.SITE_NAME}",
        hostname=request.host,
        token=token.decode(),
    )
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
    response.html("home.html", incoming=Delivery.incoming(), former=Delivery.former())


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
    for name, field in Delivery.__dataclass_fields__.items():
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

    if data.filename.endswith((".csv", ".xlsx")):
        try:
            if data.filename.endswith(".csv"):
                imports.products_from_csv(delivery, data.read().decode())
            else:
                imports.products_from_xlsx(delivery, data)
        except ValueError as err:
            message = f"Impossible d'importer le fichier. {err.args[0]}"
            response.message(message, status="error")
            response.redirect = error_path
            return
    else:
        response.message("Format de fichier inconnu", status="error")
        response.redirect = error_path
        return
    response.message("Les produits de la livraison ont bien été mis à jour!")
    response.redirect = f"/livraison/{delivery.id}"


@app.route("/livraison/{id}/exporter/produits", methods=["GET"])
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
    for name, field in Delivery.__dataclass_fields__.items():
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
    email = request.query.get("email", None)
    user = session.user.get(None)
    delivery_url = f"/livraison/{delivery.id}"
    if not email and user:
        email = user.email
    if not email:
        response.message("Impossible de comprendre pour qui passer commande…", "error")
        response.redirect = delivery_url
        return
    if request.method == "POST":
        if not (user and user.is_staff) and delivery.status == delivery.CLOSED:
            response.message("La livraison est fermée", "error")
            response.redirect = delivery_url
            return
        form = request.form
        order = Order(paid=form.bool("paid", False))
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
            if email in delivery.orders:
                del delivery.orders[email]
                delivery.persist()
            response.message("La commande est vide.", status="warning")
            response.redirect = delivery_url
            return
        delivery.orders[email] = order
        delivery.persist()
        if user and user.email == email:
            # Only send email if order has been placed by the user itself.
            emails.send_order(
                request, env, person=Person(email=email), delivery=delivery, order=order
            )
        response.message(f"La commande pour «{email}» a bien été prise en compte!")
        response.redirect = f"/livraison/{delivery.id}"
    else:
        order = delivery.orders.get(email) or Order()
        force_adjustment = "adjust" in request.query and user and user.is_staff
        response.html(
            "place_order.html",
            delivery=delivery,
            person=Person(email=email),
            order=order,
            force_adjustment=force_adjustment,
        )


@app.route("/livraison/{id}/courriel", methods=["GET"])
async def send_order(request, response, id):
    delivery = Delivery.load(id)
    email = request.query.get("email")
    order = delivery.orders.get(email)
    if not order:
        response.message(f"Aucune commande pour «{email}»", status="warning")
    else:
        emails.send_order(
            request, env, person=Person(email=email), delivery=delivery, order=order
        )
        response.message(f"Résumé de commande envoyé à «{email}»")
    response.redirect = f"/livraison/{delivery.id}"


@app.route("/livraison/{id}/émargement", methods=["GET"])
async def signing_sheet(request, response, id):
    delivery = Delivery.load(id)
    response.html("signing_sheet.html", {"delivery": delivery})


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
    response.message(f"Yallah! La commande de {email} a bien été importée!")
    response.redirect = f"/livraison/{delivery.id}"


@app.route("/livraison/{id}/bon-de-commande.xlsx", methods=["GET"])
async def xls_report(request, response, id):
    delivery = Delivery.load(id)
    response.xlsx(reports.summary(delivery))


@app.route("/livraison/{id}/rapport-complet.xlsx", methods=["GET"])
async def xls_full_report(request, response, id):
    delivery = Delivery.load(id)
    response.xlsx(reports.full(delivery))


@app.route("/livraison/{id}/ajuster/{ref}", methods=["GET", "POST"])
@staff_only
async def adjust_product(request, response, id, ref):
    delivery = Delivery.load(id)
    delivery_url = f"/livraison/{delivery.id}"
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


@app.route("/livraison/{id}/solde", methods=["GET", "POST"])
@staff_only
async def delivery_balance(request, response, id):
    delivery = Delivery.load(id)
    delivery_url = f"/livraison/{delivery.id}"
    if request.method == "POST":
        form = request.form
        for email, order in delivery.orders.items():
            order.paid = form.bool(email, False)
        delivery.persist()
        response.message(f"Les soldes ont bien été mis à jour!")
        response.redirect = delivery_url
    else:
        response.html("delivery_balance.html", {"delivery": delivery})


@app.route("/livraison/{id}/solde.xlsx", methods=["GET"])
async def delivery_balance_report(request, response, id):
    delivery = Delivery.load(id)
    response.xlsx(reports.balance(delivery))


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
