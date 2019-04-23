import inspect
import threading
import uuid
from datetime import datetime
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict

import yaml

from . import config


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
class Person(Base):
    email: str
    first_name: str = ""
    last_name: str = ""

    @property
    def is_staff(self):
        return not config.STAFF or self.email in config.STAFF


@dataclass
class Product(Base):
    name: str
    ref: str
    price: price_field
    unit: str = ""
    description: str = ""
    url: str = ""
    img: str = ""
    packing: int = None

    def __str__(self):
        out = self.name
        if self.unit:
            out += f" ({self.unit})"
        return out


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
    paid: bool = False

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

    def total(self, products):
        products = {p.ref: p for p in products}
        return round(
            sum(p.quantity * products[ref].price for ref, p in self.products.items()), 2
        )

    @property
    def has_adjustments(self):
        return any(choice.adjustment for email, choice in self)


@dataclass
class Delivery(Base):

    __root__ = "delivery"
    __lock__ = threading.Lock()
    CLOSED = 0
    OPEN = 1
    ADJUSTMENT = 2

    producer: str
    from_date: datetime_field
    to_date: datetime_field
    order_before: datetime_field
    contact: str
    description: str = ""
    instructions: str = ""
    where: str = "Marché de la Briche"
    products: List[Product] = field(default_factory=list)
    orders: Dict[str, Order] = field(default_factory=dict)
    id: str = field(default_factory=lambda *a, **k: uuid.uuid4().hex)
    infos_url: str = ""

    @property
    def status(self):
        if self.is_open:
            return self.OPEN
        if self.needs_adjustment:
            return self.ADJUSTMENT
        return self.CLOSED

    @property
    def total(self):
        return round(sum(o.total(self.products) for o in self.orders.values()), 2)

    @property
    def is_open(self):
        return datetime.now().date() <= self.order_before.date()

    @property
    def is_foreseen(self):
        return datetime.now().date() <= self.from_date.date()

    @property
    def is_passed(self):
        return not self.is_foreseen

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
    def get_root(cls):
        return Path(config.DATA_ROOT) / cls.__root__

    @classmethod
    def load(cls, id):
        path = cls.get_root() / f"{id}.yml"
        if not path.exists():
            raise DoesNotExist
        return cls(**yaml.safe_load(path.read_text()))

    @classmethod
    def all(cls):
        for path in cls.get_root().glob("*.yml"):
            yield Delivery.load(path.stem)

    @classmethod
    def incoming(cls):
        return [d for d in cls.all() if d.is_foreseen]

    @classmethod
    def former(cls):
        return [d for d in cls.all() if not d.is_foreseen]

    def persist(self):
        with self.__lock__:
            path = self.get_root() / f"{self.id}.yml"
            path.write_text(self.dump())

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
