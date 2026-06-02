# Slack-ish — a self-hosted team chat

A lightweight, self-hostable team chat application (Slack clone) built from
scratch with **Django** and **React**. Real-time messaging, workspaces,
channels, DMs, threads, reactions, file uploads, mentions, search, presence,
and typing indicators — with zero mandatory external services.

## Features

- 🔐 **Auth** — register / login with hashed passwords + JWT sessions
- 🏢 **Workspaces** — create and switch between multiple workspaces
- 💬 **Channels** — public & private channels, join/leave, mute, unread badges
- 📨 **Direct messages** — 1:1 **and group** DMs
- 🧵 **Threads** — reply in-thread to any message
- 😀 **Reactions** — emoji reactions with a full searchable picker
- ✍️ **Rich text** — markdown: bold, italic, strike, `code`, code blocks, links
- 📌 **Pins & 🔖 saved items** — pin messages to a channel, bookmark for later
- ✏️ **Edit & delete** — edit or soft-delete your own messages
- 📎 **File uploads** — attach images and files to messages
- 🔔 **Mentions & notifications** — `@user` + `@here`/`@channel`/`@everyone`
- 🔍 **Search** — full message search across your channels
- 📹 **Group calls & screen share** — multi-party video/audio via a self-hosted
  LiveKit SFU, with screen sharing
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
| Calls      | LiveKit SFU + `livekit-client`; coturn for TURN         |
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

## Calls (group video + screen share)

Calling is powered by a self-hosted [LiveKit](https://livekit.io) SFU, included
in `docker-compose.yml`. With `docker compose up` you get a working LiveKit
server on port `7880`; the **📹 Call** button appears in every channel/DM
header. The first person starts a call, everyone else in that channel sees a
ring + a "Join call" button. Controls: mute, camera, **screen share**, leave.

How it fits together:

- The Django backend mints short-lived **LiveKit access tokens** (signed JWTs)
  at `POST /api/channels/:id/call/token`, gated by channel membership.
- The browser connects directly to the LiveKit SFU using that token; media
  (audio/video/screen) is relayed by the SFU — so it scales to many
  participants, unlike peer-to-peer mesh.
- A `call:state` event over the app's own WebSocket tells everyone who's
  currently in a call.

### Important deployment notes

- **Match the secrets.** `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` (backend env)
  must match the `keys:` in `infra/livekit.yaml`. Change them for production.
- **`LIVEKIT_WS_URL` must be reachable by the browser.** Locally
  `ws://localhost:7880` is fine. For a server, set it to your public address —
  and use **`wss://`** if the app is served over HTTPS (browsers block mixed
  content).
- **HTTPS is required for camera/mic** on any non-`localhost` origin — that's a
  browser rule (`getUserMedia`/`getDisplayMedia` need a secure context). Put the
  app and LiveKit behind TLS in production.
- **Open the media ports:** LiveKit uses UDP `50000-50100` (published in the
  compose file) plus `7881/tcp` as a fallback. `use_external_ip: true` in
  `infra/livekit.yaml` makes it advertise reachable candidates.

### TURN (coturn) for strict networks

When clients are behind strict NATs/firewalls, relay via a TURN server. A
`coturn` service is provided behind the `turn` profile:

```bash
docker compose --profile turn up
```

Then advertise it to clients by setting (in `.env`):

```bash
EXTRA_ICE_SERVERS=[{"urls":"turn:YOUR_HOST:3478","username":"slack","credential":"slackturnpassword"}]
```

Edit `infra/turnserver.conf` to set your public IP and a real credential.
(LiveKit also ships an embedded TURN — see the commented block in
`infra/livekit.yaml` — which is an alternative to running coturn.)

To disable calling entirely, set `CALLS_ENABLED=false`.

## Production HTTPS (Caddy)

Calls need a secure context (HTTPS) for camera/mic, and you'll want TLS for the
whole app anyway. A [Caddy](https://caddyserver.com) reverse proxy is included
that provisions and renews Let's Encrypt certificates automatically.

1. Point two DNS records at your server (Caddy serves both over one cert each):
   - `chat.example.com` → the app
   - `livekit.example.com` → LiveKit signaling
2. Create a `.env` (see `.env.example`):

   ```bash
   APP_DOMAIN=chat.example.com
   LIVEKIT_DOMAIN=livekit.example.com
   ACME_EMAIL=you@example.com

   DJANGO_SECRET_KEY=...                       # openssl rand -hex 32
   DJANGO_ALLOWED_HOSTS=chat.example.com
   DJANGO_CSRF_TRUSTED_ORIGINS=https://chat.example.com

   LIVEKIT_WS_URL=wss://livekit.example.com    # browser uses secure WS
   LIVEKIT_API_KEY=...                         # match infra/livekit.yaml
   LIVEKIT_API_SECRET=...                       # match infra/livekit.yaml
   ```
3. Start everything (app + LiveKit + Caddy):

   ```bash
   docker compose --profile tls up --build -d
   ```

Now `https://chat.example.com` serves the app, and calls connect over
`wss://livekit.example.com`. Make sure ports **80** and **443** (Caddy) plus
LiveKit's media ports — **UDP 50000-50100** and **TCP 7881** — are open on the
host firewall. Caddy only proxies the signaling WebSocket; media flows directly
to LiveKit on those ports, with `use_external_ip` advertising your public IP.

> Behind the proxy, Django reads `X-Forwarded-Proto` (configured via
> `SECURE_PROXY_SSL_HEADER`) so it correctly treats requests as HTTPS.

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
- `POST /api/channels/:id/call/token` — mint a LiveKit token (`{ ring: true }` to notify members)
- `POST /api/files` · `GET /api/files/:id`
- `GET /api/notifications` · `POST /api/notifications/read`

Real-time WebSocket at `/ws/?token=<jwt>`:

- inbound: `typing`, `subscribe`, `call:join`, `call:leave`, `ping`
- outbound: `message`, `message:edit`, `message:delete`, `reaction`, `typing`,
  `presence`, `presence:init`, `notification`, `call:ring`, `call:state`

## Tests

```bash
cd backend && . .venv/bin/activate
python manage.py test          # REST + realtime (WebSocket) tests
```

## License

MIT
