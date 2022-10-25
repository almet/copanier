from pathlib import Path
import minicli
from roll.extensions import simple_server, static

from .models import Product, Person, Order, Delivery
from .views.core import app

__version__ = "0.0.5"

@minicli.cli()
def shell():
    """Run an ipython in app context."""
    try:
        from IPython import start_ipython
    except ImportError:
        print('IPython is not installed. Type "pip install ipython"')
    else:
        start_ipython(
            argv=[],
            user_ns={
                "app": app,
                "Product": Product,
                "Person": Person,
                "Order": Order,
                "Delivery": Delivery,
            },
        )


@minicli.cli
def serve(reload=False):
    """Run a web server (for development only)."""
    if reload:
        import hupper

        hupper.start_reloader("copanier.serve")
    static(app, root=Path(__file__).parent / "static")
    simple_server(app, port=2244)


def main():
    minicli.run()
