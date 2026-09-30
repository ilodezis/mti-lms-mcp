"""MCP-сервер для ЛМС МТИ (lms.mti.moscow).

Только чтение: расписание, дисциплины, задания, оценки, уведомления, сообщения.
Авторизация — кука браузерной сессии из .env, при протухании (если заданы
LMS_LOGIN/LMS_PASSWORD) сервер сам перелогинивается и переписывает куку в .env.
"""

import json
import logging
import os
import re
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

try:
    from fastmcp import FastMCP
    from fastmcp.server.auth import TokenVerifier, AccessToken
except ImportError:
    from mcp.server.fastmcp import FastMCP
    TokenVerifier = None
    AccessToken = None

BASE = "https://lms.mti.moscow"
ENV = Path(__file__).with_name(".env")

logging.getLogger("httpx").setLevel(logging.WARNING)

mcp = FastMCP("lms")

OAUTH_CODES: dict[str, dict] = {}
ACTIVE_MCP_TOKEN: str | None = None
ACTIVE_CLIENT_SECRET: str | None = None
ACTIVE_CLIENT_ID: str = "mti-lms"
# Claude.ai finishes OAuth on its own callback; an authorization code goes nowhere else.
ALLOWED_REDIRECT_HOSTS = ("claude.ai", "claude.com")


def _get_base_url(request) -> str:
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "localhost:8030")
    proto = request.headers.get("x-forwarded-proto", "https")
    return f"{proto}://{host}"


