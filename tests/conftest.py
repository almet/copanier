import os

import pytest
from roll.extensions import traceback

from kaba import app as kaba_app
from kaba import utils
from kaba.models import Delivery, Person


def pytest_configure(config):
    from kaba import models
    models.Base.ROOT = "tmp/db"


# def pytest_runtest_setup(item):
#     # assert get_db().name == "test_eurordis"
#     for cls in [Delivery]:
#         collection = cls.collection
#         collection.drop()


@pytest.fixture
def app():  # Requested by Roll testing utilities.
    traceback(kaba_app)
    return kaba_app


@pytest.fixture
def delivery():
    return Delivery(
        producer="Andines", when=utils.utcnow(), order_before=utils.utcnow()
    )


@pytest.fixture
def person():
    return Person(email="foo@bar.fr")
