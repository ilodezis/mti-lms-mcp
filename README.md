<h1 align="center">mti-lms-mcp</h1>

<p align="center">
  <strong>Model Context Protocol (MCP) сервер для личного кабинета студента МТИ (lms.mti.moscow)</strong><br>
  <em>Connect any AI agent to your MTI student portal via standard MCP (stdio & HTTP)</em>
</p>

<p align="center">
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python: 3.10+"></a>
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-Supported-orange.svg" alt="MCP Supported"></a>
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg" alt="Platform">
</p>

<p align="center">
  <a href="#русская-версия">Русская версия</a> • 
  <a href="#english-version">English Version</a>
</p>

---

<a name="русская-версия"></a>
## 🌐 Русская версия

> ⚖️ **Дисклеймер:** Данный проект является независимой любительской разработкой и создан исключительно в ознакомительных, исследовательских и образовательных целях для интеграции персонального ИИ-ассистента. Проект **не является официальным** и **не аффилирован** с ОАНО ВО «МосТех» (Московский технологический институт / lms.mti.moscow) либо его подразделениями. Сервер не производит обход систем аутентификации, не модифицирует платформу и выполняет запросы исключительно в рамках стандартных прав текущей пользовательской сессии. Автор проекта не несёт ответственности за действия пользователей, возможные технические сбои, сетевые ограничения или академические последствия отправки учебных материалов. Пользователь использует инструмент под собственную ответственность.

### 📖 О проекте

