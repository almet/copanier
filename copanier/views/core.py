import ujson as json

from pathlib import Path
from jinja2 import Environment, PackageLoader, select_autoescape
from roll.extensions import traceback
from roll import Roll as BaseRoll, Response as RollResponse

from weasyprint import HTML

from . import session
from .. import config, utils, loggers


class Response(RollResponse):
    def render_template(self, template_name, *args, **kwargs):
        context = app.context()
        context.update(kwargs)
        context["request"] = self.request
        context["config"] = config
        context["request"] = self.request
        if self.request.cookies.get("message"):
            context["message"] = json.loads(self.request.cookies["message"])
            self.cookies.set("message", "")
        return env.get_template(template_name).render(*args, **context)

    def html(self, template_name, *args, **kwargs):
        self.headers["Content-Type"] = "text/html; charset=utf-8"
        self.body = self.render_template(template_name, *args, **kwargs)

    def render_pdf(self, template_name, *args, **kwargs):
        html = self.render_template(template_name, *args, **kwargs)

        static_folder = Path(__file__).parent.parent / "static"
        stylesheets = [
            static_folder / "app.css",
            static_folder / "icomoon.css",
            static_folder / "page.css",
        ]
        if "css" in kwargs:
            stylesheets.append(static_folder / kwargs["css"])

        return HTML(string=html).write_pdf(stylesheets=stylesheets)

    def pdf(self, template_name, *args, **kwargs):
        self.body = self.render_pdf(template_name, *args, **kwargs)
        mimetype = "application/pdf"
        filename = kwargs.get("filename", "file.pdf")
        self.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        self.headers["Content-Type"] = f"{mimetype}; charset=utf-8"

    def xlsx(self, body, filename=f"{config.SITE_NAME}.xlsx"):
        self.body = body
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        self.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        self.headers["Content-Type"] = f"{mimetype}; charset=utf-8"

    def redirect(self, location):
        self.status = 302
        self.headers["Location"] = location

    redirect = property(None, redirect)

    def message(self, text, status="success"):
        self.cookies.set("message", json.dumps((text, status)))


class Roll(BaseRoll):
    Response = Response

    _context_func = []

    def context(self):
        context = {}
        for func in self._context_func:
            context.update(func())
        return context

    def register_context(self, func):
        self._context_func.append(func)


def staff_only(view):
    async def decorator(request, response, *args, **kwargs):
        user = session.user.get(None)
        if not user or not user.is_staff:
            response.message("Désolé, c'est réservé au staff par ici", "warning")
            response.redirect = request.headers.get("REFERRER", "/")
            return
        return await view(request, response, *args, **kwargs)

    return decorator


def configure():
    config.init()


env = Environment(
    loader=PackageLoader("copanier", "templates"),
    autoescape=select_autoescape(["copanier"]),
)

env.filters["date"] = utils.date_filter
env.filters["time"] = utils.time_filter

app = Roll()
traceback(app)


@app.listen("request")
async def attach_request(request, response):
    response.request = request


@app.listen("request")
async def log_request(request, response):
    if request.method == "POST":
        message = {
            "date": utils.utcnow().isoformat(),
            "data": request.form,
            "user": request.get("user"),
        }
        loggers.request_logger.info(
            json.dumps(message, sort_keys=True, ensure_ascii=False)
        )


@app.listen("startup")
async def on_startup():
    configure()
