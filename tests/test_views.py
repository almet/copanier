import pytest

pytestmark = pytest.mark.asyncio


async def test_empty_home(client):
    resp = await client.get('/')
    assert resp.status == 200


async def test_home_should_list_active_delivery(client, delivery):
    delivery.persist()
    resp = await client.get('/')
    assert resp.status == 200
    assert delivery.producer in resp.body.decode()


async def test_home_should_redirect_to_login_if_not_logged(client):
    client.logout()
    resp = await client.get('/')
    assert resp.status == 302
    assert resp.headers["Location"] == "/sésame?next=/"
