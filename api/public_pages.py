"""Public entry pages. Account authentication is implemented in a later step."""

from pathlib import Path
from string import Template
from html import escape
from datetime import timedelta, timezone


_TEMPLATES = Path(__file__).parent / "templates" / "public"
PUBLIC_STATIC_DIRECTORY = Path(__file__).parent / "static"
_TITLES = {
    "home": "知行 · AI Learning Coach",
    "login": "登录 · 知行成长教练",
    "register": "创建账户 · 知行成长教练",
}


def render_public_page(page: str) -> str:
    """Render only known, local content; never interpolate submitted credentials."""
    if page == "register":
        return render_registration_page()
    title = _TITLES[page]
    content = (_TEMPLATES / f"{page}.html").read_text(encoding="utf-8")
    return _render_layout(title, content, page)


def render_registration_page(*, fields=None, errors=None, form_error="", csrf=""):
    fields, errors = fields or {}, errors or {}
    values = {
        "csrf_value": escape(csrf, quote=True),
        "name_value": escape(fields.get("name", ""), quote=True),
        "email_value": escape(fields.get("email", ""), quote=True),
    }
    for field in ("name", "email", "password"):
        message = errors.get(field)
        values[f"{field}_error"] = (
            f'<p id="register-{field}-error" class="field-error">{escape(message)}</p>'
            if message
            else ""
        )
        values[f"{field}_error_attributes"] = (
            f'aria-invalid="true" aria-describedby="register-{field}-error"'
            if message and field != "password"
            else 'aria-invalid="true"'
            if message
            else ""
        )
    values["password_error_description"] = (
        " register-password-error" if "password" in errors else ""
    )
    summary = ""
    if errors or form_error:
        summary = '<div class="form-error-summary" role="alert"><p>请调整后再继续</p>'
        if form_error:
            summary += f"<p>{escape(form_error)}</p>"
        else:
            summary += "<p>请查看下方提示，密码需要重新填写。</p><ul>"
            for field, message in errors.items():
                summary += f'<li><a href="#register-{field}">{escape(message)}</a></li>'
            summary += "</ul>"
        summary += "</div>"
    values["error_summary"] = summary
    template = Template((_TEMPLATES / "register.html").read_text(encoding="utf-8"))
    return _render_layout(
        _TITLES["register"], template.substitute(**values), "register"
    )


