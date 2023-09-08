import inspect
import threading
import uuid
from collections import Counter
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict

import yaml

from . import config


def demo_mode_enabled():
    return getattr(config, "DEMO_MODE", False)


class DoesNotExist(ValueError):
    pass


def datetime_field(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, int):
        return datetime.fromtimestamp(value)
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise ValueError


def price_field(value):
    if isinstance(value, str):
        value = value.replace(",", ".").replace("€", "").strip()
    return float(value)


@dataclass
class Base:
    @classmethod
    def create(cls, data=None, **kwargs):
        if isinstance(data, Base):
            return data
        return cls(**(data or kwargs))

    def __post_init__(self):
        for name, field_ in self.__dataclass_fields__.items():
            value = getattr(self, name)
            type_ = field_.type
            # Do not recast our classes.
            if not isinstance(value, Base) and value is not None:
                try:
                    setattr(self, name, self.cast(type_, value))
                except (TypeError, ValueError):
                    raise ValueError(f"Wrong value for field `{name}`: `{value}`")

    def cast(self, type, value):
        if hasattr(type, "_name"):
            if type._name == "List":
                if type.__args__:
                    args = type.__args__
                    type = lambda v: [self.cast(args[0], s) for s in v]
                else:
                    type = list
            elif type._name == "Dict":
                if type.__args__:
                    args = type.__args__
                    type = lambda o: {
                        self.cast(args[0], k): self.cast(args[1], v)
                        for k, v in o.items()
                    }
                else:
                    type = dict
        elif inspect.isclass(type) and issubclass(type, Base):
            type = type.create
        return type(value)

    def dump(self):
        return yaml.dump(asdict(self), allow_unicode=True)


@dataclass
class PersistedBase(Base):
    @classmethod
    def get_root(cls):
        root = Path(config.DATA_ROOT)
        if demo_mode_enabled():
            root = root / "demo"

        return root / cls.__root__


@dataclass
class SavedConfiguration(PersistedBase):
    __lock__ = threading.Lock()
    demo_mode_enabled: bool = False

    @classmethod
    def get_path(cls):
        return Path(config.DATA_ROOT) / "config.yml"

    def persist(self):
        with self.__lock__:
            self.get_path().write_text(self.dump())

    @classmethod
    def load(cls):
        path = cls.get_path()
        if path.exists():
            data = yaml.safe_load(path.read_text())
            data = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        else:
            data = {}
        return cls(**data)


@dataclass
class Person(Base):
    email: str
    first_name: str = ""
    last_name: str = ""
    group_id: str = ""
    group_name: str = ""

    @property
    def is_staff(self):
        return not config.STAFF or self.email in config.STAFF

    def is_referent(self, delivery):
        return self.email in delivery.get_referents() or self.email == delivery.contact

    @property
    def id(self):
        return self.group_id or self.email

    @property
    def name(self):
        return self.group_name or self.email


@dataclass
class Group(Base):
    id: str
    name: str
    members: List[str]


@dataclass
class Groups(PersistedBase):
    __root__ = "groups"
    __lock__ = threading.Lock()
    groups: Dict[str, Group]

    @classmethod
    def get_path(cls):
        return cls.get_root() / "groups.yml"

    @classmethod
    def load(cls):
        path = cls.get_path()
        if path.exists():
            data = yaml.safe_load(path.read_text())
            data = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        else:
            data = {"groups": {}}
        groups = cls(**data)
        return groups

    @classmethod
    def is_defined(cls):
        groups = cls.load()
        return len(groups.groups) > 0

    def persist(self):
        with self.__lock__:
            self.get_path().write_text(self.dump())

    def add_group(self, group):
        assert group.id not in self.groups, "Un foyer avec ce nom existe déjà."
        self.groups[group.id] = group

    def add_user(self, email, group_id):
        self.remove_user(email)
        group = self.groups[group_id]
        group.members.append(email)
        return group

    def remove_user(self, email):
        for group in self.groups.values():
            if email in group.members:
                group.members.remove(email)

    def get_user_group(self, email):
        for group in self.groups.values():
            if email in group.members:
                return group

    @classmethod
    def init_fs(cls):
        cls.get_root().mkdir(parents=True, exist_ok=True)


@dataclass
class Producer(Base):
    id: str
    name: str
    referent: str = ""
    referent_tel: str = ""
    referent_name: str = ""
    contact: str = ""
    description: str = ""
    practical_info: str = ""

    def has_active_products(self, delivery):
        products = delivery.get_products_by(self.id)
        return any([not p.rupture for p in products])

    def has_rupture_products(self, delivery):
        products = delivery.get_products_by(self.id)
        return any([p.rupture for p in products])

    def needs_price_update(self, delivery):
        products = delivery.get_products_by(self.id)
        return delivery.products_need_price_update(products)


