import os
from datetime import datetime, timedelta

import pytest
from roll.extensions import traceback
from roll.testing import Client as BaseClient

from copanier import app as copanier_app
from copanier import config as kconfig
from copanier.utils import create_token
from copanier.models import Delivery, Person, Product, Producer, Groups, Group


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
    content_type = "application/x-www-form-urlencoded; charset=utf-8"
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
        name="CRAC d'automne",
        contact="mister@me.me",
        from_date=datetime.now() + timedelta(days=10),
        to_date=datetime.now() + timedelta(days=10),
        order_before=datetime.now() + timedelta(days=7),
        products=[
            Product(name="Lait", producer="ferme-du-coin", ref="lait", price=1.5,)
        ],
        producers={"ferme-du-coin": Producer(name="Ferme du coin", id="ferme-du-coin")},
    )


@pytest.fixture
def groups():
    fractal_brocolis = Group(
        id="fractal-brocolis", name="The Fractal Brocolis", members=["foo@bar.org"]
    )
    groups = Groups({"fractal-brocolis": fractal_brocolis})
    groups.persist()
    return groups


@pytest.fixture
def anothergroup():
    return Group(id="another-group", name="Another Group", members=["another@bar.org"])


@pytest.fixture
def yaourt():
    return Product(
        ref="yaourt",
        unit="pot 125ml",
        name="Yaourt",
        price="3.5",
        packing=4,
        producer="ferme-du-coin",
    )


@pytest.fixture
def fromage():
    return Product(
        ref="fromage", name="Fromage", price="9.2", producer="ferme-du-coin",
    )


@pytest.fixture
def person():
    return Person(email="foo@bar.fr")
