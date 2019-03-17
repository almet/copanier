import os
from time import perf_counter

import ujson as json
import hupper
import minicli
from bson import ObjectId
from jinja2 import Environment, PackageLoader, select_autoescape
from pymongo import MongoClient
from roll import Roll, Response
from roll.extensions import cors, options, traceback, simple_server

from .base import Document, Str, Float, Array, Email, Int, Reference, Datetime, Mapping


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


class Producer(Document):
    __collection__ = "producers"
    name = Str(required=True)

    @property
    def products(self):
        return Product.find(producer=self._id)


class Product(Document):
    __collection__ = "products"
    producer = Reference(Producer, required=True)
    name = Str(required=True)
    ref = Str(required=True)
    description = Str()
    price = Float(required=True)


class Person(Document):
    __collection__ = "persons"
    first_name = Str()
    last_name = Str()
    email = Email()


class ProductOrder(Document):
    wanted = Int()
    ordered = Int()


class PersonOrder(Document):
    person = Str()
    products = Mapping(str, ProductOrder)

    def get_quantity(self, product):
        choice = self.products.get(product.ref)
        return choice.wanted if choice else 0

    def total(self, products):
        products = {p.ref: p for p in products}
        return round(
            sum(p.wanted * products[ref].price for ref, p in self.products.items()), 2
        )


class Order(Document):
    __collection__ = "orders"
    when = Datetime(required=True)
    where = Str()
    producer = Reference(Producer, required=True)
    products = Array(Product)
    orders = Mapping(str, PersonOrder)

    def product_wanted(self, product):
        return round(
            sum([po.products[product.ref].wanted for po in self.orders.values()])
        )


app = Roll()
cors(app, methods="*", headers="*")
options(app)


@app.listen("request")
async def attach_request(request, response):
    response.request = request


@app.listen("startup")
async def on_startup():
    connect()


@app.route("/", methods=["GET"])
async def home(request, response):
    response.html("home.html", {"orders": Order.find()})


@app.route("/commande/{order_id}/total", methods=["GET"])
async def view_order(request, response, order_id):
    order = Order.find_one(_id=ObjectId(order_id))
    total = round(sum(po.total(order.products) for po in order.orders.values()), 2)
    response.html(
        "order.html",
        {
            "order": order,
            "producer": Producer.find_one(_id=order.producer),
            "total": total,
        },
    )


@app.route("/commande/{order_id}", methods=["GET"])
async def order_form(request, response, order_id):
    order = Order.find_one(_id=ObjectId(order_id))
    email = request.query.get("email")
    person_order = order.orders.get(email)
    response.html(
        "place_order.html",
        {
            "order": order,
            "person": email,
            "person_order": person_order,
            "producer": Producer.find_one(_id=order.producer),
        },
    )


@app.route("/commande/{order_id}", methods=["POST"])
async def place_order(request, response, order_id):
    order = Order.find_one(_id=ObjectId(order_id))
    email = request.query.get("email")
    person_order = PersonOrder(person=email)
    form = request.form
    for product in order.products:
        quantity = form.int(product.ref, 0)
        if quantity:
            person_order.products[product.ref] = ProductOrder(wanted=quantity)
    if not order.orders:
        order.orders = {}
    order.orders[email] = person_order
    order.replace_one()
    response.headers["Location"] = request.url.decode()
    response.status = 302


def connect():
    db = os.environ.get("KABA_DB", "mongodb://localhost/kaba")
    client = MongoClient(db)
    db = client.get_database()
    Producer.bind(db)
    Product.bind(db)
    Order.bind(db)
    Person.bind(db)
    return client


@minicli.cli()
def shell():
    """Run an ipython already connected to Mongo."""
    try:
        from IPython import start_ipython
    except ImportError:
        print('IPython is not installed. Type "pip install ipython"')
    else:
        start_ipython(
            argv=[],
            user_ns={
                "Producer": Producer,
                "app": app,
                "Product": Product,
                "Person": Person,
                "Order": Order,
            },
        )


@minicli.wrap
def cli_wrapper():
    connect()
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
    simple_server(app, port=2244)


def main():
    minicli.run()