@dataclass
class Product(Base):
    name: str
    ref: str
    price: price_field
    last_update: datetime_field = datetime.now()
    unit: str = ""
    description: str = ""
    packing: int = None
    producer: str = ""
    rupture: str = None

    def __str__(self):
        out = self.name
        # if self.unit:
        #     out += f" ({self.unit})"
        return out

    def update_from_form(self, form):
        self.name = form.get("name")
        self.price = form.float("price")
        self.unit = form.get("unit")
        self.description = form.get("description")
        self.last_update = datetime.now()
        if form.get("packing"):
            self.packing = form.int("packing")
        if "rupture" in form:
            self.rupture = form.get("rupture")
        else:
            self.rupture = None
        return self


@dataclass
class ProductOrder(Base):
    wanted: int
    adjustment: int = 0

    @property
    def quantity(self):
        return self.wanted + self.adjustment


@dataclass
class Order(Base):
    products: Dict[str, ProductOrder] = field(default_factory=dict)
    phone_number: str = ""

    def __getitem__(self, ref):
        if isinstance(ref, Product):
            ref = ref.ref
        return self.products.get(ref, ProductOrder(wanted=0))

    def __setitem__(self, ref, value):
        if isinstance(ref, Product):
            ref = ref.ref
        self.products[ref] = value

    def __iter__(self):
        yield from self.products.items()

    def total(self, products, delivery, email=None, include_shipping=True):
        def _get_price(ref):
            product = products.get(ref)
            return product.price if product and not product.rupture else 0

        producers = set([p.producer for p in products])
        products = {p.ref: p for p in products}

        total_products = sum(
            p.quantity * _get_price(ref) for ref, p in self.products.items()
        )

        shipping = (
            self.compute_shipping(delivery, producers, email) if include_shipping else 0
        )

        return round(total_products + shipping, 2)

    def compute_shipping(self, delivery, producers, email):
        total_shipping = 0
        for producer in producers:
            total_shipping = total_shipping + delivery.shipping_for(email, producer)
        return total_shipping

    @property
    def has_adjustments(self):
        return any(choice.adjustment for email, choice in self)


