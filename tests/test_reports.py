from io import BytesIO

from openpyxl import load_workbook

from copanier import reports
from copanier.models import Order, Product, ProductOrder


def test_summary_report(delivery, yaourt, fromage):
    delivery.products[0].packing = 6
    delivery.products.append(yaourt)
    delivery.products.append(fromage)
    delivery.orders["fractals-brocoli"] = Order(
        products={"lait": ProductOrder(wanted=1), "yaourt": ProductOrder(wanted=4)}
    )
    delivery.persist()
    wb = load_workbook(filename=BytesIO(reports.summary(delivery)))
    assert list(wb.active.values) == [
        ("ref", "produit", "prix unitaire", "quantité commandée", "unité", "total"),
        ("lait", "Lait", 1.5, 1, None, 1.5),
        ("yaourt", "Yaourt", 3.5, 4, "pot 125ml", 14),
        (None, None, None, None, "Total", 15.5),
    ]
