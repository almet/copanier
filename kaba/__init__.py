import csv
from datetime import timedelta
from pathlib import Path
from time import perf_counter

import jwt
import ujson as json
import hupper
import minicli
from jinja2 import Environment, PackageLoader, select_autoescape
from roll import Roll, Response
from roll.extensions import cors, options, traceback, simple_server, static

from . import config, reports, session, utils, emails
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
        self.body = env.get_template(template_name).render(*args, **context)

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
    loader=PackageLoader("kaba", "templates"), autoescape=select_autoescape(["kaba"])
)


app = Roll()
cors(app, methods="*", headers="*")
options(app)


def auth_required(view):
    async def redirect(request, response, *a, **k):
        # FIXME do not return a view when Roll allows it.
        response.redirect = f"/sésame?next={request.path}"

    def wrapper(request, response, *args, **kwargs):
        token = request.cookies.get("token")
        email = None
        if token:
            decoded = read_token(token)
            email = decoded.get("sub")
        if not email:
            return redirect(request, response, *args, **kwargs)
        user = Person(email=email)
        request["user"] = user
        session.user.set(user)
        return view(request, response, *args, **kwargs)

    return wrapper


def create_token(email):
    return jwt.encode(
        {"sub": str(email), "exp": utils.utcnow() + timedelta(days=7)},
        config.SECRET,
        config.JWT_ALGORITHM,
    )


def read_token(token):
    try:
        return jwt.decode(token, config.SECRET, algorithms=[config.JWT_ALGORITHM])
    except (jwt.DecodeError, jwt.ExpiredSignatureError):
        return {}


@app.listen("request")
async def attach_request(request, response):
    response.request = request


@app.listen("startup")
async def on_startup():
    configure()


@app.route("/sésame", methods=["GET"])
async def sesame(request, response):
    response.html("sesame.html")


@app.route("/sésame", methods=["POST"])
async def send_sesame(request, response):
    email = request.form.get("email")
    token = create_token(email)
    emails.send(
        email,
        "Sésame Panio",
        emails.ACCESS_GRANTED.format(hostname=request.host, token=token.decode()),
    )
    response.message(f"Un sésame vous a été envoyé à l'adresse '{email}'")
    response.redirect = "/"


@app.route("/sésame/{token}", methods=["GET"])
async def set_sesame(request, response, token):
    decoded = read_token(token)
    if not decoded:
        response.message("Sésame invalide :(", status="error")
    else:
        response.message("Yay! Le sésame a fonctionné. Bienvenue à bord! :)")
        response.cookies.set(name="token", value=token)
    response.redirect = "/"


@app.route("/", methods=["GET"])
@auth_required
async def home(request, response):
    response.html("home.html", deliveries=Delivery.all())


@app.route("/livraison/new", methods=["GET"])
@auth_required
async def new_delivery(request, response):
    response.html("edit_delivery.html", delivery={})


@app.route("/livraison/new", methods=["POST"])
@auth_required
async def create_delivery(request, response):
    form = request.form
    data = {}
    for name, field in Delivery.__dataclass_fields__.items():
        if name in form:
            data[name] = form.get(name)
    delivery = Delivery(**data)
    delivery.persist()
    response.message("La livraison a bien été créée!")
    response.redirect = f"/livraison/{delivery.id}"


@app.route("/livraison/{id}/importer/produits", methods=["POST"])
@auth_required
async def import_products(request, response, id):
    delivery = Delivery.load(id)
    delivery.products = []
    reader = csv.DictReader(
        request.files.get("data").read().decode().splitlines(), delimiter=";"
    )
    for row in reader:
        delivery.products.append(Product(**row))
    delivery.persist()
    response.message("Les produits de la livraison ont bien été mis à jour!")
    response.redirect = f"/livraison/{delivery.id}"


@app.route("/livraison/{id}/edit", methods=["GET"])
@auth_required
async def edit_delivery(request, response, id):
    delivery = Delivery.load(id)
    response.html("edit_delivery.html", {"delivery": delivery})


@app.route("/livraison/{id}/edit", methods=["POST"])
@auth_required
async def post_delivery(request, response, id):
    delivery = Delivery.load(id)
    form = request.form
    for name, field in Delivery.__dataclass_fields__.items():
        if name in form:
            setattr(delivery, name, form.get(name))
    delivery.persist()
    response.message("La livraison a bien été mise à jour!")
    response.redirect = f"/livraison/{delivery.id}"


@app.route("/livraison/{id}", methods=["GET"])
@auth_required
async def view_delivery(request, response, id):
    delivery = Delivery.load(id)
    response.html("delivery.html", {"delivery": delivery})


@app.route("/livraison/{id}/commander", methods=["GET"])
@auth_required
async def order_form(request, response, id):
    delivery = Delivery.load(id)
    email = request.query.get("email", None)
    if not email:
        user = session.user.get(None)
        if user:
            email = user.email
    if email:
        order = delivery.orders.get(email) or Order()
        response.html(
            "place_order.html", {"delivery": delivery, "person": email, "order": order}
        )
    else:
        response.message("Impossible de comprendre pour qui passer commande…", "error")
        response.redirect = request.path


@app.route("/livraison/{id}/émargement", methods=["GET"])
@auth_required
async def signing_sheet(request, response, id):
    delivery = Delivery.load(id)
    response.html("signing_sheet.html", {"delivery": delivery})


@app.route("/livraison/{id}/commander", methods=["POST"])
@auth_required
async def place_order(request, response, id):
    delivery = Delivery.load(id)
    email = request.query.get("email")
    order = Order()
    form = request.form
    for product in delivery.products:
        quantity = form.int(product.ref, 0)
        if quantity:
            order.products[product.ref] = ProductOrder(wanted=quantity)
    if not delivery.orders:
        delivery.orders = {}
    delivery.orders[email] = order
    delivery.persist()
    response.message("Jour de fête! Votre commande a bien été prise en compte!")
    response.redirect = request.url.decode()


@app.route("/livraison/{id}/importer/commande", methods=["POST"])
@auth_required
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


@app.route("/livraison/{id}/rapport.xlsx", methods=["GET"])
@auth_required
async def xls_report(request, response, id):
    delivery = Delivery.load(id)
    response.body = reports.summary(delivery)
    mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    response.headers["Content-Disposition"] = f'attachment; filename="epinamap.xlsx"'
    response.headers["Content-Type"] = f"{mimetype}; charset=utf-8"


@app.route("/livraison/{id}/rapport-complet.xlsx", methods=["GET"])
@auth_required
async def xls_full_report(request, response, id):
    delivery = Delivery.load(id)
    response.body = reports.full(delivery)
    mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    response.headers["Content-Disposition"] = f'attachment; filename="epinamap.xlsx"'
    response.headers["Content-Type"] = f"{mimetype}; charset=utf-8"


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


@minicli.wrap
def cli_wrapper():
    configure()
    start = perf_counter()
    yield
    elapsed = perf_counter() - start
    print(f"Done in {elapsed:.5f} seconds.")


@minicli.cli
def serve(reload=False):
    """Run a web server (for development only)."""
    if reload:
        hupper.start_reloader("kaba.serve")
    traceback(app)
    static(app, root=Path(__file__).parent / "static")
    simple_server(app, port=2244)


def main():
    minicli.run()
