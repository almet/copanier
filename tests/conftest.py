import os
from datetime import datetime, timedelta

import pytest
from roll.extensions import traceback
from roll.testing import Client as BaseClient

from kaba import app as kaba_app
from kaba import config as kconfig
from kaba import create_token
from kaba.models import Delivery, Person


def pytest_configure(config):
    os.environ["KABA_DATA_ROOT"] = "tmp/db"
    kconfig.init()
    assert str(kconfig.DATA_ROOT) == "tmp/db"


def pytest_runtest_setup(item):
    for path in Delivery.get_root().glob("*.yml"):
        path.unlink()


class Client(BaseClient):
    headers = {}

    async def request(
        self, path, method="GET", body=b"", headers=None, content_type=None
    ):
        # TODO move this to Roll upstream?
        headers = headers or {}
        for key, value in self.headers.items():
            headers.setdefault(key, value)
        return await super().request(path, method, body, headers, content_type)

    def login(self, email="foo@bar.org"):
        token = create_token(email)
        self.headers["Cookie"] = f"token={token.decode()}"

    def logout(self):
        try:
            del self.headers["Cookie"]
        except KeyError:
            pass


@pytest.fixture
def client(app, event_loop):
    app.loop = event_loop
    app.loop.run_until_complete(app.startup())
    client = Client(app)
    client.login()
    yield client
    app.loop.run_until_complete(app.shutdown())


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
