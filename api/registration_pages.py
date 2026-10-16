"""Registration form preview: bounded, read-only validation with honest status."""

from urllib.parse import parse_qs

from fastapi import Request
from fastapi.responses import HTMLResponse

from api.public_pages import render_registration_page, render_registration_waiting_page
from security.registration_validation import validate_registration_fields


_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'self'; form-action 'self'; "
        "base-uri 'none'; frame-ancestors 'none'"
    ),
}


def register_registration_preview(app):
    def form_error():
        return HTMLResponse(
            render_registration_page(form_error="填写内容无法读取，请重新填写后提交。"),
            status_code=400,
            headers=_HEADERS,
        )

    @app.post(
        "/web/auth/register", response_class=HTMLResponse, include_in_schema=False
    )
    async def validate_registration(request: Request):
        if (
            request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            != "application/x-www-form-urlencoded"
        ):
            return form_error()
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 8192:
                return form_error()
            body.extend(chunk)
        try:
            fields = parse_qs(
                body.decode("ascii"),
                keep_blank_values=True,
                strict_parsing=True,
                encoding="utf-8",
                errors="strict",
                max_num_fields=3,
            )
        except (ValueError, UnicodeError):
            return form_error()
        if not set(fields) <= {"name", "email", "password"} or any(
            len(values) != 1 for values in fields.values()
        ):
            return form_error()
        checked = validate_registration_fields(
            fields.get("name", [""])[0],
            fields.get("email", [""])[0],
            fields.get("password", [""])[0],
        )
        if checked["errors"]:
            return HTMLResponse(
                render_registration_page(fields=checked, errors=checked["errors"]),
                status_code=400,
                headers=_HEADERS,
            )
        return HTMLResponse(
            render_registration_waiting_page(checked["email"]), headers=_HEADERS
        )
