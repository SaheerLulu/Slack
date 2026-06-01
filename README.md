# Slack-ish — a self-hosted team chat

A lightweight, self-hostable team chat application (Slack clone) built from
scratch with **Django** and **React**. Real-time messaging, workspaces,
channels, DMs, threads, reactions, file uploads, mentions, search, presence,
and typing indicators — with zero mandatory external services.

## Features

- 🔐 **Auth** — register / login with hashed passwords + JWT sessions
- 🏢 **Workspaces** — create and switch between multiple workspaces
- 💬 **Channels** — public & private channels, join/leave, unread badges
- 📨 **Direct messages** — 1:1 conversations
- 🧵 **Threads** — reply in-thread to any message
- 😀 **Reactions** — emoji reactions on messages
- ✏️ **Edit & delete** — edit or soft-delete your own messages
- 📎 **File uploads** — attach images and files to messages
- 🔔 **Mentions & notifications** — `@mention` people, get notified
- 🔍 **Search** — full message search across your channels
- ⚡ **Real-time** — messages, presence, and typing over WebSockets
- 🟢 **Presence** — see who's online
- 🐳 **Self-host** — one `docker compose up`, data in a mounted volume

## Tech stack

| Layer      | Choice                                                  |
|------------|---------------------------------------------------------|
| Backend    | Django, Django REST Framework, **Django Channels** (ASGI)|
| Real-time  | WebSockets via Channels (in-memory layer; Redis optional)|
| Database   | SQLite by default; Postgres via `DATABASE_URL`          |
| Auth       | JWT (`djangorestframework-simplejwt`)                   |
| Frontend   | React + Vite + Zustand                                  |
| Server     | daphne (ASGI) + WhiteNoise (static)                     |
| Deploy     | Docker / docker-compose                                 |

No Redis or message broker is required for single-process self-hosting — the
whole thing runs as one ASGI process plus a SQLite file. Redis and Postgres are
opt-in for scaling.

## Quick start (Docker)

```bash
# from the repo root
JWT=$(openssl rand -hex 32)
DJANGO_SECRET_KEY=$JWT docker compose up --build
```

Open http://localhost:8000 and register an account. The SQLite database and
uploaded files are persisted to `./data` on the host.

## Quick start (local dev)

You need Python 3.11+ and Node.js 18+.

```bash
# 1. Backend (terminal 1)
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver        # ASGI dev server on :8000

# 2. Frontend (terminal 2)
cd frontend
npm install
npm run dev                       # Vite on :5173, proxies /api + /ws to :8000
```

Open http://localhost:5173.

## Production build (without Docker)

```bash
cd frontend && npm install && npm run build      # outputs frontend/dist
cp -r frontend/dist backend/frontend_dist        # SPA served by the backend

cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
DJANGO_SECRET_KEY=change-me daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

The backend serves the built SPA (and `/api` + `/ws`) on a single port.

## Configuration

Environment variables (see `.env.example`):

| Variable                | Default                    | Description                                   |
|-------------------------|----------------------------|-----------------------------------------------|
| `DJANGO_SECRET_KEY`     | `dev-insecure-secret-…`    | **Set this in production!**                   |
| `DJANGO_DEBUG`          | `false`                    | Enable Django debug mode                      |
| `DJANGO_ALLOWED_HOSTS`  | `*`                        | Comma-separated allowed hosts                 |
| `DATA_DIR`              | `backend/data` / `/data`   | SQLite DB + uploaded media location           |
| `DATABASE_URL`          | —                          | Use Postgres instead of SQLite                |
| `REDIS_URL`             | —                          | Use Redis for the Channels layer (scaling)    |
| `MAX_UPLOAD_BYTES`      | `26214400` (25MB)          | Max attachment size                           |

### Scaling with Postgres + Redis

```bash
DATABASE_URL=postgres://slack:slack@postgres:5432/slack \
REDIS_URL=redis://redis:6379/0 \
DJANGO_SECRET_KEY=$(openssl rand -hex 32) \
docker compose --profile postgres --profile redis up --build
```

> Note: the default in-memory Channels layer only works within a single
> process. To run multiple workers/replicas you **must** set `REDIS_URL`.

## Project layout

```
.
├── backend/                 # Django project
│   ├── config/              # settings, urls, asgi/wsgi
│   └── chat/                # the app
│       ├── models.py        # User, Workspace, Channel, Message, …
│       ├── views.py         # REST endpoints
│       ├── serializers.py
│       ├── consumers.py     # WebSocket consumer (presence, delivery)
│       ├── middleware.py    # JWT auth for WebSockets
│       ├── events.py        # broadcast helpers (group_send)
│       └── tests.py / test_realtime.py
├── frontend/                # React + Vite SPA
│   └── src/
│       ├── store.js         # Zustand store
│       ├── ws.js            # reconnecting WebSocket client
│       ├── api/client.js    # fetch wrapper with JWT refresh
│       ├── pages/           # Login, Chat
│       └── components/      # Sidebar, Message, Composer, ThreadPanel, …
├── Dockerfile               # multi-stage: build SPA → serve via daphne
└── docker-compose.yml
```

## API overview

REST (all under `/api`, JWT via `Authorization: Bearer <token>`):

- `POST /api/auth/register` · `POST /api/auth/login` · `POST /api/auth/refresh` · `GET /api/auth/me`
- `GET/POST /api/workspaces` · `POST /api/workspaces/:id/join` · `GET /api/workspaces/:id/members`
- `GET/POST /api/workspaces/:id/channels` · `POST /api/workspaces/:id/dm/:userId`
- `GET /api/workspaces/:id/search?q=`
- `POST /api/channels/:id/join` · `GET /api/channels/:id/members` · `POST /api/channels/:id/read`
- `GET/POST /api/channels/:id/messages`
- `PATCH/DELETE /api/messages/:id` · `GET /api/messages/:id/thread` · `PUT/DELETE /api/messages/:id/reactions`
- `POST /api/files` · `GET /api/files/:id`
- `GET /api/notifications` · `POST /api/notifications/read`

Real-time WebSocket at `/ws/?token=<jwt>`:

- inbound: `{ type: "typing", channelId }`, `{ type: "subscribe", channelId }`, `{ type: "ping" }`
- outbound: `message`, `message:edit`, `message:delete`, `reaction`, `typing`, `presence`, `presence:init`, `notification`

## Tests

```bash
cd backend && . .venv/bin/activate
python manage.py test          # REST + realtime (WebSocket) tests
```

## License

MIT
