from datetime import datetime, timedelta
from io import BytesIO

import pytest
from openpyxl import load_workbook
from pyquery import PyQuery as pq

from copanier.views.core import url
from copanier.models import Delivery, Order, ProductOrder, Product

pytestmark = pytest.mark.asyncio


async def test_home_redirects_to_group_if_needed(client):
    client.login(email="new@example.org")
    resp = await client.get("/")
    assert resp.status == 302
    assert resp.headers["Location"] == url("/groupes")


async def test_empty_home(client, delivery, groups):
    groups.persist()
    resp = await client.get("/")
    assert resp.status == 200


async def test_home_should_list_active_delivery(client, delivery, groups):
    groups.persist()
    delivery.persist()
    resp = await client.get("/")
    assert resp.status == 200
    assert delivery.name in resp.body.decode()


async def test_home_should_redirect_to_login_if_not_logged(client):
    client.logout()
    resp = await client.get("/")
    assert resp.status == 302
    assert resp.headers["Location"] == url("/connexion?next=" + url("/"))


async def test_create_delivery(client):
    assert not list(Delivery.all())
    body = {
        "name": "Andines",
        "where": "Marché de la Briche",
        "date": "2019-02-23",
        "from_time": "18:30:00",
        "to_time": "20:00:00",
        "order_before": "2019-02-12",
        "contact": "lucky@you.me",
    }
    resp = await client.post("/distribution", body=body)
    assert resp.status == 302
    assert len(list(Delivery.all())) == 1
    delivery = list(Delivery.all())[0]
    assert delivery.name == "Andines"
    assert delivery.from_date.year == 2019
    assert delivery.from_date.hour == 18
    assert delivery.from_date.minute == 30
    assert delivery.to_date.year == 2019
    assert delivery.to_date.hour == 20
    assert delivery.to_date.minute == 0


async def test_place_order_with_session(client, delivery):
    delivery.persist()
    body = {"wanted:lait": "3"}
    resp = await client.post(f"/distribution/{delivery.id}/commander", body=body)
    assert resp.status == 302
    delivery = Delivery.load(id=delivery.id)
    assert "fractal-brocolis" in delivery.orders.keys()
    assert delivery.orders["fractal-brocolis"].products["lait"].wanted == 3


async def test_place_empty_order(client, delivery):
    delivery.persist()
    resp = await client.post(f"/distribution/{delivery.id}/commander", body={})
    assert resp.status == 302
    delivery = Delivery.load(id=delivery.id)
    assert not delivery.orders


async def test_place_empty_order_should_delete_previous(client, delivery):
    delivery.orders["fractal-brocolis"] = Order(
        products={"lait": ProductOrder(wanted=1)}
    )
    delivery.persist()
    resp = await client.post(f"/distribution/{delivery.id}/commander", body={})
    assert resp.status == 302
    delivery = Delivery.load(delivery.id)
    assert not delivery.orders


async def test_place_order_with_empty_string(client, delivery):
    delivery.persist()
    body = {"wanted:lait": ""}  # User deleted the field value.
    resp = await client.post(f"/distribution/{delivery.id}/commander", body=body)
    assert resp.status == 302
    delivery = Delivery.load(id=delivery.id)
    assert not delivery.orders


async def test_get_place_order_if_not_adjustable(client, delivery, monkeypatch):
    monkeypatch.setattr("copanier.config.STAFF", ["someone@else.org"])
    delivery.order_before = datetime.now() - timedelta(days=1)
    delivery.orders["fractal-brocolis"] = Order(
        products={"lait": ProductOrder(wanted=1)}
    )
    delivery.persist()
    assert delivery.status == delivery.CLOSED
    resp = await client.get(f"/distribution/{delivery.id}/commander")
    doc = pq(resp.body)
    assert doc('[name="wanted:lait"]').attr("readonly")
    assert not doc('[name="adjustment:lait"]')
    assert not doc('input[type="submit"]')


