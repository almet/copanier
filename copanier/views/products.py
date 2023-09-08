from datetime import datetime

import random
import string

from slugify import slugify
from .core import app
from ..models import Delivery, Product, Producer
from .. import utils


@app.route("/produits/{id}")
@app.route("/produits/{id}/produits.pdf")
async def list_products(request, response, id):
    delivery = Delivery.load(id)
    template_name = "products/list_products.html"
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
            css="landscape.css",
            filename=utils.prefix("producteurices.pdf", delivery),
        )
    else:
        response.html(template_name, template_params)


@app.route("/produits/{delivery_id}/producteurs/créer", methods=["GET", "POST"])
async def create_producer(request, response, delivery_id):
    delivery = Delivery.load(delivery_id)
    producer = None
    if request.method == "POST":
        form = request.form
        name = form.get("name")
        producer_id = slugify(name)

        producer = Producer(name=name, id=producer_id)
        producer.referent = form.get("referent")
        producer.referent_tel = form.get("referent_tel")
        producer.referent_name = form.get("referent_name")
        producer.description = form.get("description")
        producer.contact = form.get("contact")

        delivery.producers[producer_id] = producer
        delivery.persist()
        response.message(f"« {producer.name} » à bien été créé !")
        response.redirect = f"/produits/{delivery.id}/producteurs/{producer.id}"

    response.html(
        "products/edit_producer.html", {"delivery": delivery, "producer": producer}
    )


@app.route("/produits/{delivery_id}/producteurs/{producer_id}", methods=["GET", "POST"])
async def edit_producer(request, response, delivery_id, producer_id):
    delivery = Delivery.load(delivery_id)
    producer = delivery.producers.get(producer_id)
    if request.method == "POST":
        form = request.form
        producer.referent = form.get("referent")
        producer.referent_tel = form.get("referent_tel")
        producer.referent_name = form.get("referent_name")
        producer.description = form.get("description")
        producer.contact = form.get("contact")
        producer.practical_info = form.get("practical_info")
        delivery.producers[producer_id] = producer
        delivery.persist()

    response.html(
        "products/edit_producer.html",
        {
            "delivery": delivery,
            "producer": producer,
            "products": delivery.get_products_by(producer_id),
        },
    )


@app.route(
    "/produits/{delivery_id}/producteurs/{producer_id}/supprimer",
    methods=["GET", "POST"],
)
async def delete_producer(request, response, delivery_id, producer_id):
    # Delete the producer and all the related products.
    delivery = Delivery.load(delivery_id)
    producer = delivery.producers.get(producer_id)
    if request.method == "POST":
        delivery.producers.pop(producer_id)
        products = delivery.get_products_by(producer.id)
        for product in products:
            delivery.products.remove(product)
            for order in delivery.orders.values():
                order.products.pop(product.ref)
        delivery.persist()

        response.message(f"{producer.name} à bien été supprimé !")
        response.redirect = f"/produits/{delivery.id}"

    response.html(
        "products/delete_producer.html",
        {
            "delivery": delivery,
            "producer": producer,
            "products": delivery.get_products_by(producer.id),
        },
    )


@app.route(
    "/produits/{delivery_id}/producteurs/{producer_id}/valider-prix", methods=["GET"]
)
async def validate_producer_prices(request, response, delivery_id, producer_id):
    delivery = Delivery.load(delivery_id)
    producer = delivery.producers.get(producer_id)

    for product in delivery.products:
        if product.producer == producer_id:
            product.last_update = datetime.now()
    delivery.persist()

    response.message(
        f"Les prix ont été marqués comme OK pour « { producer.name } », merci !"
    )
    response.redirect = f"/produits/{delivery_id}/producteurs/{producer_id}"


@app.route("/produits/{delivery_id}/valider-prix", methods=["GET"])
async def mark_all_prices_as_ok(request, response, delivery_id):
    delivery = Delivery.load(delivery_id)
    delivery.validate_all_prices()
    delivery.persist()

    response.message(f"Les prix ont été marqués comme OK pour toute la distribution !")
    response.redirect = f"/produits/{delivery_id}"


@app.route(
    "/produits/{delivery_id}/producteurs/{producer_id}/produits/créer",
    methods=["GET", "POST"],
)
async def create_product(request, response, delivery_id, producer_id):
    delivery = Delivery.load(delivery_id)
    product = Product(name="", ref="", price=0)
    producer = delivery.producers.get(producer_id)

    if request.method == "POST":
        product.producer = producer_id
        form = request.form
        product.update_from_form(form)
        random_string = "".join(
            random.choices(string.ascii_lowercase + string.digits, k=8)
        )
        product.ref = slugify(
            f"{producer_id}-{product.name}-{product.unit}-{random_string}"
        )

        delivery.products.append(product)
        delivery.persist()
        response.message("Le produit à bien été créé")
        response.redirect = f"/produits/{delivery_id}/producteurs/{producer_id}"
        return

    response.html(
        "products/edit_product.html",
        {"delivery": delivery, "producer": producer, "product": product},
    )


@app.route(
    "/produits/{delivery_id}/producteurs/{producer_id}/produits/{product_ref}",
    methods=["GET", "POST"],
)
async def edit_product(request, response, delivery_id, producer_id, product_ref):
    delivery = Delivery.load(delivery_id)
    product = delivery.get_product(product_ref)
    producer = delivery.producers.get(producer_id)

    if request.method == "POST":
        form = request.form
        product.name = form.get("name")
        product.price = form.float("price")
        product.unit = form.get("unit")
        product.description = form.get("description")
        product.url = form.get("url", None)
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
        response.redirect = f"/produits/{delivery_id}/producteurs/{producer_id}"
        return

    response.html(
        "products/edit_product.html",
        {"delivery": delivery, "product": product, "producer": producer},
    )


@app.route(
    "/produits/{delivery_id}/producteurs/{producer_id}/produits/{product_ref}/supprimer",
    methods=["GET"],
)
async def delete_product(request, response, delivery_id, producer_id, product_ref):
    delivery = Delivery.load(delivery_id)
    product = delivery.delete_product(product_ref)
    delivery.persist()
    response.message(f"Le produit « { product.name } » à bien été supprimé.")
    response.redirect = f"/produits/{delivery_id}/producteurs/{producer_id}"


@app.route(
    "/produits/{delivery_id}/producteurs/{producer_id}/frais-de-livraison",
    methods=["GET", "POST"],
)
async def edit_shipping_price(request, response, delivery_id, producer_id):
    delivery = Delivery.load(delivery_id)
    producer = delivery.producers.get(producer_id)

    if request.method == "POST":
        form = request.form
        shipping = form.float("shipping")

        delivery.shipping[producer_id] = shipping
        delivery.persist()
        response.message("Les frais de livraison ont bien été enregistrés, merci !")
        response.redirect = f"/produits/{delivery_id}"
        return

    response.html(
        "products/edit_shipping_fees.html",
        {
            "delivery": delivery,
            "producer": producer,
            "shipping": delivery.shipping.get(producer_id, ""),
        },
    )


@app.route("/produits/{id}/copier", methods=["GET"])
async def copy_products(request, response, id):
    deliveries = Delivery.all()
    response.html("products/copy_products.html", {"deliveries": deliveries})


@app.route("/produits/{id}/copier", methods=["POST"])
async def copy_products_post(request, response, id):
    delivery = Delivery.load(id)
    to_copy = delivery.load(request.form.get("to_copy"))
    delivery.producers = to_copy.producers
    delivery.products = to_copy.products
    delivery.persist()
    response.redirect = f"/produits/{id}"
