"""Isolated account entry: no legacy user-ID routes, AI runtime or .env loading."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from api.account_pages import register_account_pages
from api.email_verification_pages import register_registration_verification_pages
from api.public_pages import PUBLIC_STATIC_DIRECTORY, render_public_page
from api.registration_pages import register_registration_pages
from conversation.coach_repository import CoachRepository
from coach.materials import MaterialRepository
from user.sqlite_repository import SQLiteUserRepository


def create_account_app(
    database_dir, *, registration_mail=None, dialogue_responder=None, dialogue_label=""
):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    repository = SQLiteUserRepository(Path(database_dir) / "users.db")
    app.mount("/static", StaticFiles(directory=PUBLIC_STATIC_DIRECTORY), name="static")
    register_registration_pages(app, repository, mail_config=registration_mail)
    register_registration_verification_pages(app, repository, login_enabled=True)
    dialogue = CoachRepository(Path(database_dir) / "coach_conversations.db")
    materials = MaterialRepository(Path(database_dir) / "coach_library.db")
    register_account_pages(
        app,
        repository,
        dialogue_repository=dialogue,
        dialogue_responder=dialogue_responder,
        dialogue_label=dialogue_label,
        materials_repository=materials,
    )

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def home():
        return HTMLResponse(
            render_public_page("home"),
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        )

    return app
