import csv
from zipfile import BadZipFile

from openpyxl import load_workbook, Workbook

from .models import Product


PRODUCT_FIELDS = {"ref", "name", "price"}


def products_from_xlsx(delivery, data):
    if not isinstance(data, Workbook):
        try:
            data = load_workbook(data)
        except BadZipFile:
            raise ValueError("Impossible de lire le fichier")
    rows = list(data.active.values)
    if not rows:
        raise ValueError
    headers = rows[0]
    if not set(headers) >= PRODUCT_FIELDS:
        raise ValueError("Colonnes obligatoires: name, ref, price")
    delivery.products = []
    for row in rows[1:]:
        raw = {k: v for k, v in dict(zip(headers, row)).items() if v}
        try:
            delivery.products.append(Product(**raw))
        except TypeError as e:
            raise ValueError(f"Erreur durant l'importation de {raw['ref']}")
    delivery.persist()


def products_from_csv(delivery, data):
    reader = csv.DictReader(data.splitlines(), delimiter=";")
    if not set(reader.fieldnames) >= PRODUCT_FIELDS:
        raise ValueError("Colonnes obligatoires: name, ref, price. "
                         "Assurez-vous que le délimiteur soit bien «;»")
    delivery.products = []
    for row in reader:
        delivery.products.append(Product(**row))
    delivery.persist()
