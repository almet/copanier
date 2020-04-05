from slugify import slugify
from .core import app
from ..models import Delivery, Product, Producer
from .. import utils


@app.route("/distribution/{id}/produits")
@app.route("/distribution/{id}/produits.pdf")
async def list_products(request, response, id):
    delivery = Delivery.load(id)
    template_name = "products/list.html"
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


@app.route("/distribution/{delivery_id}/{producer_id}/éditer", methods=["GET", "POST"])
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
        delivery.producers[producer_id] = producer
        delivery.persist()

    response.html(
        "products/edit_producer.html",
        {
            "delivery": delivery,
            "producer": producer,
            "products": delivery.get_products_by(producer.id),
        },
    )


@app.route(
    "/distribution/{delivery_id}/{producer_id}/supprimer", methods=["GET", "POST"]
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
        response.redirect = f"/distribution/{delivery.id}/produits"

    response.html(
        "products/delete_producer.html",
        {
            "delivery": delivery,
            "producer": producer,
            "products": delivery.get_products_by(producer.id),
        },
    )


@app.route("/distribution/{delivery_id}/{producer_id}/frais", methods=["GET", "POST"])
async def handle_shipping_fees(request, response, delivery_id, producer_id):
    delivery = Delivery.load(delivery_id)
    producer = delivery.producers.get(producer_id)
    if request.method == "POST":
        form = request.form
        producer.referent = form.get("referent")
        producer.referent_tel = form.get("referent_tel")
        producer.referent_name = form.get("referent_name")
        producer.description = form.get("description")
        producer.contact = form.get("contact")
        delivery.producers[producer_id] = producer
        delivery.persist()

    response.html(
        "products/shipping_fees.html", {"delivery": delivery, "producer": producer}
    )


@app.route("/producteurices/créer/{delivery_id}", methods=["GET", "POST"])
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
        response.redirect = f"/distribution/{delivery.id}/{producer.id}/éditer"

    response.html(
        "products/edit_producer.html",
        {"delivery": delivery, "producer": producer or None},
    )


@app.route(
    "/distribution/{delivery_id}/{producer_id}/produit/{product_ref}/éditer",
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
        response.redirect = f"/distribution/{delivery_id}/{producer_id}/éditer"
        return

    response.html(
        "products/edit.html",
        {"delivery": delivery, "product": product, "producer": producer},
    )


@app.route(
    "/distribution/{delivery_id}/{producer_id}/{product_ref}/supprimer", methods=["GET"]
)
async def delete_product(request, response, delivery_id, producer_id, product_ref):
    delivery = Delivery.load(delivery_id)
    product = delivery.delete_product(product_ref)
    delivery.persist()
    response.message(f"Le produit « { product.name } » à bien été supprimé.")
    response.redirect = f"/distribution/{delivery_id}/{producer_id}/éditer"


@app.route(
    "/distribution/{delivery_id}/{producer_id}/ajouter-produit", methods=["GET", "POST"]
)
async def create_product(request, response, delivery_id, producer_id):
    delivery = Delivery.load(delivery_id)
    product = Product(name="", ref="", price=0)
    producer = delivery.producers.get(producer_id)

    if request.method == "POST":
        product.producer = producer_id
        form = request.form
        product.update_from_form(form)
        product.ref = slugify(f"{producer_id}-{product.name}-{product.unit}")

        delivery.products.append(product)
        delivery.persist()
        response.message("Le produit à bien été créé")
        response.redirect = f"/distribution/{delivery_id}/{producer_id}/éditer"
        return

    response.html(
        "products/edit.html",
        {"delivery": delivery, "producer": producer, "product": product},
    )


@app.route("/distribution/{id}/copier", methods=["GET"])
async def copy_products(request, response, id):
    deliveries = Delivery.all()
    response.html("delivery/copy.html", {"deliveries": deliveries})


@app.route("/distribution/{id}/copier", methods=["POST"])
async def copy_products(request, response, id):
    delivery = Delivery.load(id)
    to_copy = delivery.load(request.form.get("to_copy"))
    delivery.producers = to_copy.producers
    delivery.products = to_copy.products
    delivery.persist()
    response.redirect = f"/distribution/{id}"
