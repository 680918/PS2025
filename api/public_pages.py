"""Public entry pages. Account authentication is implemented in a later step."""

from pathlib import Path
from string import Template
from html import escape


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
    return _render_layout(title, content, page)


def _render_layout(title, content, page=""):
    layout = Template((_TEMPLATES / "layout.html").read_text(encoding="utf-8"))
    return layout.substitute(
        title=title,
        content=content,
        home_current='aria-current="page"' if page == "home" else "",
        login_current='aria-current="page"' if page == "login" else "",
        register_current='aria-current="page"' if page == "register" else "",
    )


def render_verification_page(state, *, token="", csrf=""):
    """Only fixed copy and escaped hidden form values enter the shared layout."""
    copy = {
        "confirm": (
            "信",
            "ONE SMALL STEP",
            "确认这是你的邮箱",
            "如果你本人正在创建知行账户，请点击下方按钮，完成邮箱验证。",
            "链接只可使用一次。如果这不是你的操作，关闭页面即可。",
        ),
        "success": (
            "✓",
            "EMAIL VERIFIED",
            "邮箱验证成功",
            "你的邮箱已完成验证。登录功能正在准备中，暂时还不能进入成长空间。",
            "本次操作只验证邮箱，不会设置或修改密码，也不会自动登录。",
        ),
        "invalid": (
            "!",
            "LET’S TRY AGAIN",
            "这个验证链接暂时无法使用",
            "链接可能已过期、已使用或已被更新。请打开最新的验证邮件，再试一次。",
            "重新发送邮件的入口将在注册流程接通后提供。目前可返回注册页查看进度。",
        ),
        "retry": (
            "↻",
            "OPEN YOUR EMAIL",
            "请重新打开验证邮件",
            "确认页面已失效，或浏览器未保留验证信息。请从最新邮件重新打开链接，再点击确认。",
            "如果打开了多个确认页面，请使用最近打开的那一个。邮箱验证链接本身仍按原有效期计算。",
        ),
        "unavailable": (
            "…",
            "PLEASE TRY LATER",
            "验证暂时无法完成",
            "服务暂时无法完成这次确认。请稍后重新打开邮件链接，再试一次。",
            "如果链接已经过期，请等待重新发送入口开放后申请新邮件。",
        ),
    }
    symbol, eyebrow, heading, description, help_text = copy[state]
    if state == "confirm":
        action = (
            '<form method="post" action="/web/verify-email" autocomplete="off">'
            f'<input type="hidden" name="token" value="{escape(token, quote=True)}">'
            f'<input type="hidden" name="csrf" value="{escape(csrf, quote=True)}">'
            '<button class="button button-primary button-full" type="submit">确认验证邮箱 →</button></form>'
        )
    elif state == "success":
        action = '<a class="button button-primary button-full" href="/web/login">查看登录页 →</a>'
    else:
        action = '<a class="button button-outline button-full" href="/web/register">查看注册页 →</a>'
    template = Template((_TEMPLATES / "verification.html").read_text(encoding="utf-8"))
    content = template.substitute(
        symbol=symbol,
        eyebrow=eyebrow,
        heading=heading,
        description=description,
        help=help_text,
        action=action,
    )
    return _render_layout(f"{heading} · 知行成长教练", content)
