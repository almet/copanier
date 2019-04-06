from io import BytesIO

import pytest
from openpyxl import Workbook

from copanier import imports
from copanier.models import Product, Delivery


@pytest.fixture
def workbook():
    def _(rows, headers=["ref", "name", "price"]):
        wb = Workbook()
        ws = wb.active
        ws.append(headers)
        for row in rows:
            ws.append(row)
        return wb

    return _


def test_mandatory_headers_with_xlsx(delivery, workbook):
    with pytest.raises(ValueError):
        imports.products_from_xlsx(
            delivery,
            workbook([("123", "Chocolat", "2.3")], headers=["ref", "nom", "prix"]),
        )


def test_bad_xlsx_file(delivery, workbook):
    with pytest.raises(ValueError):
        imports.products_from_xlsx(delivery, BytesIO(b"pouet"))


def test_simple_xlsx_import(delivery, workbook):
    delivery.persist()
    assert delivery.products == [Product(ref="123", name="Lait", price=1.5)]
    imports.products_from_xlsx(delivery, workbook([("123", "Lait cru", 1.3)]))
    assert Delivery.load(delivery.id).products == [
        Product(ref="123", name="Lait cru", price=1.3)
    ]


def test_simple_xlsx_import_invalid_price(delivery, workbook):
    delivery.persist()
    assert delivery.products == [Product(ref="123", name="Lait", price=1.5)]
    with pytest.raises(ValueError):
        imports.products_from_xlsx(delivery, workbook([("123", "Lait cru", "invalid")]))
    assert Delivery.load(delivery.id).products == [
        Product(ref="123", name="Lait", price=1.5)
    ]


def test_mandatory_headers_with_csv(delivery):
    with pytest.raises(ValueError):
        imports.products_from_csv(delivery, "ref;nom;prix\n123;Chocolat;2.3")


def test_bad_csv_file(delivery):
    with pytest.raises(ValueError):
        imports.products_from_csv(delivery, "pouet")


def test_simple_csv_import(delivery):
    delivery.persist()
    assert delivery.products == [Product(ref="123", name="Lait", price=1.5)]
    imports.products_from_csv(delivery, "ref;name;price\n123;Lait cru;1.3")
    assert Delivery.load(delivery.id).products == [
        Product(ref="123", name="Lait cru", price=1.3)
    ]


def test_simple_csv_import_invalid_price(delivery):
    delivery.persist()
    assert delivery.products == [Product(ref="123", name="Lait", price=1.5)]
    with pytest.raises(ValueError):
        imports.products_from_csv(delivery, "ref;name;price\n123;Lait cru;invalid")
    assert Delivery.load(delivery.id).products == [
        Product(ref="123", name="Lait", price=1.5)
    ]