def render_registration_waiting_page(
    masked_email,
    expires_at,
    *,
    delivery_state="not_sent",
    retry_after_seconds=0,
    mail_enabled=False,
    simulated=False,
    csrf="",
):
    template = Template(
        (_TEMPLATES / "registration_waiting.html").read_text(encoding="utf-8")
    )
    expires = expires_at.astimezone(timezone(timedelta(hours=8))).strftime(
        "%m月%d日 %H:%M"
    )
    heading, symbol, step_title, step_description, help_text = {
        "not_sent": (
            "申请已保存，等待验证邮箱",
            "信",
            "准备验证邮箱",
            "本次尚未发送邮件，也未创建账户",
            "发送后，请打开注册邮箱，点击验证邮件中的链接，并在页面上确认。",
        ),
        "sending": (
            "正在确认邮件发送结果",
            "…",
            "发送处理中，结果待确认",
            "请先查看邮箱，再刷新申请进度",
            "发送可能仍在处理，也可能在连接中断后等待确认。系统不会因刷新或等待时间较长而重复发送。",
        ),
        "accepted": (
            "验证邮件已提交，请查收邮箱",
            "✓",
            "邮件服务器已接收",
            "尚需打开邮件，确认邮箱归属",
            "服务器接收不代表已经到达收件箱。若没看到邮件，请检查垃圾邮件；已有有效链接仍可使用。",
        ),
        "failed": (
            "邮件暂未发出，可以稍后重试",
            "!",
            "本次邮件未成功提交",
            "申请仍然保留，账户尚未创建",
            "本次发送已明确失败。准备好后，可主动重试；重试不会延长申请的有效期。",
        ),
        "unknown": (
            "发送结果暂未确认",
            "…",
            "邮件可能已经提交",
            "请先查看收件箱和垃圾邮件",
            "当前无法确定邮件是否已提交，暂不提供重复发送。若收到邮件，已有有效链接仍可继续确认。",
        ),
    }[delivery_state]
    action = ""
    if mail_enabled and delivery_state in {"not_sent", "failed"}:
        action_name = "retry" if delivery_state == "failed" else "send"
        button = "重试发送验证邮件" if action_name == "retry" else "发送验证邮件"
        if simulated:
            button = "模拟重试发送" if action_name == "retry" else "模拟发送验证邮件"
        if retry_after_seconds > 0:
            action = (
                '<p class="mail-cooldown" role="status">'
                f"请在 {int(retry_after_seconds)} 秒后刷新本页，再重试。</p>"
                '<button class="button button-primary button-full" type="button" disabled>等待后可重试</button>'
            )
        else:
            action = (
                '<form method="post" action="/web/register/send-verification" class="registration-mail-form">'
                f'<input type="hidden" name="csrf" value="{escape(csrf, quote=True)}">'
                f'<input type="hidden" name="action" value="{action_name}">'
                f'<button class="button button-primary button-full" type="submit">{button} →</button></form>'
            )
    if mail_enabled or delivery_state != "not_sent":
        action += '<a class="button button-outline button-full" href="/web/register/pending">刷新申请进度</a>'
    if delivery_state == "not_sent" and not mail_enabled:
        help_text = "请保留当前浏览器的申请信息，后续查询或重发时会用到。正式账户仍须验证邮箱后才能创建。"
        note = "邮件发送尚未接通，本次没有发送邮件，无需等待邮件。"
    elif mail_enabled:
        note = "刷新页面只查询状态，不会重复发送邮件。"
    else:
        note = "当前环境未启用发送或重试，请先查看已有邮件与申请状态。"
    if simulated:
        step_description = {
            "not_sent": "点击模拟按钮，检验邮件提交后的页面效果",
            "sending": "模拟请求正在处理，请刷新进度查看结果",
            "accepted": "仅模拟服务器接收，未发送真实邮件",
            "failed": "模拟发送未成功，可等待后检验重试",
            "unknown": "模拟请求结果待确认，不会自动重发",
        }[delivery_state]
        if delivery_state == "accepted":
            heading = "验证邮件已模拟提交"
            step_title = "已完成模拟提交"
        help_text = "这是本机模拟流程，没有发送真实邮件。页面用于检验发送、失败重试和状态变化；不会据此自动验证邮箱。"
    content = template.substitute(
        masked_email=escape(masked_email),
        expires_at=escape(expires),
        heading=escape(heading),
        symbol=escape(symbol),
        step_title=escape(step_title),
        step_description=escape(step_description),
        help_text=escape(help_text),
        delivery_action=action,
        delivery_note=escape(note),
        simulation_notice='<p class="mail-simulation-notice" role="note">本机模拟 · 不会发送真实邮件</p>'
        if simulated
        else "",
    )
    return _render_layout(f"{heading} · 知行成长教练", content, "register")


def render_registration_mail_problem_page(kind, *, wait_seconds=0):
    heading, description = {
        "security": (
            "请刷新申请页面后再操作",
            "页面已过期或操作无法核对。请在原申请浏览器中刷新进度，再使用页面上的按钮。",
        ),
        "unavailable": (
            "暂时无法处理邮件操作",
            "请稍后刷新申请进度。如果你已发起过发送，请先查看状态和收件箱。",
        ),
        "disabled": ("邮件发送暂未启用", "当前环境尚未配置网页发信，请返回申请进度。"),
        "limited": (
            "邮件操作有些频繁",
            f"请在 {int(wait_seconds)} 秒后刷新申请进度，再决定是否继续。",
        ),
    }[kind]
    return _render_registration_notice(
        symbol="…",
        heading=heading,
        description=description,
        help_text="刷新进度不会触发发送，也不会修改已保存的邮箱或密码。",
        button="返回申请进度 →",
        href="/web/register/pending",
    )


def render_registration_problem_page(kind):
    copy = {
        "missing": (
            "暂时无法查看这份申请",
            "浏览器未保留有效申请信息，或申请已经失效。请返回注册页查看进度。",
            "为保护你的信息，页面不会显示其他浏览器的申请。正式登录与邮件发送仍在准备中。",
        ),
        "conflict": (
            "暂时无法继续这次申请",
            "请稍后重新打开注册页再试。已有账户的用户可以查看登录页进度。",
            "本次没有更改已有申请或账户，也没有发送邮件。请勿反复提交或更改密码尝试。",
        ),
        "unavailable": (
            "申请暂时无法保存或查看",
            "服务暂时较忙，或保存没有完成。请稍后重新打开注册页再试。",
            "本次没有创建正式账户或发送邮件。稍后重试时，密码需要重新填写。",
        ),
    }
    heading, description, help_text = copy[kind]
    return _render_registration_notice(
        symbol="…",
        heading=heading,
        description=description,
        help_text=help_text,
        button="返回注册页 →",
    )


