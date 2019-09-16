import csv
import functools

from zipfile import BadZipFile

from openpyxl import load_workbook, Workbook

from .models import Product, Producer


PRODUCT_FIELDS = {"ref", "name", "price"}
PRODUCER_FIELDS = {"id"}


def append_list(field, item):
    field.append(item)


def append_dict(field, item):
    field[item.id] = item


def items_from_xlsx(data, items, model_class, required_fields, append_method):
    if not data:
        raise ValueError
    headers = data[0]
    if not set(headers) >= required_fields:
        raise ValueError(f"Colonnes obligatoires: {', '.join(required_fields)}.")
    for row in data[1:]:
        raw = {k: v for k, v in dict(zip(headers, row)).items() if v}
        try:
            append_method(items, model_class(**raw))
        except TypeError as e:
            raise ValueError(f"Erreur durant l'importation de {raw['ref']}")
    return items


def products_and_producers_from_xlsx(delivery, data):
    if not isinstance(data, Workbook):
        try:
            data = load_workbook(data)
        except BadZipFile:
            raise ValueError("Impossible de lire le fichier")

    sheet_names = data.get_sheet_names()
    if len(sheet_names) != 2:
        raise ValueError("Le fichier doit comporter deux onglets.")
    # First, get the products data from the first tab.
    products_sheet = data.get_sheet_by_name(sheet_names[0])
    delivery.products = items_from_xlsx(list(products_sheet.values), [], Product, PRODUCT_FIELDS, append_list)
    
    # Then import producers info
    producers_sheet = data.get_sheet_by_name(sheet_names[1])
    delivery.producers = items_from_xlsx(list(producers_sheet.values), {}, Producer, PRODUCER_FIELDS, append_dict)
    delivery.persist()