@dataclass
class Delivery(PersistedBase):

    __root__ = "delivery"
    __lock__ = threading.Lock()
    EMPTY = -1
    CLOSED = 0
    NEED_PRICE_UPDATE = 1
    OPEN = 2
    ADJUSTMENT = 3
    WAITING_PRODUCTS = 4
    OVER = 5

    name: str
    from_date: datetime_field
    to_date: datetime_field
    order_before: datetime_field
    contact: str
    contact_phone: str = ""
    instructions: str = ""
    where: str = "Marché de la Briche"
    products: List[Product] = field(default_factory=list)
    producers: Dict[str, Producer] = field(default_factory=dict)
    orders: Dict[str, Order] = field(default_factory=dict)
    shipping: Dict[str, price_field] = field(default_factory=dict)
    over: bool = False

    def __post_init__(self):
        self.id = None  # Not a field because we don't want to persist it.
        super().__post_init__()

    @property
    def status(self):
        if self.over:
            return self.OVER
        if not self.products:
            return self.EMPTY
        if self.products_need_price_update():
            return self.NEED_PRICE_UPDATE
        if self.is_open:
            return self.OPEN
        if self.needs_adjustment:
            return self.ADJUSTMENT
        if self.is_waiting_products:
            return self.WAITING_PRODUCTS

        return self.CLOSED

    def products_need_price_update(self, products=None):
        products = products or self.products
        max_age = self.from_date.date() - timedelta(days=60)
        return any(
            [
                product.last_update.date() < max_age
                for product in products
                if product.producer in self.producers
            ]
        )

    @property
    def dates(self):
        delivery_date = self.from_date.date()
        return {
            "creation_date": self.order_before - timedelta(weeks=4),
            "price_update_start": self.order_before - timedelta(weeks=4),
            "price_update_deadline": self.order_before - timedelta(weeks=2),
            "order_before": self.order_before,
            "adjustment_deadline": self.order_before + timedelta(days=4),
            "delivery_date": delivery_date,
        }

    @property
    def has_products(self):
        return len(self.products) > 0

    @property
    def total(self):
        return round(sum(o.total(self.products, self) for o in self.orders.values()), 2)

    @property
    def is_open(self):
        return datetime.now().date() <= self.order_before.date()

    @property
    def is_waiting_products(self):
        return (
            datetime.now().date() >= self.order_before.date()
            and datetime.now().date() <= self.from_date.date()
        )

    @property
    def is_foreseen(self):
        return datetime.now().date() <= self.from_date.date()

    @property
    def is_passed(self):
        return not self.is_foreseen

    @property
    def can_generate_reports(self):
        return not self.is_open and not self.needs_adjustment

    @property
    def has_packing(self):
        return any(p.packing for p in self.products)

    @property
    def needs_adjustment(self):
        return self.has_packing and any(self.product_missing(p) for p in self.products)

    @classmethod
    def init_fs(cls):
        cls.get_root().mkdir(parents=True, exist_ok=True)

    @classmethod
    def load(cls, id):
        path = cls.get_root() / f"{id}.yml"
        if not path.exists():
            raise DoesNotExist

        def _dedupe_products(raw_data):
            """On some rare occasions, different products get
            the same identifier (ref).

            This function finds them and appends "-dedupe" to it.
            This is not ideal but fixes the problem before it causes more
            trouble (such as https://github.com/spiral-project/copanier/issues/136)

            This function returns True if dupes have been found.
            """
            if ("products" not in raw_data) or len(raw_data["products"]) < 1:
                return False

            products = raw_data["products"]

            counter = Counter([p["ref"] for p in products])
            most_common = counter.most_common(1)[0]
            number_of_dupes = most_common[1]

            if number_of_dupes < 2:
                return False

            dupe_id = most_common[0]
            # Reconstruct the products list but change the duplicated ID.
            counter = 0
            new_products = []
            for product in products:
                ref = product["ref"]
                if ref == dupe_id:
                    counter = counter + 1
                    if counter == number_of_dupes:  # Only change the last occurence.
                        product["ref"] = f"{ref}-dedupe"
                new_products.append(product)
            raw_data["products"] = new_products
            return True

        data = yaml.safe_load(path.read_text())
        dupe_found = _dedupe_products(data)

        # Tolerate extra fields (but we'll lose them if instance is persisted)
        data = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        delivery = cls(**data)
        delivery.id = id

        if demo_mode_enabled():
            delivery.from_date = datetime.now()
            delivery.to_date = datetime.now() + timedelta(days=10)
            delivery.order_before = datetime.now() + timedelta(days=5)
            delivery.validate_all_prices()
            delivery.persist()

        if dupe_found:
            delivery.persist()

        return delivery

    @classmethod
    def all(cls):
        root = cls.get_root()
        for path in root.glob("*.yml"):
            id_ = str(path.relative_to(cls.get_root())).replace(".yml", "")
            yield Delivery.load(id_)

    @classmethod
    def is_defined(cls):
        return len(list(cls.all())) > 0

    @classmethod
    def incoming(cls):
        incoming_deliveries = [d for d in cls.all() if d.is_foreseen]
        return sorted(incoming_deliveries, key=lambda d: d.order_before)

    @classmethod
    def former(cls):
        former_deliveries = [d for d in cls.all() if not d.is_foreseen]
        return sorted(former_deliveries, key=lambda d: d.from_date, reverse=True)

    @property
    def path(self):
        assert self.id, "Cannot operate on unsaved deliveries"
        return self.get_root() / f"{self.id}.yml"

    def persist(self):
        with self.__lock__:
            if not self.id:
                self.id = uuid.uuid4().hex
            self.path.write_text(self.dump())

    def product_wanted(self, product):
        total = 0
        for order in self.orders.values():
            if product.ref in order.products:
                total += order.products[product.ref].quantity
        return total

    def product_missing(self, product):
        if not product.packing:
            return 0
        wanted = self.product_wanted(product)
        orphan = wanted % product.packing
        return product.packing - orphan if orphan else 0

    def has_order(self, person):
        return person.email in self.orders

    def get_products_by(self, producer):
        return [p for p in self.products if p.producer == producer]

    def get_product(self, ref):
        products = [p for p in self.products if p.ref == ref]
        if products:
            return products[0]

    def delete_product(self, ref):
        product = self.get_product(ref)
        if product:
            self.products.remove(product)

            for order in self.orders.values():
                if product.ref in order.products:
                    order.products.pop(product.ref)

            return product

    def total_for_producer(self, producer, person=None, include_shipping=True):
        producer_products = [p for p in self.products if p.producer == producer]
        if person:
            return self.orders.get(person).total(
                producer_products, self, person, include_shipping
            )
        return round(
            sum(
                o.total(producer_products, self, person, include_shipping=False)
                for o in self.orders.values()
            )
            + self.shipping.get(producer, 0),
            2,
        )

    def get_producers_for_referent(self, referent):
        return {
            id: producer
            for id, producer in self.producers.items()
            if producer.referent == referent
        }

    def get_referents(self):
        return [producer.referent for producer in self.producers.values()]

    def total_for(self, person):
        if person.email not in self.orders:
            return 0
        return self.orders[person.email].total(self.products, self)

    def shipping_for(self, person, producer):
        producer_shipping = self.shipping.get(producer)
        if not producer_shipping:
            return 0

        if not person:
            return producer_shipping

        producer_total = (
            self.total_for_producer(producer, include_shipping=False)
            - producer_shipping
        )
        person_amount = self.total_for_producer(
            producer, person=person, include_shipping=False
        )

        percentage_person = person_amount / producer_total
        shipping = percentage_person * producer_shipping
        return shipping

    def validate_all_prices(self):
        for product in self.products:
            product.last_update = datetime.now()
