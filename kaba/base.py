from datetime import datetime

from bson import ObjectId


class classproperty:
    def __init__(self, f):
        self.f = f

    def __get__(self, obj, owner):
        return self.f(owner)


class DoesNotExist(ValueError):
    pass


class Field:

    name = None
    coerce = None

    def __init__(self, choices=[], required=False, default=None):
        self.choices = choices
        self.required = required
        self.default = default

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        value = obj.get(self.name)
        return value

    def __set__(self, obj, value):
        print("set", value, id(value))
        value = self.coerce(value)
        print("set after", value, id(value))
        obj[self.name] = value


class Str(Field):
    coerce = str


class Float(Field):
    coerce = float


class Int(Field):
    coerce = int


class Datetime(Field):
    def coerce(self, value):
        if isinstance(value, datetime):
            return value
        if isinstance(value, int):
            return datetime.fromtimestamp(value)


class Email(Field):
    def coerce(self, value):
        # TODO proper validation
        if "@" not in value:
            raise ValueError(f"Invalid value for email: {value}")
        return value


class Reference(Field):

    def coerce(self, value):
        if isinstance(value, dict):
            value = value["_id"]
        return ObjectId(value)

    def __init__(self, document, *args, **kwargs):
        self.document = document
        return super().__init__(*args, **kwargs)


class Dict(Field):
    coerce = dict


class Mapping(Field):
    def __init__(self, key_field, value_field, *args, **kwargs):
        self.key_field = key_field
        self.value_field = value_field
        return super().__init__(*args, **kwargs)

    def coerce(self, value):
        print("coerce raw", value, id(value))
        if value is None:
            value = {}
        if not isinstance(value, dict):
            raise ValueError(f"{value} is not a dict")
        print("coerce", value, id(value))
        return {
            self.key_field.coerce(k): self.value_field.coerce(v)
            for k, v in value.items()
        }


class Array(Field):
    def __init__(self, type, *args, **kwargs):
        self.coerce = type
        return super().__init__(*args, **kwargs)

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        value = obj.get(self.name)
        if value is None:
            value = []
            self.__set__(value)
        return value

    def __set__(self, obj, value):
        obj[self.name] = [self.coerce(v) for v in value or []]


class MetaDocument(type):
    def __new__(cls, name, bases, attrs):
        for attr_name, attr_value in attrs.items():
            if not isinstance(attr_value, Field):
                continue
            attr_value.name = attr_name
        return super().__new__(cls, name, bases, attrs)


class Document(dict, metaclass=MetaDocument):
    __db__ = None
    __collection__ = None

    # def __repr__(self):
    #     return f"<{self.__class__.__name__} {self._id}>"

    @property
    def _id(self):
        return self["_id"]

    def insert_one(self):
        self.collection.insert_one(self)
        return self

    def replace_one(self):
        self.collection.replace_one({"_id": self._id}, self)
        return self

    @classmethod
    def find_one(cls, **kwargs):
        raw = cls.collection.find_one(kwargs)
        if not raw:
            raise DoesNotExist
        return cls(**raw)

    @classmethod
    def find(cls, **kwargs):
        for raw in cls.collection.find(kwargs):
            yield cls(**raw)

    @classproperty
    def collection(cls):
        assert cls.__collection__ is not None, f"You must define a {cls}.__collection__"
        return cls.__db__[cls.__collection__]

    @classmethod
    def bind(cls, db):
        cls.__db__ = db
