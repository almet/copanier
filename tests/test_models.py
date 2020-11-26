from datetime import datetime, timedelta

import pytest

from copanier import config
from copanier.models import (
    Delivery,
    Product,
    Person,
    Order,
    ProductOrder,
    Groups,
    Group,
)


now = datetime.now


def test_can_create_delivery():
    delivery = Delivery(
        name="Andines",
        from_date=now(),
        to_date=now(),
        order_before=now(),
        contact="some@one.to",
    )
    assert delivery.name == "Andines"
    assert delivery.where == "Marché de la Briche"
    assert delivery.from_date.year == now().year
    assert not delivery.id


def test_wrong_datetime_raise_valueerror():
    with pytest.raises(ValueError):
        Delivery(
            name="Andines",
            order_before=now(),
            to_date=now(),
            from_date="pouet",
            contact="some@one.to",
        )


def test_delivery_is_open_when_order_before_is_in_the_future(delivery):
    delivery.order_before = now() + timedelta(hours=1)
    assert delivery.is_open
    delivery.order_before = now() - timedelta(days=1)
    assert not delivery.is_open
    # We don't take the hour into account
    delivery.order_before = now() - timedelta(hours=1)
    # assert delivery.is_open


def test_delivery_status(delivery):
    delivery.order_before = now() + timedelta(hours=1)
    assert delivery.status == delivery.OPEN
    delivery.order_before = now() - timedelta(days=1)
    assert delivery.status == delivery.CLOSED


def test_can_create_product():
    product = Product(name="Lait 1.5L", ref="123", price=1.5)
    assert product.ref == "123"
    assert product.price == 1.5


def test_can_create_delivery_with_products():
    delivery = Delivery(
        name="Andines",
        from_date=now(),
        to_date=now(),
        order_before=now(),
        products=[Product(name="Lait", ref="123", price=1.5)],
        contact="some@one.to",
    )
    assert len(delivery.products) == 1
    assert delivery.products[0].ref == "123"


def test_can_add_product_to_delivery(delivery):
    delivery.products = []
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


def test_order_has_adjustments():
    order = Order()
    assert not order.has_adjustments
    order.products["123"] = ProductOrder(wanted=2)
    assert not order.has_adjustments
    order.products["123"] = ProductOrder(wanted=2, adjustment=1)
    assert order.has_adjustments


def test_order_total(delivery):
    delivery.products = [Product(name="Lait", ref="123", price=1.5)]
    order = Order()
    assert order.total(delivery.products, delivery) == 0
    order.products["123"] = ProductOrder(wanted=2)
    assert order.total(delivery.products, delivery) == 3
    order.products["unknown"] = ProductOrder(wanted=2)
    assert order.total(delivery.products, delivery) == 3


def test_can_persist_delivery(delivery):
    with pytest.raises(AssertionError):
        delivery.path
    assert not delivery.id
    delivery.persist()
    assert delivery.id
    assert delivery.path.exists()


def test_can_load_delivery(delivery):
    delivery.name = "Corto"
    delivery.persist()
    loaded = Delivery.load(delivery.id)
    assert loaded.name == "Corto"


def test_person_is_staff_if_email_is_in_config(monkeypatch):
    monkeypatch.setattr(config, "STAFF", ["foo@bar.fr"])
    person = Person(email="foo@bar.fr")
    assert person.is_staff
    person = Person(email="foo@bar.org")
    assert not person.is_staff


def test_person_is_staff_if_no_staff_in_config(monkeypatch):
    monkeypatch.setattr(config, "STAFF", [])
    person = Person(email="foo@bar.fr")
    assert person.is_staff


def test_productorder_quantity():
    choice = ProductOrder(wanted=3)
    assert choice.wanted == 3
    assert choice.quantity == 3
    choice = ProductOrder(wanted=3, adjustment=2)
    assert choice.quantity == 5
    choice = ProductOrder(wanted=3, adjustment=-1)
    assert choice.quantity == 2


def test_group_management():
    ndp = Group(
        id="passage-creuse", name="Nid de poules", members=["someone@domain.tld"]
    )
    assert ndp.id == "passage-creuse"
    assert ndp.name == "Nid de poules"
    assert len(ndp.members) == 1
    groups = Groups.load()
    groups.persist()

    groups.add_group(ndp)
    groups.add_user("simon@tld", ndp.id)
    assert "simon@tld" in groups.groups[ndp.id].members

    ladouce = Group(id="la-lointaine", name="La douce", members=[])
    groups.add_group(ladouce)
    groups.add_user("simon@tld", ladouce.id)
    assert "simon@tld" in groups.groups[ladouce.id].members
    assert "simon@tld" not in groups.groups[ndp.id].members