**mti-lms-mcp** — открытый MCP-сервер, позволяющий подключить личный кабинет студента [lms.mti.moscow](https://lms.mti.moscow) напрямую к **любым ИИ-ассистентам, агентным средам и IDE**, поддерживающим стандарт **Model Context Protocol (MCP)**.

Сервер работает как локально (через универсальный транспорт **stdio**), так и удалённо (через **Streamable HTTP / SSE / OAuth** для Claude.ai).

#### Что умеет ассистент с этим сервером:
- 📅 **Расписание**: проверять пары, семинары и ссылки на вебинары.
- 📚 **Дисциплины и темы**: видеть список предметов текущего или любого семестра и текущий прогресс.
- 📝 **Задания и дедлайны**: читать полные формулировки практических, тестов и контрольных мероприятий, скачивать методички и проверять статус сдачи.
- 📊 **Оценки**: выгружать баллы текущего контроля успеваемости (ТКУ) и зачётную книжку за всё время обучения.
- 🔔 **Уведомления и сообщения**: отслеживать проверенные работы, выставленные баллы и переписку в ЛМС.
- 🎓 **Учебный план и финансы**: смотреть часы/ЗЕТ по дисциплинам и состояние оплаты обучения.
- 📤 **Безопасная сдача работ**: отправлять решения на проверку с обязательным подтверждением (`dry-run`).

---

### 🛠 Доступные инструменты (MCP Tools)

#### Чтение данных

| Инструмент | Параметры | Описание |
|---|---|---|
| `schedule` | `limit: int = 10`, `kind: str = ""` | Расписание занятий по датам. При `kind="webinar"` выводит расписание вебинаров. |
| `courses` | `semester: int = 0` | Список дисциплин семестра (0 — текущий) с ID и текущими баллами. |
| `course` | `course_id: str` | Карточка дисциплины: преподаватели, темы, контрольные мероприятия, дедлайны и `event_id`. |
| `assignment` | `event_id: str` | Полный текст задания, методические указания и статус текущей попытки сдачи. |
| `grades` | — | Баллы ТКУ за текущий семестр и полная зачётная книжка за все курсы. |
| `curriculum` | — | Официальный учебный план: перечень предметов, кафедры, часы и зачётные единицы (ЗЕТ). |
| `notifications` | — | Новые системные уведомления: проверенные работы, выставленные оценки и комментарии. |
| `messages` | `message_id: str = ""` | Входящие сообщения ЛМС (с указанием ID — полный текст конкретного письма). |
| `dialog` | `kind: str = "curator"` | Диалоги в ЛМС (`"curator"` — куратор, `"teacher"` — преподаватели, `"support"` — техподдержка). |
| `finance` | — | Финансовое состояние: начисления по семестрам, оплаченные суммы, скидки и баланс. |
| `announcements` | — | Официальные объявления института для студентов. |

#### Запись (Сдача работ)

| Инструмент | Параметры | Описание |
|---|---|---|
| `submit_assignment` | `event_id`, `text=""`, `file_path=""`, `confirm=False` | Отправка ответа на задание (файла и/или текста). |

> ⚠️ **Безопасность сдачи:** Отправка попытки в ЛМС МТИ **необратима** — после отправки работу нельзя отозвать или изменить.  
> Поэтому по умолчанию вызов без `confirm=True` выполняет **только сухой прогон (dry-run)**: ассистент показывает вам предпросмотр (название задания, файл, размер, текст ответа). Отправка на сервер происходит **исключительно при повторном вызове с флагом `confirm=True`** после вашего явного согласия.

---

### 🚀 Быстрый старт

#### 1. Клонирование и установка зависимостей

Требуется **Python 3.10+**.

```bash
git clone https://github.com/ilodezis/mti-lms-mcp.git
cd mti-lms-mcp

# Создание виртуального окружения
python -m venv .venv

# Активация окружения:
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (CMD):
.venv\Scripts\activate.bat
# macOS / Linux:
source .venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt
```

#### 2. Настройка авторизации (`.env`)

Скопируйте шаблон:
```bash
cp .env.example .env
```

В `.env` доступно два способа авторизации (выберите один):

- **Способ А (Автоматический, рекомендуется):**  
  Укажите свои логин и пароль от ЛМС:
  ```ini
  LMS_LOGIN=твой_логин
  LMS_PASSWORD=твой_пароль
  ```
  *Сервер авторизуется сам и будет автоматически обновлять сессию при её истечении.*

- **Способ Б (По сессионной куке):**  
  Если не хотите сохранять пароль в файле:
  1. Откройте [lms.mti.moscow](https://lms.mti.moscow) в браузере и войдите в аккаунт.
  2. Нажмите `F12` (инструменты разработчика) → вкладка **Console**.
  3. Введите:
     ```javascript
     copy(document.cookie)
     ```
  4. Вставьте полученную строку в `.env`:
     ```ini
     LMS_COOKIE=вставленная_строка_кук
     ```

#### 3. Проверка подключения

Запустите дымовой тест:
```bash
python test_lms.py
```
Скрипт запросит данные из ЛМС и проверит ключевые эндпоинты. В случае успеха в консоли будет: `всё зелёное`.

---

### 🔌 Подключение к любому ИИ-агенту (stdio)

Сервер полностью совместим со спецификацией **Model Context Protocol** и работает по стандартному транспорту `stdio`. Это означает, что его можно подключить к **абсолютно любому агенту, IDE или клиенту**, поддерживающему MCP.

#### Универсальный контракт подключения

Любой MCP-клиент ожидает три параметра:
1. `command`: путь к исполняемому файлу Python (`python` или путь к `.venv/bin/python` / `.venv/Scripts/python.exe`).
2. `args`: `["полный/путь/к/server.py", "--transport", "stdio"]`.
3. `env` (опционально): переменные окружения, если они не заданы в файле `.env`.

#### Готовые конфигурации для популярных клиентов:

<details>
<summary><b>1. Claude Desktop</b> (нажмите, чтобы развернуть)</summary>

Конфигурационный файл:
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "mti-lms": {
      "command": "/полный/путь/к/mti-lms-mcp/.venv/Scripts/python.exe",
      "args": ["/полный/путь/к/mti-lms-mcp/server.py", "--transport", "stdio"]
    }
  }
}
```
*(На macOS/Linux укажите `.venv/bin/python`).*
</details>

<details>
<summary><b>2. Cursor</b> (нажмите, чтобы развернуть)</summary>

В корне проекта создайте `.cursor/mcp.json` или откройте **Cursor Settings → Features → MCP**:

```json
{
  "mcpServers": {
    "mti-lms": {
      "command": "python",
      "args": ["/полный/путь/к/mti-lms-mcp/server.py", "--transport", "stdio"]
    }
  }
}
```
</details>

<details>
<summary><b>3. Windsurf</b> (нажмите, чтобы развернуть)</summary>

Конфиг `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "mti-lms": {
      "command": "/полный/путь/к/mti-lms-mcp/.venv/bin/python",
      "args": ["/полный/путь/к/mti-lms-mcp/server.py", "--transport", "stdio"]
    }
  }
}
```
</details>

<details>
<summary><b>4. Claude Code (CLI)</b> (нажмите, чтобы развернуть)</summary>

Добавьте сервер одной командой в терминале:

```bash
claude mcp add mti-lms -- /полный/путь/к/mti-lms-mcp/.venv/bin/python /полный/путь/к/mti-lms-mcp/server.py --transport stdio
```
</details>

<details>
<summary><b>5. VS Code (Cline / Roo Code / Continue)</b> (нажмите, чтобы развернуть)</summary>

В настройках расширения (MCP Servers settings):

```json
{
  "mcpServers": {
    "mti-lms": {
      "command": "python",
      "args": ["/полный/путь/к/mti-lms-mcp/server.py", "--transport", "stdio"],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```
</details>

<details>
<summary><b>6. Zed Editor</b> (нажмите, чтобы развернуть)</summary>

В настройках `settings.json`:

```json
{
  "context_servers": {
    "mti-lms": {
      "command": {
        "path": "/полный/путь/к/mti-lms-mcp/.venv/bin/python",
        "args": ["/полный/путь/к/mti-lms-mcp/server.py", "--transport", "stdio"]
      }
    }
  }
}
```
</details>

<details>
<summary><b>7. Goose, LibreChat, Cherry Studio, OpenCode и другие</b> (нажмите, чтобы развернуть)</summary>

Во всех остальных клиентах указывайте:
- **Type / Transport**: `stdio`
- **Command**: `python` (или путь к Python в виртуальном окружении)
- **Args**: `["/полный/путь/к/server.py", "--transport", "stdio"]`
- **Working Directory**: `/полный/путь/к/mti-lms-mcp/`
</details>

---

### 🌐 Удалённый запуск (HTTP / SSE / Docker для Claude.ai)

Для работы с веб-интерфейсом **Claude.ai** (через Custom Connectors) или удалённым сервером `mti-lms-mcp` поднимается в режиме веб-сервиса с поддержкой авторизации RFC 8414 / RFC 9728.

> ℹ️ **Сетевые ограничения:** ЛМС МТИ защищена DDOS-Guard и сбрасывает запросы с зарубежных дата-центров. Разворачивайте сервер на машине с **российским IP** (домашний сервер/ПК, роутер или РФ VPS).

#### 1. Задайте токены в `.env`

```ini
MCP_TRANSPORT=http
MCP_HOST=0.0.0.0
MCP_PORT=8030

# Сгенерируйте случайные ключи (например: python -c "import secrets; print(secrets.token_urlsafe(32))"):
MCP_TOKEN=твой_секретный_токен_bearer
MCP_CLIENT_ID=mti-lms
MCP_CLIENT_SECRET=твой_секретный_токен_oauth
```

#### 2. Запуск через Docker

```bash
docker compose up -d --build
```
Сервер слушает на `127.0.0.1:8030`.

#### 3. Подключение в Claude.ai

1. Опубликуйте сервис наружу по HTTPS (например, через Cloudflare Tunnel, Caddy, Nginx или Traefik).
2. В веб-интерфейсе Claude.ai перейдите в **Settings → Integrations → Add Custom Connector**:
   - **Server URL:** `https://твой-домен/mcp`
   - **Client ID:** `mti-lms` (из `MCP_CLIENT_ID`)
   - **Client Secret:** значение `MCP_CLIENT_SECRET` из `.env`
3. Нажмите **Connect** — откроется 1-клик окно подтверждения авторизации.

---

### 🔒 Безопасность и приватность

- **100% локальное хранение данных:** Ваши пароли, куки и токены хранятся **только на вашем устройстве** в файле `.env`. Файл закрыт в `.gitignore` и никогда не передаётся во внешние сервисы.
- **Двухэтапная отправка:** Случайная сдача работ невозможна — инструмент требует явного подтверждения пользователя перед выполнением POST-запроса.
- **Чистый парсинг:** Все данные запрашиваются напрямую с `lms.mti.moscow` под вашей сессией без сторонних прокси-серверов.

---

<a name="english-version"></a>
## 🌐 English Version

> ⚖️ **Disclaimer:** This project is an independent open-source tool developed exclusively for educational, personal productivity, and research purposes. It is **not an official tool** and is **not affiliated with, endorsed by, or connected to** OANO VO "MosTech" (Moscow Technological Institute / lms.mti.moscow) or any of its subsidiaries. The server does not bypass platform security, access unauthorized data, or modify university systems. It strictly operates within the permissions of the authenticated user's session. The author assumes no responsibility or liability for how this software is used, any session/network restrictions, or any academic consequences resulting from assignment submissions. Use at your own discretion and risk.

### 📖 Overview

**mti-lms-mcp** is an open-source Model Context Protocol (MCP) server that connects the Moscow Technological Institute student portal ([lms.mti.moscow](https://lms.mti.moscow)) directly to **any AI agent, agentic workflow, or IDE** supporting the **MCP standard**.

It supports both local **stdio transport** (for desktop applications) and **Streamable HTTP / SSE with OAuth 2.0 PKCE** (for web clients like Claude.ai).

#### Capabilities:
- 📅 **Schedule & Webinars**: Check upcoming classes, lectures, seminars, and live webinar URLs.
- 📚 **Courses & Syllabi**: Browse subjects across any semester with grading progress.
- 📝 **Assignments & Deadlines**: Inspect full assignment prompts, deadlines, download study materials, and check previous attempts.
- 📊 **Grades & Transcripts**: Retrieve continuous evaluation points and complete official gradebook records.
- 🔔 **Notifications & Messages**: Track graded homework, instructor feedback, and internal LMS messages.
- 📤 **Safe Homework Submission**: Send solutions (text/file) with mandatory dry-run verification.

---

### 🛠 MCP Tools

#### Read Operations

| Tool | Parameters | Description |
|---|---|---|
| `schedule` | `limit: int = 10`, `kind: str = ""` | List classes by date. Pass `kind="webinar"` for webinar schedule. |
| `courses` | `semester: int = 0` | List courses for a semester (0 = current) with IDs and current scores. |
| `course` | `course_id: str` | Course card: professors, topics, assignments, deadlines, and `event_id`. |
| `assignment` | `event_id: str` | Full prompt, instructions, attached guidelines, and submission status. |
| `grades` | — | Current term grades and complete academic record. |
| `curriculum` | — | Official curriculum: discipline list, departments, study hours, and ECTS credits. |
| `notifications` | — | Notification feed: graded submissions, review remarks, score updates. |
| `messages` | `message_id: str = ""` | Inbox messages (pass message ID for full body). |
| `dialog` | `kind: str = "curator"` | Chat threads (`"curator"`, `"teacher"`, `"support"`). |
| `finance` | — | Tuition billing, semester payments, applied discounts, balance. |
| `announcements` | — | Official university bulletin announcements. |

#### Write Operations

| Tool | Parameters | Description |
|---|---|---|
| `submit_assignment` | `event_id`, `text=""`, `file_path=""`, `confirm=False` | Submit an assignment response (file and/or text). |

> ⚠️ **Submission Safety:** Submissions to MTI LMS cannot be revoked or edited once sent.  
> Therefore, calling `submit_assignment` without `confirm=True` performs a **dry run only**, previewing the target event, attached file, size, and message. Live submission occurs **only when explicitly invoked with `confirm=True`**.

---

### 🚀 Quick Start

#### 1. Clone & Setup

Requires **Python 3.10+**.

```bash
git clone https://github.com/ilodezis/mti-lms-mcp.git
cd mti-lms-mcp

# Create virtual environment
python -m venv .venv

# Activate:
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### 2. Authentication Setup (`.env`)

Copy the template:
```bash
cp .env.example .env
```

Choose one of two authentication options:

- **Option A: Login & Password (Recommended)**  
  Provide LMS credentials in `.env`:
  ```ini
  LMS_LOGIN=your_username
  LMS_PASSWORD=your_password
  ```
  *The server automatically signs in and handles session renewal upon expiration.*

- **Option B: Session Cookie**  
  If you prefer not storing passwords:
  1. Log into [lms.mti.moscow](https://lms.mti.moscow) in your browser.
  2. Open DevTools (`F12`) → **Console**.
  3. Execute: `copy(document.cookie)`
  4. Paste into `.env`:
     ```ini
     LMS_COOKIE=pasted_cookie_string
     ```

#### 3. Verification

Run the smoke test:
```bash
python test_lms.py
```

---

### 🔌 Connecting to Any AI Agent (stdio)

The server conforms to the **Model Context Protocol specification** using standard I/O (`stdio`). It can be hooked into **any MCP-compliant tool, agentic runtime, or IDE**.

#### Generic MCP JSON Configuration

```json
{
  "mcpServers": {
    "mti-lms": {
      "command": "/path/to/mti-lms-mcp/.venv/bin/python",
      "args": ["/path/to/mti-lms-mcp/server.py", "--transport", "stdio"]
    }
  }
}
```

#### Client Configuration Snippets:

- **Claude Desktop:** Add entry to `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS).
- **Cursor:** Configure `.cursor/mcp.json` or add in **Settings → MCP**.
- **Windsurf:** Add to `~/.codeium/windsurf/mcp_config.json`.
- **Claude Code CLI:** Run `claude mcp add mti-lms -- /path/to/.venv/bin/python /path/to/server.py --transport stdio`.
- **VS Code Extensions (Cline / Roo Code / Continue):** Paste into MCP server configuration panel.
- **Zed Editor:** Add under `context_servers` in `settings.json`.

---

### 🌐 Remote Deployment (Docker & Claude.ai)

To connect from the **Claude.ai Web UI**:

1. Fill required secrets in `.env`:
   ```ini
   MCP_TRANSPORT=http
   MCP_HOST=0.0.0.0
   MCP_PORT=8030
   MCP_TOKEN=generate_random_secret_token
   MCP_CLIENT_ID=mti-lms
   MCP_CLIENT_SECRET=generate_random_secret_token
   ```
2. Start container:
   ```bash
   docker compose up -d --build
   ```
3. Expose via HTTPS (Cloudflare Tunnel, Caddy, Nginx).
4. In Claude.ai: **Settings → Integrations → Add Custom Connector** with your server URL, client ID, and secret.

*(Note: MTI LMS enforces DDOS-Guard protection; run the server on a Russian residential or VPS IP).*

---

### 📄 License

Distributed under the [MIT License](LICENSE).