async def test_get_place_order_with_adjustment_status(client, delivery, yaourt, fromage):
    resp = await client.get(f"/distribution/{delivery.id}/commander")
    doc = pq(resp.body)
    assert not doc('[name="wanted:lait"]').attr("readonly")
    assert not doc('[name="adjustment:lait"]')
    delivery.order_before = datetime.now() - timedelta(days=1)
    delivery.products[0].packing = 6
    delivery.products.append(yaourt)
    delivery.products.append(fromage)
    delivery.orders["fractal-brocolis"] = Order(
        products={
            "lait": ProductOrder(wanted=1),
            "yaourt": ProductOrder(wanted=4)
        }
    )
    delivery.persist()
    assert delivery.status == delivery.ADJUSTMENT
    resp = await client.get(f"/distribution/{delivery.id}/commander")
    doc = pq(resp.body)
    assert doc('[name="wanted:lait"]').attr("readonly")
    assert doc('[name="adjustment:lait"]')
    assert not doc('[name="adjustment:lait"]').attr("readonly")
    assert doc('[name="adjustment:lait"]').attr("min") == "-1"
    assert doc('[name="wanted:yaourt"]').attr("readonly")
    assert doc('[name="adjustment:yaourt"]')
    # Already adjusted.
    assert doc('[name="adjustment:yaourt"]').attr("readonly")
    assert doc('[name="adjustment:fromage"]')
    # Needs no adjustment.
    assert doc('[name="adjustment:fromage"]').attr("readonly")
    assert doc('input[type="submit"]')


async def test_cannot_place_order_on_closed_delivery(client, delivery, monkeypatch):
    monkeypatch.setattr("copanier.config.STAFF", ["someone@else.org"])
    delivery.order_before = datetime.now() - timedelta(days=1)
    delivery.persist()
    body = {"wanted:lait": "3"}
    resp = await client.post(f"/distribution/{delivery.id}/commander", body=body)
    assert resp.status == 302
    delivery = Delivery.load(id=delivery.id)
    assert not delivery.orders


async def test_get_adjust_product(client, delivery):
    delivery.order_before = datetime.now() - timedelta(days=1)
    delivery.products[0].packing = 6
    delivery.orders["fractal-brocolis"] = Order(
        products={"lait": ProductOrder(wanted=2, adjustment=1)}
    )
    delivery.persist()
    assert delivery.status == delivery.ADJUSTMENT
    resp = await client.get(f"/distribution/{delivery.id}/ajuster/lait")
    doc = pq(resp.body)
    assert doc('[name="fractal-brocolis"]')
    assert doc('[name="fractal-brocolis"]').attr("value") == "1"


async def test_post_adjust_product(client, delivery):
    delivery.order_before = datetime.now() - timedelta(days=1)
    delivery.products[0].packing = 6
    delivery.orders["fractal-brocolis"] = Order(products={"lait": ProductOrder(wanted=2)})
    delivery.persist()
    assert delivery.status == delivery.ADJUSTMENT
    body = {"fractal-brocolis": "1"}
    resp = await client.post(f"/distribution/{delivery.id}/ajuster/lait", body=body)
    assert resp.status == 302
    delivery = Delivery.load(id=delivery.id)
    assert delivery.orders["fractal-brocolis"].products["lait"].wanted == 2
    assert delivery.orders["fractal-brocolis"].products["lait"].adjustment == 1


async def test_only_staff_can_adjust_product(client, delivery, monkeypatch):
    delivery.order_before = datetime.now() - timedelta(days=1)
    delivery.products[0].packing = 6
    delivery.orders["fractal-brocolis"] = Order(products={"lait": ProductOrder(wanted=2)})
    delivery.persist()
    monkeypatch.setattr("copanier.config.STAFF", ["someone@else.org"])
    resp = await client.get(f"/distribution/{delivery.id}/ajuster/lait")
    assert resp.status == 302
    body = {"fractal-brocolis": "1"}
    resp = await client.post(f"/distribution/{delivery.id}/ajuster/lait", body=body)
    assert resp.status == 302
    delivery = Delivery.load(id=delivery.id)
    assert delivery.orders["fractal-brocolis"].products["lait"].wanted == 2
    assert delivery.orders["fractal-brocolis"].products["lait"].adjustment == 0


async def test_export_products(client, delivery):
    delivery.persist()
    resp = await client.get(f"/distribution/{delivery.id}/exporter")
    wb = load_workbook(filename=BytesIO(resp.body))
    assert list(wb.active.values) == [
        (
            'name',
            'ref',
            'price',
            'last_update',
            'unit',
            'description',
            'packing',
            'producer',
            'rupture'
        ),
        ("Lait", "lait", 1.5, delivery.products[0].last_update, None, None, None, "ferme-du-coin", None),
    ]