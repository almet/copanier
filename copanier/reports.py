from dataclasses import fields as get_fields

from openpyxl import Workbook
from openpyxl.writer.excel import save_virtual_workbook

from .models import Product


def summary(delivery):
    wb = Workbook()
    ws = wb.active
    ws.title = f"{delivery.producer} {delivery.from_date.date()}"
    headers = [
        "ref",
        "produit",
        "prix unitaire",
        "quantité commandée",
        "unité",
        "total",
    ]
    ws.append(headers)
    for product in delivery.products:
        wanted = delivery.product_wanted(product)
        if not wanted:
            continue
        ws.append(
            [
                product.ref,
                str(product),
                product.price,
                wanted,
                product.unit,
                round(product.price * wanted, 2),
            ]
        )
    ws.append(["", "", "", "", "Total", delivery.total])
    return save_virtual_workbook(wb)


def full(delivery):
    wb = Workbook()
    ws = wb.active
    ws.title = f"{delivery.producer} {delivery.from_date.date()}"
    headers = ["ref", "produit", "prix"] + [e for e in delivery.orders] + ["total"]
    ws.append(headers)
    for product in delivery.products:
        row = [product.ref, str(product), product.price]
        for order in delivery.orders.values():
            wanted = order.products.get(product.ref)
            row.append(wanted.quantity if wanted else 0)
        row.append(delivery.product_wanted(product))
        ws.append(row)
    footer = (
        ["Total", "", ""]
        + [round(o.total(delivery.products),2) for o in delivery.orders.values()]
        + [round(delivery.total, 2)]
    )
    ws.append(footer)
    return save_virtual_workbook(wb)


def products(delivery):
    wb = Workbook()
    ws = wb.active
    ws.title = f"{delivery.producer} produits"
    fields = [f.name for f in get_fields(Product)]
    ws.append(fields)
    for product in delivery.products:
        ws.append([getattr(product, field) for field in fields])
    return save_virtual_workbook(wb)


def balance(delivery):
    wb = Workbook()
    ws = wb.active
    ws.title = f"Solde {delivery.producer}"
    ws.append(["Adhérent", "Montant", "Payé"])
    for email, order in delivery.orders.items():
        ws.append(
            [email, order.total(delivery.products), "oui" if order.paid else "non"]
        )
    return save_virtual_workbook(wb)