def render_registration_security_retry_page():
    return _render_registration_notice(
        symbol="↻",
        heading="请重新打开注册页面",
        description="页面已过期，或浏览器未保留注册信息。请重新打开注册页，再填写并提交。",
        help_text="为保护你的信息，本次没有继续处理填写内容，也没有创建账户或发送邮件。",
        button="重新打开注册页 →",
    )


def render_registration_rate_limited_page(wait_seconds):
    return _render_registration_notice(
        symbol="…",
        heading="操作有些频繁，请稍等一下",
        description=f"请在 {wait_seconds} 秒后再打开注册页，继续填写。你可以按自己的节奏慢慢来。",
        help_text="本次操作没有继续处理，也没有创建账户或发送邮件。稍后重试时，密码需要重新填写。",
        button="稍后返回注册页 →",
    )


def _render_registration_notice(
    *, symbol, heading, description, help_text, button, href="/web/register"
):
    content = Template(
        (_TEMPLATES / "verification.html").read_text(encoding="utf-8")
    ).substitute(
        step_label="注册填写",
        symbol=symbol,
        eyebrow="LET’S START AGAIN",
        heading=heading,
        description=description,
        help=help_text,
        action=f'<a class="button button-primary button-full" href="{escape(href, quote=True)}">{escape(button)}</a>',
    )
    return _render_layout(f"{heading} · 知行成长教练", content, "register")


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
    return _render_confirmation_page(
        state, copy, "/web/verify-email", "确认验证邮箱 →", token, csrf
    )


def render_registration_verification_page(state, *, token="", csrf=""):
    copy = {
        "confirm": (
            "信",
            "YOUR GROWTH STARTS HERE",
            "确认邮箱，开启成长的第一步",
            "如果你本人刚刚申请创建知行账户，请确认使用这个邮箱。确认后，我们会为你创建账户。",
            "只有你本人发起的注册才应确认。如果这不是你的操作，直接关闭页面即可，不会因此创建账户。",
        ),
        "success": (
            "✓",
            "A NEW BEGINNING",
            "账户已创建，邮箱已验证",
            "你的账户已准备好，注册时设置的密码也已安全保存。期待与你一起，把每一次学习变成成长的积累。",
            "登录功能正在准备中，目前还不能进入成长空间。本次确认不会自动登录，也不会修改你设置的密码。",
        ),
        "invalid": (
            "!",
            "LET’S TRY AGAIN",
            "这个注册链接暂时无法使用",
            "链接可能已过期、已使用或已被更新。请从最新的注册验证邮件重新打开。",
            "如果之前已经看到开户成功，无需再次确认。重新申请和重发邮件入口仍在准备中，当前注册页仅供预览。",
        ),
        "retry": (
            "↻",
            "OPEN YOUR EMAIL",
            "请重新打开注册验证邮件",
            "确认页面已失效，或浏览器未保留确认信息。请从最新邮件重新打开链接，再点击确认。",
            "如果打开了多个注册确认页面，请使用最近打开的那一个。注册链接仍按原有效期计算。",
        ),
        "unavailable": (
            "…",
            "PLEASE TRY LATER",
            "账户创建暂时无法完成",
            "服务暂时无法完成这次确认。请稍后重新打开邮件链接，再试一次。",
            "本次操作没有完成账户创建。你可以在链接有效期内稍后重试，重新打开页面不会延长期限。",
        ),
    }
    return _render_confirmation_page(
        state, copy, "/web/verify-registration", "确认邮箱并创建账户 →", token, csrf
    )


def _render_confirmation_page(state, copy, path, button_label, token, csrf):
    symbol, eyebrow, heading, description, help_text = copy[state]
    if state == "confirm":
        action = (
            f'<form method="post" action="{escape(path, quote=True)}" autocomplete="off">'
            f'<input type="hidden" name="token" value="{escape(token, quote=True)}">'
            f'<input type="hidden" name="csrf" value="{escape(csrf, quote=True)}">'
            f'<button class="button button-primary button-full" type="submit">{escape(button_label)}</button></form>'
        )
    elif state == "success":
        action = '<a class="button button-primary button-full" href="/web/login">查看登录页 →</a>'
    else:
        action = '<a class="button button-outline button-full" href="/web/register">查看注册页 →</a>'
    template = Template((_TEMPLATES / "verification.html").read_text(encoding="utf-8"))
    content = template.substitute(
        step_label="邮箱验证",
        symbol=symbol,
        eyebrow=eyebrow,
        heading=heading,
        description=description,
        help=help_text,
        action=action,
    )
    return _render_layout(f"{heading} · 知行成长教练", content)