if hasattr(mcp, "custom_route"):
    @mcp.custom_route("/health", methods=["GET"])
    async def _health(request):
        from starlette.responses import JSONResponse
        return JSONResponse({"status": "ok", "service": "lms-mcp", "transport": "http", "version": "4.0.3"})

    @mcp.custom_route("/healthz", methods=["GET"])
    async def _healthz(request):
        from starlette.responses import JSONResponse
        return JSONResponse({"status": "ok", "service": "lms-mcp", "transport": "http", "version": "4.0.3"})

    @mcp.custom_route("/ping", methods=["GET"])
    async def _ping(request):
        from starlette.responses import JSONResponse
        return JSONResponse({"status": "ok", "service": "lms-mcp", "transport": "http", "version": "4.0.3"})

    @mcp.custom_route("/", methods=["GET"])
    async def _root(request):
        from starlette.responses import JSONResponse
        return JSONResponse({
            "status": "ok",
            "service": "lms-mcp",
            "transport": "http",
            "endpoint": "/mcp",
            "health": "/health",
        })

    @mcp.custom_route("/.well-known/oauth-authorization-server", methods=["GET", "OPTIONS"])
    @mcp.custom_route("/.well-known/openid-configuration", methods=["GET", "OPTIONS"])
    async def _oauth_as_meta(request):
        from starlette.responses import JSONResponse
        base = _get_base_url(request)
        return JSONResponse(
            {
                "issuer": base,
                "authorization_endpoint": f"{base}/oauth/authorize",
                "token_endpoint": f"{base}/oauth/token",
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code"],
                "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"],
                "code_challenge_methods_supported": ["S256"],
            },
            headers={"Access-Control-Allow-Origin": "*"},
        )

    @mcp.custom_route("/.well-known/oauth-protected-resource", methods=["GET", "OPTIONS"])
    async def _oauth_pr_meta(request):
        from starlette.responses import JSONResponse
        base = _get_base_url(request)
        return JSONResponse(
            {
                "resource": f"{base}/mcp",
                "authorization_servers": [base],
                "bearer_methods_supported": ["header"],
            },
            headers={"Access-Control-Allow-Origin": "*"},
        )

    @mcp.custom_route("/oauth/authorize", methods=["GET", "POST", "OPTIONS"])
    async def _oauth_authorize(request):
        import secrets
        import time
        import urllib.parse
        from html import escape
        from starlette.responses import HTMLResponse, PlainTextResponse

        if request.method == "OPTIONS":
            return PlainTextResponse("", status_code=200, headers={"Access-Control-Allow-Origin": "*"})

        client_id = request.query_params.get("client_id")
        redirect_uri = request.query_params.get("redirect_uri")
        state = request.query_params.get("state")
        code_challenge = request.query_params.get("code_challenge")
        code_challenge_method = request.query_params.get("code_challenge_method", "S256")

        expected_client_id = os.getenv("MCP_CLIENT_ID", CFG.get("MCP_CLIENT_ID", "mti-lms"))
        if client_id and client_id != expected_client_id:
            return HTMLResponse(
                f"<h3 style='color:#ef4444;font-family:sans-serif;'>Ошибка: неверный client_id ({escape(client_id)})</h3>",
                status_code=400,
            )

        parsed = urllib.parse.urlsplit(redirect_uri or "")
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_REDIRECT_HOSTS:
            return HTMLResponse(
                "<h3 style='color:#ef4444;font-family:sans-serif;'>Ошибка: redirect_uri должен вести на claude.ai</h3>",
                status_code=400,
            )

        code = f"code_{secrets.token_urlsafe(32)}"
        OAUTH_CODES[code] = {
            "client_id": client_id or expected_client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "expires_at": time.time() + 300,
        }

        sep = "&" if "?" in redirect_uri else "?"
        params = {"code": code}
        if state:
            params["state"] = state
        target = f"{redirect_uri}{sep}{urllib.parse.urlencode(params)}"
        safe_target = escape(target)

        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>LMS MCP — Авторизация</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #0f172a; color: #f8fafc; }}
    .card {{ background: #1e293b; padding: 2.5rem; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); width: 100%; max-width: 420px; text-align: center; border: 1px solid #334155; }}
    h2 {{ margin-top: 0; color: #38bdf8; font-size: 1.4rem; }}
    p {{ color: #94a3b8; font-size: 0.95rem; line-height: 1.5; }}
    .badge {{ display: inline-block; padding: 0.35rem 0.75rem; background: #0369a1; color: #e0f2fe; border-radius: 20px; font-size: 0.85rem; font-weight: 600; margin: 0.5rem 0 1rem; }}
    .btn {{ display: inline-block; width: 100%; box-sizing: border-box; padding: 0.85rem; margin-top: 1.5rem; background: #0284c7; color: white; border: none; border-radius: 10px; font-weight: 600; font-size: 1rem; cursor: pointer; text-decoration: none; transition: background 0.2s; }}
    .btn:hover {{ background: #0369a1; }}
  </style>
  <meta http-equiv="refresh" content="1;url={safe_target}">
</head>
<body>
  <div class="card">
    <h2>LMS MCP Server</h2>
    <div class="badge">Авторизация Claude.ai</div>
    <p>Доступ к инструментам LMS МТИ успешно одобрен. Перенаправление в Claude...</p>
    <a href="{safe_target}" class="btn">Перейти в Claude</a>
  </div>
</body>
</html>"""
        return HTMLResponse(html, headers={"Access-Control-Allow-Origin": "*"})

    @mcp.custom_route("/oauth/token", methods=["POST", "OPTIONS"])
    async def _oauth_token(request):
        import base64
        import hashlib
        import secrets
        import time
        from starlette.responses import JSONResponse, PlainTextResponse

        if request.method == "OPTIONS":
            return PlainTextResponse("", status_code=200, headers={"Access-Control-Allow-Origin": "*"})

        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            body = await request.json()
        else:
            form = await request.form()
            body = dict(form)

        grant_type = body.get("grant_type")
        code = body.get("code")
        client_id = body.get("client_id")
        client_secret = body.get("client_secret")
        code_verifier = body.get("code_verifier")

        if not client_secret:
            auth_header = request.headers.get("authorization", "")
            if auth_header.lower().startswith("basic "):
                try:
                    decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
                    cid, csec = decoded.split(":", 1)
                    if not client_id:
                        client_id = cid
                    client_secret = csec
                except Exception:
                    pass

        expected_client_id = os.getenv("MCP_CLIENT_ID", CFG.get("MCP_CLIENT_ID", ACTIVE_CLIENT_ID))

        if client_id and client_id != expected_client_id:
            return JSONResponse({"error": "invalid_client", "error_description": "Client ID mismatch"}, status_code=400, headers={"Access-Control-Allow-Origin": "*"})

        # Mandatory, never skipped when absent: the client_id is public, so a check that
        # only runs when a secret is sent hands the access token to anyone.
        if not (client_secret and ACTIVE_CLIENT_SECRET and secrets.compare_digest(client_secret, ACTIVE_CLIENT_SECRET)):
            return JSONResponse({"error": "invalid_client", "error_description": "Client authentication failed"}, status_code=401, headers={"Access-Control-Allow-Origin": "*"})

        if grant_type != "authorization_code":
            return JSONResponse({"error": "unsupported_grant_type", "error_description": "Only authorization_code is supported"}, status_code=400, headers={"Access-Control-Allow-Origin": "*"})

        if not code or code not in OAUTH_CODES:
            return JSONResponse({"error": "invalid_grant", "error_description": "Code expired or invalid"}, status_code=400, headers={"Access-Control-Allow-Origin": "*"})

        code_data = OAUTH_CODES.pop(code)
        if time.time() > code_data.get("expires_at", 0):
            return JSONResponse({"error": "invalid_grant", "error_description": "Code expired"}, status_code=400, headers={"Access-Control-Allow-Origin": "*"})

        redirect_uri = body.get("redirect_uri")
        if redirect_uri and redirect_uri != code_data.get("redirect_uri"):
            return JSONResponse({"error": "invalid_grant", "error_description": "redirect_uri mismatch"}, status_code=400, headers={"Access-Control-Allow-Origin": "*"})

        stored_challenge = code_data.get("code_challenge")
        if stored_challenge:
            pkce_ok = False
            if code_verifier and code_data.get("code_challenge_method", "S256") == "S256":
                calc = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode("utf-8")).digest()).decode("utf-8").rstrip("=")
                pkce_ok = secrets.compare_digest(calc, stored_challenge.rstrip("="))
            if not pkce_ok:
                return JSONResponse({"error": "invalid_grant", "error_description": "PKCE verification failed"}, status_code=400, headers={"Access-Control-Allow-Origin": "*"})

        return JSONResponse({
            "access_token": ACTIVE_MCP_TOKEN,
            "token_type": "Bearer",
            "expires_in": 31536000,
        }, headers={"Access-Control-Allow-Origin": "*"})




def _env() -> dict:
    cfg = {}
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    cfg.update({k: v for k, v in os.environ.items() if k.startswith("LMS_") or k.startswith("MCP_")})
    return cfg


CFG = _env()

client = httpx.Client(
    base_url=BASE,
    timeout=30,
    follow_redirects=True,
    headers={
        "User-Agent": CFG.get("LMS_UA", "Mozilla/5.0"),
        "Accept-Language": "ru-RU,ru;q=0.9",
    },
)
for _part in CFG.get("LMS_COOKIE", "").split(";"):
    if "=" in _part:
        _k, _v = _part.split("=", 1)
        client.cookies.set(_k.strip(), _v.strip(), domain="lms.mti.moscow")


def _save_cookie() -> None:
    """Переписать LMS_COOKIE в .env после успешного перелогина."""
    if not ENV.exists():
        return
    jar = "; ".join(f"{k}={v}" for k, v in client.cookies.items())
    lines = ENV.read_text(encoding="utf-8").splitlines()
    out = [f"LMS_COOKIE={jar}" if l.startswith("LMS_COOKIE=") else l for l in lines]
    ENV.write_text("\n".join(out) + "\n", encoding="utf-8")


def _login() -> None:
    login, pw = CFG.get("LMS_LOGIN"), CFG.get("LMS_PASSWORD")
    if not (login and pw):
        raise RuntimeError(
            "Сессия ЛМС истекла. Либо впиши свежую куку в LMS_COOKIE в .env, "
            "либо задай там LMS_LOGIN и LMS_PASSWORD — тогда сервер будет логиниться сам."
        )
    # The session is dead, so its cookies are too. Dropping them also keeps DDOS-Guard's
    # fresh __ddg*_ cookie (set for another domain) from sitting next to the stale one
    # under the same name, which makes client.cookies.items() raise CookieConflict.
    client.cookies.clear()
    r = client.post(
        "/user/login",
        data={"popupUsername": login, "popupPassword": pw, "currentUrl": BASE + "/"},
    )
    if _is_login_page(r.text):
        raise RuntimeError("Логин в ЛМС не прошёл: проверь LMS_LOGIN/LMS_PASSWORD в .env")
    _save_cookie()


def _is_login_page(html: str) -> bool:
    return "popupUsername" in html


def _get(path: str) -> httpx.Response:
    r = client.get(path)
    if _is_login_page(r.text):
        _login()
        r = client.get(path)
        if _is_login_page(r.text):
            raise RuntimeError("ЛМС не пускает даже после перелогина.")
    return r


def _post(path: str, **kw) -> httpx.Response:
    kw.setdefault("headers", {})["X-Requested-With"] = "XMLHttpRequest"
    r = client.post(path, **kw)
    if _is_login_page(r.text):
        _login()
        r = client.post(path, **kw)
    return r


def _soup(path: str) -> BeautifulSoup:
    s = BeautifulSoup(_get(path).text, "html.parser")
    for tag in s(["script", "style"]):
        tag.decompose()
    return s


def _t(node, sep: str = " ") -> str:
    """Текст узла со схлопнутыми пробелами."""
    raw = node.get_text("\n") if sep == "\n" else node.get_text(" ")
    lines = [re.sub(r"[ \t\xa0]+", " ", l).strip() for l in raw.split("\n")]
    return "\n".join(l for l in lines if l) if sep == "\n" else " ".join(lines).strip()


def _id(href: str) -> str:
    m = re.search(r"/(\d+)/?$", href or "")
    return m.group(1) if m else ""


@mcp.tool()
def schedule(limit: int = 20, kind: str = "academ") -> str:
    """Расписание ЛМС.

    kind: "academ" — занятия по датам (ближайшие первыми), "webinar" — вкладка вебинаров.
    limit — сколько строк вернуть.
    """
    s = _soup("/schedule/" + ("webinar" if kind == "webinar" else "academ"))
    table = s.find("table", class_="table-list")
    if not table:
        return "Расписание пустое."
    out, day, n = [], "", 0
    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if len(cells) == 1:
            day = _t(cells[0])
        elif len(cells) >= 2 and day:
            if n >= limit:
                break
            parts = [_t(c) for c in cells if _t(c)]
            out.append(f"{day}  " + "  ".join(parts))
            n += 1
    return "\n".join(out) if out else "Занятий в расписании нет."


@mcp.tool()
def courses(semester: int = 0) -> str:
    """Дисциплины семестра: id, название, вид контроля, баллы.

    semester — номер семестра; 0 (по умолчанию) — текущий.
    id из этого списка передаётся в course().
    """
    s = _soup("/student/up")
    blocks = s.find_all("tbody", class_="semester")
    picked = None
    for tb in blocks:
        head = tb.find("tr", class_="semtab")
        num = re.search(r"(\d+)", " ".join(tb.get("class")))
        is_current = bool(head and head.find("em"))
        if (semester == 0 and is_current) or (num and int(num.group(1)) == semester):
            picked = tb
            break
    if picked is None:
        return "Такого семестра нет."
    title = _t(picked.find("tr", class_="semtab"))
    out = [title]
    for tr in picked.find_all("tr", class_="discipl"):
        tds = [_t(td) for td in tr.find_all("td")]
        a = tr.find("a", href=True)
        cid = _id(a["href"]) if a else ""
        name = tds[1] if len(tds) > 1 else ""
        rest = " | ".join(x for x in tds[2:] if x)
        out.append(f"[{cid}] {name} — {rest}".rstrip(" —"))
    return "\n".join(out)


@mcp.tool()
def course(course_id: str) -> str:
    """Карточка дисциплины: преподаватель, темы, список заданий с дедлайнами и баллами.

    course_id — id из courses(). Задания идут с [event id] для assignment().
    """
    s = _soup(f"/lntools/versiongroupassign/contents/student/{course_id}")
    out = []
    h1 = s.find("h1")
    if h1:
        out.append(_t(h1))
    body = s.find("div", class_="inner-center") or s
    text = _t(body, sep="\n")
    for anchor in ("Преподавательский состав", "Учебные материалы"):
        i = text.find(anchor)
        if i != -1:
            out.append(text[i : i + 700].split("Контрольные итоговые")[0].strip())
            break
    for table in s.find_all("table", class_="table-list"):
        head = [_t(th) for th in table.find_all("th")]
        if "Мероприятие" not in head:
            continue
        out.append("\nЗадания и контрольные мероприятия:")
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            a = tr.find("a", href=True)
            eid = _id(a["href"]) if a else ""
            if not eid:  # строка «Все мероприятия» в подвале таблицы
                continue
            name, access, mx, res = (_t(td) for td in tds[:4])
            name = re.sub(r"\s+", " ", name)
            line = f"[{eid}] {name} — доступ {access}, макс {mx}"
            out.append(line + (f", результат {res}" if res else ", результата нет"))
    return "\n".join(out)


def _event_url(event_id: str) -> str:
    """Ссылка на мероприятие с учётом того, что /event/view только редиректит."""
    r = client.get(f"/event/view/{event_id}", follow_redirects=False)
    loc = r.headers.get("location", "")
    if "/user/login" in loc or _is_login_page(getattr(r, "text", "") or ""):
        _login()
        r = client.get(f"/event/view/{event_id}", follow_redirects=False)
        loc = r.headers.get("location", "")
    # /practicums/view/... закрыт для прямого захода, а /practicums/attempt/... открыт
    m = re.match(r"/practicums/view/(\d+)/\d+/0/\?groupPeriodId=(\d+)", loc)
    if m:
        loc = f"/practicums/attempt/{m.group(1)}/?groupPeriodId={m.group(2)}"
    return loc or f"/event/view/{event_id}"


def _event_page(event_id: str) -> BeautifulSoup:
    return _soup(_event_url(event_id))


@mcp.tool()
def assignment(event_id: str) -> str:
    """Полный текст задания и что по нему сдано.

    event_id — id мероприятия из course() или notifications().
    """
    s = _event_page(event_id)
    block = s.find("div", class_="content")
    if not block:
        return "Страница задания не открылась — возможно, мероприятие другого типа (тест, зачёт)."
    return _t(block, sep="\n")


@mcp.tool()
def grades() -> str:
    """Оценки: текущий контроль за семестр (ТКУ) и зачётная книжка целиком."""
    out = ["ТЕКУЩИЙ КОНТРОЛЬ (ТКУ)"]
    s = _soup("/student/tku")
    for table in s.find_all("table", class_="table-list"):
        for tr in table.find_all("tr"):
            cells = [_t(c) for c in tr.find_all(["th", "td"])]
            if any(cells):
                out.append(" | ".join(cells))
    out.append("\nЗАЧЁТНАЯ КНИЖКА")
    b = _soup("/student/book")
    for tb in b.find_all("tbody", class_="semester"):
        head = tb.find("tr", class_="semtab")
        if head:
            out.append("\n" + _t(head))
        for tr in tb.find_all("tr", class_="discipl"):
            cells = [_t(td) for td in tr.find_all("td")]
            cells = [c for c in cells if c and c != "Компетенции:"]
            if cells:
                out.append(" | ".join(cells))
    return "\n".join(out)


@mcp.tool()
def notifications() -> str:
    """Новые уведомления: проверенные работы, выставленные баллы, комментарии преподавателей."""
    s = _soup("/student/notifications")
    out = []
    for table in s.find_all("table", class_="table-list"):
        for tr in table.find_all("tr"):
            cells = [_t(c) for c in tr.find_all(["th", "td"])]
            if not any(cells):
                continue
            links = [a["href"] for a in tr.find_all("a", href=True)]
            eid = next((_id(h) for h in links if "/event/view/" in h), "")
            out.append(" | ".join(cells) + (f"  [event {eid}]" if eid else ""))
    return "\n".join(out) if out else "Новых уведомлений нет."


@mcp.tool()
def messages(message_id: str = "") -> str:
    """Личные сообщения: без аргумента — входящие, с message_id — текст письма."""
    if message_id:
        s = _soup(f"/messages/details/{message_id}")
        block = s.find("div", class_="content") or s.find("div", class_="inner-center")
        return _t(block, sep="\n") if block else "Сообщение не открылось."
    s = _soup("/messages/listing")
    out = []
    for table in s.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [_t(c) for c in tr.find_all(["th", "td"])]
            a = tr.find("a", href=re.compile(r"/messages/details/"))
            if a:
                out.append(f"[{_id(a['href'])}] " + " | ".join(c for c in cells if c))
    return "\n".join(out) if out else "Входящих нет."


def _tables(s: BeautifulSoup) -> str:
    """Все таблицы страницы построчно — для разделов, где содержимое и есть таблица."""
    out = []
    for table in s.find_all("table", class_="table-list"):
        for tr in table.find_all("tr"):
            cells = [_t(c) for c in tr.find_all(["th", "td"])]
            if any(cells):
                out.append(" | ".join(c for c in cells if c))
    return "\n".join(out)


@mcp.tool()
def finance() -> str:
    """Платежи: плановая стоимость по семестрам, оплачено, скидки, задолженность."""
    s = _soup("/finance")
    body = _tables(s)
    return body or "Раздел платежей пуст."


@mcp.tool()
def curriculum() -> str:
    """Учебный план: дисциплины по семестрам, вид контроля, часы, зачётные единицы."""
    return _tables(_soup("/student/curriculum")) or "Учебный план пуст."


@mcp.tool()
def announcements() -> str:
    """Объявления института."""
    s = _soup("/announce")
    block = s.find("div", class_="content")
    return _t(block, sep="\n") if block else "Объявлений нет."


@mcp.tool()
def dialog(kind: str = "curator") -> str:
    """Переписка: kind — "curator" (чат с куратором), "faculty" (вопрос преподавателю),
    "university-notifications" (уведомления института)."""
    if kind not in ("curator", "faculty", "university-notifications"):
        return "kind бывает только curator, faculty или university-notifications."
    s = _soup(f"/dialog/messages/0/0/{kind}")
    rows = _tables(s)
    return rows or "Переписки нет."


@mcp.tool()
def submit_assignment(
    event_id: str, text: str = "", file_path: str = "", confirm: bool = False
) -> str:
    """Отправить ответ на задание в ЛМС. НЕОБРАТИМО: после отправки попытку не изменить.

    Без confirm=True ничего не отправляет, а показывает, что именно уйдёт, — сначала показать
    это пользователю и получить от него явное «да», и только потом вызывать с confirm=True.

    event_id — id мероприятия из course(); file_path — путь к файлу; text — текст ответа.
    """
    url = _event_url(event_id)
    if "/practicums/attempt/" not in url:
        return f"Это мероприятие не принимает ответы файлом (ведёт на {url})."

    path = Path(file_path) if file_path else None
    if path and not path.is_file():
        return f"Файла нет: {file_path}"
    if not path and not text.strip():
        return "Нечего отправлять: нет ни файла, ни текста."

    head = _soup(url).find("h1")
    title = _t(head) if head else ""
    size = f"{path.stat().st_size / 1024:.0f} КБ" if path else "без файла"
    plan = (
        f"Задание: {title or event_id}\n"
        f"Файл: {path.name if path else '—'} ({size})\n"
        f"Текст ответа: {text.strip() or '—'}\n"
        f"Куда: {url}"
    )
    if not confirm:
        return plan + "\n\nНЕ ОТПРАВЛЕНО. Это необратимо — вызвать повторно с confirm=True."

    files_meta = []
    if path:
        with path.open("rb") as fh:
            up = _post(
                "/ajax/upload_files",
                data={"maxFileSize": "104857600", "controller": "practicums"},
                files={"openDialog[]": (path.name, fh)},
            )
        try:
            payload = up.json()
        except ValueError:
            return f"Загрузка файла не удалась, сервер ответил не JSON:\n{up.text[:300]}"
        files_meta = payload if isinstance(payload, list) else payload.get("files", [])
        if not files_meta:
            return f"Файл не принят: {str(payload)[:300]}"

    r = _post(url, data={"body": text, "files": json.dumps(files_meta, ensure_ascii=False)})
    try:
        res = r.json()
    except ValueError:
        return f"Ответ отправлен, но сервер вернул не JSON ({r.status_code}). Проверить в ЛМС."
    if res.get("errors"):
        return f"ЛМС не принял ответ: {res['errors']}"
    return plan + "\n\nОтправлено."


def create_app(token: str | None = None, transport: str = "http"):
    """ASGI-приложение FastMCP 4.0.3 с поддержкой Streamable HTTP (или SSE), CORS и Bearer-токена."""
    import hmac
    import urllib.parse
    from starlette.responses import PlainTextResponse

    global ACTIVE_MCP_TOKEN, ACTIVE_CLIENT_SECRET
    token = token or os.getenv("MCP_TOKEN", CFG.get("MCP_TOKEN"))
    client_secret = os.getenv("MCP_CLIENT_SECRET", CFG.get("MCP_CLIENT_SECRET"))
    # This app faces the internet. Without both secrets /mcp or /oauth/token would give
    # the whole LMS to anyone, so refuse to start rather than run open.
    if not (token and client_secret and TokenVerifier):
        raise RuntimeError("HTTP-режиму нужны MCP_TOKEN и MCP_CLIENT_SECRET в .env")
    ACTIVE_MCP_TOKEN, ACTIVE_CLIENT_SECRET = token, client_secret

    class BearerTokenVerifier(TokenVerifier):
        def __init__(self, expected: str):
            super().__init__()
            self.expected = expected

        async def verify_token(self, tok: str) -> AccessToken | None:
            if tok and hmac.compare_digest(tok, self.expected):
                return AccessToken(token=tok, client_id="mcp-client", scopes=[])
            return None

    mcp.auth = BearerTokenVerifier(token)

    # host_origin_protection=False необходимо при обращении через внешний домен или обратный прокси
    # stateless_http=True обеспечивает надёжную работу по HTTP без зависших стримов
    base_app = mcp.http_app(
        transport=transport,
        host_origin_protection=False,
        stateless_http=(transport == "http"),
    )

    class MCPHTTPMiddleware:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return

            method = scope.get("method", "")
            if method == "OPTIONS":
                res = PlainTextResponse(
                    "",
                    status_code=200,
                    headers={
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
                        "Access-Control-Allow-Headers": "*",
                    },
                )
                await res(scope, receive, send)
                return

            headers = list(scope.get("headers", []))
            headers_dict = dict(headers)
            query = urllib.parse.parse_qs(
                scope.get("query_string", b"").decode("utf-8", errors="ignore")
            )

            # Проброс токена из ?token= или X-MCP-Token в Authorization: Bearer
            has_auth = any(k.lower() == b"authorization" for k, _ in headers)
            if not has_auth:
                tok = (
                    query.get("token", [None])[0]
                    or headers_dict.get(b"x-mcp-token", b"").decode("utf-8", errors="ignore").strip()
                    or None
                )
                if tok:
                    headers.append((b"authorization", f"Bearer {tok}".encode()))
                    scope = dict(scope)
                    scope["headers"] = headers

            # Проброс session_id из query в заголовок mcp-session-id при необходимости
            has_sess = any(k.lower() == b"mcp-session-id" for k, _ in headers)
            if not has_sess:
                sess = (
                    query.get("session_id", [None])[0]
                    or query.get("mcp_session_id", [None])[0]
                    or query.get("mcp-session-id", [None])[0]
                )
                if sess:
                    headers.append((b"mcp-session-id", sess.encode()))
                    scope = dict(scope)
                    scope["headers"] = headers

            await self.app(scope, receive, send)

    return MCPHTTPMiddleware(base_app)


def run_server(
    host: str = "127.0.0.1",
    port: int = 8030,
    token: str | None = None,
    transport: str = "http",
) -> None:
    import uvicorn

    app = create_app(token=token, transport=transport)
    path = "/mcp" if transport == "http" else "/sse"
    print(f"Запуск lms-mcp FastMCP 4.0.3 на http://{host}:{port} ({transport.upper()}: http://{host}:{port}{path})")
    print("Авторизация: Bearer-токен для /mcp, client secret + PKCE для OAuth.")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LMS MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="MCP transport: stdio (локально), http (Streamable HTTP /mcp) или sse",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("MCP_HOST", "127.0.0.1"),
        help="Хост для биндинга (по умолчанию 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_PORT", "8030")),
        help="Порт для биндинга (по умолчанию 8030)",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("MCP_TOKEN", CFG.get("MCP_TOKEN")),
        help="Bearer-токен для защиты HTTP эндпоинта",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        run_server(host=args.host, port=args.port, token=args.token, transport=args.transport)


