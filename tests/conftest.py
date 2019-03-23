import os
from datetime import datetime, timedelta

import pytest
from roll.extensions import traceback

from kaba import app as kaba_app
from kaba import config as kconfig
from kaba.models import Delivery, Person


def pytest_configure(config):
    os.environ["KABA_DATA_ROOT"] = "tmp/db"
    kconfig.init()
    assert str(kconfig.DATA_ROOT) == "tmp/db"


def pytest_runtest_setup(item):
    for path in Delivery.get_root().glob("*.yml"):
        path.unlink()


@pytest.fixture
def app():  # Requested by Roll testing utilities.
    traceback(kaba_app)
    return kaba_app


@pytest.fixture
def delivery():
    return Delivery(
        producer="Andines",
        when=datetime.now() + timedelta(days=10),
        order_before=datetime.now() + timedelta(days=7),
    )


@pytest.fixture
def person():
    return Person(email="foo@bar.fr")
