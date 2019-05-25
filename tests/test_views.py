from datetime import datetime, timedelta
from io import BytesIO

import pytest
from openpyxl import load_workbook
from pyquery import PyQuery as pq

from copanier.models import Delivery, Order, ProductOrder, Product

pytestmark = pytest.mark.asyncio


async def test_empty_home(client):
    resp = await client.get("/")
    assert resp.status == 200


async def test_home_should_list_active_delivery(client, delivery):
    delivery.persist()
    resp = await client.get("/")
    assert resp.status == 200
    assert delivery.producer in resp.body.decode()


async def test_home_should_redirect_to_login_if_not_logged(client):
    client.logout()
    resp = await client.get("/")
    assert resp.status == 302
    assert resp.headers["Location"] == "/sésame?next=/"


async def test_create_delivery(client):
    assert not list(Delivery.all())
    body = {
        "producer": "Andines",
        "where": "Marché de la Briche",
        "date": "2019-02-23",
        "from_time": "18:30:00",
        "to_time": "20:00:00",
        "order_before": "2019-02-12",
        "contact": "lucky@you.me",
    }
    resp = await client.post("/livraison", body=body)
    assert resp.status == 302
    assert len(list(Delivery.all())) == 1
    delivery = list(Delivery.all())[0]
    assert delivery.producer == "Andines"
    assert delivery.from_date.year == 2019
    assert delivery.from_date.hour == 18
    assert delivery.from_date.minute == 30
    assert delivery.to_date.year == 2019
    assert delivery.to_date.hour == 20
    assert delivery.to_date.minute == 0


async def test_place_order_with_session(client, delivery):
    delivery.persist()
    body = {"wanted:123": "3"}
    resp = await client.post(f"/livraison/{delivery.id}/commander", body=body)
    assert resp.status == 302
    delivery = Delivery.load(id=delivery.id)
    assert delivery.orders["foo@bar.org"]
    assert delivery.orders["foo@bar.org"].products["123"].wanted == 3


async def test_place_empty_order(client, delivery):
    delivery.persist()
    resp = await client.post(f"/livraison/{delivery.id}/commander", body={})
    assert resp.status == 302
    delivery = Delivery.load(id=delivery.id)
    assert not delivery.orders


async def test_place_empty_order_should_delete_previous(client, delivery):
    delivery.orders["foo@bar.org"] = Order(products={"123": ProductOrder(wanted=1)})
    delivery.persist()
    resp = await client.post(f"/livraison/{delivery.id}/commander", body={})
    assert resp.status == 302
    delivery = Delivery.load(delivery.id)
    assert not delivery.orders


async def test_place_order_with_empty_string(client, delivery):
    delivery.persist()
    body = {"wanted:123": ""}  # User deleted the field value.
    resp = await client.post(f"/livraison/{delivery.id}/commander", body=body)
    assert resp.status == 302
    delivery = Delivery.load(id=delivery.id)
    assert not delivery.orders


async def test_change_paid_status_when_placing_order(client, delivery):
    delivery.persist()
    body = {"wanted:123": "3", "paid": 1}
    resp = await client.post(f"/livraison/{delivery.id}/commander", body=body)
    assert resp.status == 302
    delivery = Delivery.load(id=delivery.id)
    assert delivery.orders["foo@bar.org"]
    assert delivery.orders["foo@bar.org"].paid is True


async def test_get_place_order_with_closed_delivery(client, delivery, monkeypatch):
    monkeypatch.setattr("copanier.config.STAFF", ["someone@else.org"])
    delivery.order_before = datetime.now() - timedelta(days=1)
    delivery.orders["foo@bar.org"] = Order(products={"123": ProductOrder(wanted=1)})
    delivery.persist()
    assert delivery.status == delivery.CLOSED
    resp = await client.get(f"/livraison/{delivery.id}/commander")
    doc = pq(resp.body)
    assert doc('[name="wanted:123"]').attr("readonly")
    assert not doc('[name="adjustment:123"]')
    assert not doc('input[type="submit"]')


async def test_get_place_order_with_adjustment_status(client, delivery):
    resp = await client.get(f"/livraison/{delivery.id}/commander")
    doc = pq(resp.body)
    assert not doc('[name="wanted:123"]').attr("readonly")
    assert not doc('[name="adjustment:123"]')
    delivery.order_before = datetime.now() - timedelta(days=1)
    delivery.products[0].packing = 6
    delivery.products.append(Product(ref="456", name="yaourt", price="3.5", packing=4))
    delivery.products.append(Product(ref="789", name="fromage", price="9.2"))
    delivery.orders["foo@bar.org"] = Order(
        products={"123": ProductOrder(wanted=1), "456": ProductOrder(wanted=4)}
    )
    delivery.persist()
    assert delivery.status == delivery.ADJUSTMENT
    resp = await client.get(f"/livraison/{delivery.id}/commander")
    doc = pq(resp.body)
    assert doc('[name="wanted:123"]').attr("readonly")
    assert doc('[name="adjustment:123"]')
    assert not doc('[name="adjustment:123"]').attr("readonly")
    assert doc('[name="adjustment:123"]').attr("min") == "-1"
    assert doc('[name="wanted:456"]').attr("readonly")
    assert doc('[name="adjustment:456"]')
    # Already adjusted.
    assert doc('[name="adjustment:456"]').attr("readonly")
    assert doc('[name="adjustment:789"]')
    # Needs no adjustment.
    assert doc('[name="adjustment:789"]').attr("readonly")
    assert doc('input[type="submit"]')


