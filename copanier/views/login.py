from .core import app, session, env

from ..models import Groups, Person
from .. import utils, emails, config


@app.listen("request")
async def auth_required(request, response):
    # Should be handled Roll side?
    # In dev mode, we serve the static, but we don't have yet a way to mark static
    # route as unprotected.
    if request.path.startswith("/static/"):
        return
    if request.route.payload and not request.route.payload.get("unprotected"):
        token = request.cookies.get("token")
        email = None
        if token:
            decoded = utils.read_token(token)
            email = decoded.get("sub")
        if not email:
            response.redirect = f"/connexion?next={request.path}"
            return response

        groups = Groups.load()
        request["groups"] = groups

        group = groups.get_user_group(email)
        user_info = {"email": email}
        if group:
            user_info.update(dict(group_id=group.id, group_name=group.name))
        user = Person(**user_info)
        request["user"] = user
        session.user.set(user)


@app.route("/connexion", methods=["GET"], unprotected=True)
async def connexion(request, response):
    response.html("login.html")


@app.route("/connexion", methods=["POST"], unprotected=True)
async def send_sesame(request, response):
    email = request.form.get("email").lower()
    token = utils.create_token(email)
    try:
        emails.send_from_template(
            env,
            "access_granted",
            email,
            f"Sésame {config.SITE_NAME}",
            hostname=request.host,
            token=token.decode(),
        )
    except RuntimeError:
        response.message("Oops, impossible d'envoyer le courriel…", status="error")
    else:
        response.message(
            f"Un sésame vous a été envoyé par mail, cliquez sur le lien pour vous "
            "connecter."
        )
    response.redirect = "/"


@app.route("/connexion/{token}", methods=["GET"], unprotected=True)
async def set_sesame(request, response, token):
    decoded = utils.read_token(token)
    if not decoded:
        response.message("Sésame invalide :(", status="error")
    else:
        response.message("Yay ! Le sésame a fonctionné. Bienvenue à bord ! :-)")
        response.cookies.set(
            name="token", value=token, httponly=True, max_age=60 * 60 * 24 * 7
        )
    response.redirect = "/"


@app.route("/déconnexion", methods=["GET"])
async def logout(request, response):
    response.cookies.set(name="token", value="", httponly=True)
    response.redirect = "/"
