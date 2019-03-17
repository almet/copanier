import os

import pytest
from roll.extensions import traceback

# Before loading any eurordis module.
os.environ["KABA_DB"] = "mongodb://localhost/kaba_test"

from kaba import app as kaba_app
from kaba import connect, Producer


def pytest_configure(config):
    client = connect()
    client.drop_database("test_kaba")


def pytest_runtest_setup(item):
    # assert get_db().name == "test_eurordis"
    for cls in [Producer]:
        collection = cls.collection
        collection.drop()


@pytest.fixture
def app():  # Requested by Roll testing utilities.
    traceback(kaba_app)
    return kaba_app