async def test_get_place_order_with_closed_delivery_but_adjustments(client, delivery):
    delivery.order_before = datetime.now() - timedelta(days=1)
    delivery.orders["foo@bar.org"] = Order(
        products={"123": ProductOrder(wanted=1, adjustment=1)}
    )
    delivery.persist()
    assert delivery.status == delivery.CLOSED
    resp = await client.get(f"/livraison/{delivery.id}/commander")
    doc = pq(resp.body)
    assert doc('[name="wanted:123"]').attr("readonly")
    assert doc('[name="adjustment:123"]')


async def test_get_place_order_with_closed_delivery_but_force(client, delivery):
    delivery.order_before = datetime.now() - timedelta(days=1)
    delivery.orders["foo@bar.org"] = Order(products={"123": ProductOrder(wanted=1)})
    delivery.persist()
    assert delivery.status == delivery.CLOSED
    resp = await client.get(f"/livraison/{delivery.id}/commander")
    doc = pq(resp.body)
    assert doc('[name="wanted:123"]').attr("readonly") is not None
    assert not doc('[name="adjustment:123"]')
    resp = await client.get(f"/livraison/{delivery.id}/commander?adjust")
    doc = pq(resp.body)
    assert doc('[name="wanted:123"]').attr("readonly") is not None
    assert doc('[name="adjustment:123"]')


async def test_cannot_place_order_on_closed_delivery(client, delivery, monkeypatch):
    monkeypatch.setattr("copanier.config.STAFF", ["someone@else.org"])
    delivery.order_before = datetime.now() - timedelta(days=1)
    delivery.persist()
    body = {"wanted:123": "3"}
    resp = await client.post(f"/livraison/{delivery.id}/commander", body=body)
    assert resp.status == 302
    delivery = Delivery.load(id=delivery.id)
    assert not delivery.orders


async def test_get_adjust_product(client, delivery):
    delivery.order_before = datetime.now() - timedelta(days=1)
    delivery.products[0].packing = 6
    delivery.orders["foo@bar.org"] = Order(
        products={"123": ProductOrder(wanted=2, adjustment=1)}
    )
    delivery.persist()
    assert delivery.status == delivery.ADJUSTMENT
    resp = await client.get(f"/livraison/{delivery.id}/ajuster/123")
    doc = pq(resp.body)
    assert doc('[name="foo@bar.org"]')
    assert doc('[name="foo@bar.org"]').attr("value") == "1"


async def test_post_adjust_product(client, delivery):
    delivery.order_before = datetime.now() - timedelta(days=1)
    delivery.products[0].packing = 6
    delivery.orders["foo@bar.org"] = Order(products={"123": ProductOrder(wanted=2)})
    delivery.persist()
    assert delivery.status == delivery.ADJUSTMENT
    body = {"foo@bar.org": "1"}
    resp = await client.post(f"/livraison/{delivery.id}/ajuster/123", body=body)
    assert resp.status == 302
    delivery = Delivery.load(id=delivery.id)
    assert delivery.orders["foo@bar.org"].products["123"].wanted == 2
    assert delivery.orders["foo@bar.org"].products["123"].adjustment == 1


async def test_only_staff_can_adjust_product(client, delivery, monkeypatch):
    delivery.order_before = datetime.now() - timedelta(days=1)
    delivery.products[0].packing = 6
    delivery.orders["foo@bar.org"] = Order(products={"123": ProductOrder(wanted=2)})
    delivery.persist()
    monkeypatch.setattr("copanier.config.STAFF", ["someone@else.org"])
    resp = await client.get(f"/livraison/{delivery.id}/ajuster/123")
    assert resp.status == 302
    body = {"foo@bar.org": "1"}
    resp = await client.post(f"/livraison/{delivery.id}/ajuster/123", body=body)
    assert resp.status == 302
    delivery = Delivery.load(id=delivery.id)
    assert delivery.orders["foo@bar.org"].products["123"].wanted == 2
    assert delivery.orders["foo@bar.org"].products["123"].adjustment == 0


async def test_get_delivery_balance(client, delivery):
    delivery.from_date = datetime.now() - timedelta(days=1)
    delivery.orders["foo@bar.org"] = Order(products={"123": ProductOrder(wanted=2)})
    delivery.persist()
    resp = await client.get(f"/livraison/{delivery.id}/solde")
    doc = pq(resp.body)
    assert doc('[name="foo@bar.org"]')
    assert not doc('[name="foo@bar.org"]').attr("checked")
    delivery.orders["foo@bar.org"] = Order(
        products={"123": ProductOrder(wanted=2)}, paid=True
    )
    delivery.persist()
    resp = await client.get(f"/livraison/{delivery.id}/solde")
    doc = pq(resp.body)
    assert doc('[name="foo@bar.org"]').attr("checked")


async def test_post_delivery_balance(client, delivery):
    delivery.order_before = datetime.now() - timedelta(days=1)
    delivery.orders["foo@bar.org"] = Order(products={"123": ProductOrder(wanted=2)})
    delivery.persist()
    body = {"foo@bar.org": "on"}
    resp = await client.post(f"/livraison/{delivery.id}/solde", body=body)
    assert resp.status == 302
    delivery = Delivery.load(id=delivery.id)
    assert delivery.orders["foo@bar.org"].paid is True


async def test_export_products(client, delivery):
    delivery.persist()
    resp = await client.get(f"/livraison/{delivery.id}/exporter/produits")
    wb = load_workbook(filename=BytesIO(resp.body))
    assert list(wb.active.values) == [
        ("name", "ref", "price", "unit", "description", "url", "img", "packing"),
        ("Lait", "123", 1.5, None, None, None, None, None),
    ]
