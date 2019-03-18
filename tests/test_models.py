import pytest

from kaba import utils
from kaba.models import Delivery, Product, Person, Order, ProductOrder


def test_can_create_delivery():
    delivery = Delivery(
        producer="Andines", when=utils.utcnow(), order_before=utils.utcnow()
    )
    assert delivery.producer == "Andines"
    assert delivery.where == "Marché de la Briche"
    assert delivery.when.year == utils.utcnow().year
    assert delivery.id


def test_wrong_datetime_raise_valueerror():
    with pytest.raises(ValueError):
        Delivery(producer="Andines", order_before=utils.utcnow(), when="pouet")


def test_can_create_product():
    product = Product(name="Lait 1.5L", ref="123", price=1.5)
    assert product.ref == "123"
    assert product.price == 1.5


def test_can_create_delivery_with_products():
    delivery = Delivery(
        producer="Andines",
        when=utils.utcnow(),
        order_before=utils.utcnow(),
        products=[Product(name="Lait", ref="123", price=1.5)],
    )
    assert len(delivery.products) == 1
    assert delivery.products[0].ref == "123"


def test_can_add_product_to_delivery(delivery):
    assert not delivery.products
    delivery.products.append(Product(name="Chocolat", ref="choco", price=10))
    assert len(delivery.products) == 1


def test_can_create_person():
    person = Person(email="foo@bar.fr", first_name="Foo")
    assert person.email == "foo@bar.fr"
    assert person.first_name == "Foo"


def test_can_create_order_with_products():
    order = Order(products={"123": ProductOrder(wanted=2)})
    assert len(order.products) == 1
    assert order.products["123"].wanted == 2


def test_can_add_product_to_order():
    order = Order()
    assert len(order.products) == 0
    order.products["123"] = ProductOrder(wanted=2)
    assert order.products["123"].wanted == 2


def test_can_persist_delivery(delivery):
    delivery.persist()


def test_can_load_delivery(delivery):
    delivery.producer = "Corto"
    delivery.persist()
    loaded = Delivery.load(delivery.id)
    assert loaded.producer == "Corto"
