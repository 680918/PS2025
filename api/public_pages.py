"""Public entry pages. Account authentication is implemented in a later step."""

from pathlib import Path
from string import Template


_TEMPLATES = Path(__file__).parent / "templates" / "public"
PUBLIC_STATIC_DIRECTORY = Path(__file__).parent / "static"
_TITLES = {
    "home": "知行 · AI Learning Coach",
    "login": "登录 · 知行成长教练",
    "register": "创建账户 · 知行成长教练",
}


def render_public_page(page: str) -> str:
    """Render only known, local content; never interpolate submitted credentials."""
    title = _TITLES[page]
    content = (_TEMPLATES / f"{page}.html").read_text(encoding="utf-8")
    layout = Template((_TEMPLATES / "layout.html").read_text(encoding="utf-8"))
    return layout.substitute(
        title=title,
        content=content,
        home_current='aria-current="page"' if page == "home" else "",
        login_current='aria-current="page"' if page == "login" else "",
        register_current='aria-current="page"' if page == "register" else "",
    )
