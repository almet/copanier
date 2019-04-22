import os
from datetime import datetime, timedelta

import pytest
from roll.extensions import traceback
from roll.testing import Client as BaseClient

from copanier import app as copanier_app
from copanier import config as kconfig
from copanier.utils import create_token
from copanier.models import Delivery, Person, Product


def pytest_configure(config):
    os.environ["COPANIER_DATA_ROOT"] = "tmp/db"
    os.environ["COPANIER_SEND_EMAILS"] = ""
    os.environ["COPANIER_STAFF"] = ""
    kconfig.init()
    assert str(kconfig.DATA_ROOT) == "tmp/db"


def pytest_runtest_setup(item):
    for path in Delivery.get_root().glob("*.yml"):
        path.unlink()


class Client(BaseClient):
    content_type = 'application/x-www-form-urlencoded; charset=utf-8'
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
    traceback(copanier_app)
    return copanier_app


@pytest.fixture
def delivery():
    return Delivery(
        producer="Andines",
        contact="mister@me.me",
        from_date=datetime.now() + timedelta(days=10),
        to_date=datetime.now() + timedelta(days=10),
        order_before=datetime.now() + timedelta(days=7),
        products=[Product(name="Lait", ref="123", price=1.5)],
    )


@pytest.fixture
def person():
    return Person(email="foo@bar.fr")
