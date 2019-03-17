from kaba import Producer, Order, Product


def test_can_create_producer():
    producer = Producer(name="Andines")
    producer.insert_one()
    assert producer.name == "Andines"
    retrieved = Producer.find_one(name="Andines")
    assert retrieved.name == producer.name
    assert retrieved._id == producer._id


def test_can_create_order():
    order = Order(products=[Product(name="riz", price="2.4")])
    order.insert_one()
    retrieved = Order.find_one(_id=order._id)
    assert retrieved.products[0].name == "riz"


def test_can_update_order_products():
    order = Order()
    order.products.append(Product(name="riz", price="2.4"))
    assert len(order.products) == 1
