from slugify import slugify
from ..models import Groups, Group
from .core import app, session


@app.listen("startup")
async def on_startup():
    Groups.init_fs()


@app.route("/groupes", methods=["GET"])
async def groups(request, response):
    response.html("groups/list_groups.html", {"groups": request["groups"]})


@app.route("/groupes/{id}/rejoindre", method=["GET"])
async def join_group(request, response, id):
    user = session.user.get(None)
    group = request["groups"].add_user(user.email, id)
    request["groups"].persist()
    redirect = "/" if not request["user"].group_id else "/groupes"

    response.message(f"Vous avez bien rejoint le foyer « {group.name} »")
    response.redirect = redirect


@app.route("/groupes/créer", methods=["GET", "POST"])
async def create_group(request, response):
    group = None
    if request.method == "POST":
        form = request.form
        members = []
        if form.get("members"):
            members = [m.strip() for m in form.get("members").split(",")]

        if not request["user"].group_id and request["user"].email not in members:
            members.append(request["user"].email)

        group = Group.create(
            id=slugify(form.get("name")), name=form.get("name"), members=members
        )
        request["groups"].add_group(group)
        request["groups"].persist()
        response.message(f"Le foyer {group.name} à bien été créé")
        response.redirect = "/"
    response.html("groups/edit_group.html", group=group)


@app.route("/groupes/{id}/éditer", methods=["GET", "POST"])
async def edit_group(request, response, id):
    assert id in request["groups"].groups, "Impossible de trouver le foyer"
    group = request["groups"].groups[id]
    if request.method == "POST":
        form = request.form
        members = []
        if form.get("members"):
            members = [m.strip() for m in form.get("members").split(",")]
        group.members = members
        group.name = form.get("name")
        request["groups"].groups[id] = group
        request["groups"].persist()
        response.redirect = "/groupes"
    response.html("groups/edit_group.html", group=group)


@app.route("/groupes/{id}/supprimer", methods=["GET"])
async def delete_group(request, response, id):
    assert id in request["groups"].groups, "Impossible de trouver le foyer"
    deleted = request["groups"].groups.pop(id)
    request["groups"].persist()
    response.message(f"Le foyer {deleted.name} à bien été supprimé")
    response.redirect = "/groupes"
