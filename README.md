# auth-service

[![CI](https://github.com/GlowyStar/auth-service/actions/workflows/ci.yml/badge.svg)](https://github.com/GlowyStar/auth-service/actions/workflows/ci.yml)

An authentication microservice for apps that sign users up by email. It confirms the
address with one-time codes, issues short-lived JWT access tokens together with rotating
refresh tokens, detects a stolen refresh token by its reuse, and resets passwords by code.
Durable state (users, refresh tokens) lives in PostgreSQL; short-lived security state
(codes, login counters, revoked access tokens) lives in Redis with TTLs. FastAPI, async
SQLAlchemy 2, Alembic, Redis, typed with strict mypy and tested against real databases.

## Features

- Sign-up by email and password; the account stays inactive until the email is confirmed.
- One-time codes: 6 digits from `secrets`, stored as an HMAC digest in Redis for 5 minutes,
  5 attempts and the code burns, single use, 60-second resend cooldown.
- Login with a JSON body or the OAuth2 password form (the Swagger "Authorize" button works).
- Failed logins limited per email and per client IP.
- Access token: HS256 JWT, 15 minutes. Refresh token: opaque, 30 days, rotated on every use,
  reuse of an old one revokes the whole token family.
- Logout revokes the refresh family and deny-lists the access token until it expires.
- Password reset by one-time code; a reset ends every session of the user.
- `/me` profile read and update.
- Mail through one small interface: a console sender for development and tests, an SMTP
  sender (aiosmtplib) for real delivery.

## Architecture

```mermaid
flowchart LR
    client([Client]) -->|HTTP| api
    subgraph service [auth-service]
        api[API routers<br/>FastAPI] --> rules[AuthService<br/>business rules]
        rules --> repos[Repositories<br/>SQLAlchemy async]
        rules --> stores[Redis stores<br/>codes, login limits, deny-list]
        rules --> mailer[EmailSender<br/>console or SMTP]
    end
    repos --> pg[(PostgreSQL<br/>users, refresh tokens)]
    stores --> redis[(Redis)]
    mailer --> smtp[SMTP server]
```

Routers only translate HTTP, the service holds the rules and raises domain errors (mapped
to status codes in one handler), repositories and Redis stores only read and write.

### Refresh rotation and reuse detection

```mermaid
sequenceDiagram
    participant U as Client
    participant X as Attacker
    participant S as auth-service
    participant DB as PostgreSQL

    U->>S: POST /auth/refresh (R1)
    S->>DB: lock the row of sha256(R1) FOR UPDATE
    S->>DB: mark R1 used, insert R2 in the same family
    S-->>U: new access token + R2

    X->>S: POST /auth/refresh (stolen R1)
    S->>DB: R1 is already used
    S->>DB: revoke every token of the family
    S-->>X: 401 refresh token was already used

    U->>S: POST /auth/refresh (R2)
    S-->>U: 401, the family is revoked, log in again
```

## API

| Method | Path | Auth | Body | Result |
|---|---|---|---|---|
| POST | `/auth/signup` | | `email`, `password` | 201 user, confirmation code mailed |
| POST | `/auth/confirm` | | `email`, `code` | 204, account active |
| POST | `/auth/confirm/resend` | | `email` | 202, or 429 during the cooldown |
| POST | `/auth/login` | | `email`, `password` (JSON) | 200 token pair |
| POST | `/auth/token` | | `username`, `password` (form) | 200 token pair (OAuth2, Swagger) |
| POST | `/auth/refresh` | | `refresh_token` | 200 new token pair |
| POST | `/auth/logout` | Bearer | | 204 |
| POST | `/auth/password/forgot` | | `email` | 202 (always) |
| POST | `/auth/password/reset` | | `email`, `code`, `new_password` | 204 |
| GET | `/me` | Bearer | | 200 profile |
| PATCH | `/me` | Bearer | `full_name` | 200 profile |

A token pair is `{access_token, refresh_token, token_type, expires_in}`. Errors are
`{"detail": "..."}` with 400 (bad code), 401, 403 (email not confirmed), 409 (email taken),
422 (validation) or 429 (cooldown, too many failed logins). Interactive docs: `/docs`.

## Security decisions

| Decision | Why |
|---|---|
| Argon2 (pwdlib) for passwords, hashed in a worker thread | Memory-hard hash; tens of milliseconds of CPU would otherwise stall the event loop. |
| Unknown email still verifies a dummy hash | A login takes the same time whether the account exists. |
| Refresh tokens stored in PostgreSQL | They live for 30 days and carry security state (used, revoked, family). They must survive a Redis restart or eviction, revoking a family or a user is one indexed `UPDATE`, and a row lock (`SELECT ... FOR UPDATE`) makes rotation safe under concurrent requests. |
| Refresh tokens are opaque, only their SHA-256 is stored | A database leak gives no usable tokens; 256 random bits make a fast hash enough. |
| Rotation with reuse detection | A refresh token works once. A second use means a copy exists, so the whole family (one login) is revoked. |
| Access JWT carries `jti` and `sid` (the family id) | Requests are checked without a database hit; logout needs only the bearer token. |
| Deny-list of access `jti` in Redis, TTL = time left | Logout takes effect at once, and entries expire together with the token. |
| Codes as HMAC-SHA256 digests keyed by the secret | A million possible codes are trivial to brute force from a plain hash; the key never leaves the app. |
| 5 attempts per code, then it burns; codes bound to purpose and email | Caps online guessing; a confirmation code cannot reset a password. |
| Resend cooldown applies to unknown emails; forgot always answers 202 | These endpoints do not reveal which emails are registered. Sign-up does answer 409 for a taken email, a usual usability trade-off. |
| Failed logins: 5 per email, 20 per IP, per 15 minutes | Slows guessing against one account and spraying from one address. |
| Password reset revokes all refresh tokens | A reset after a compromise logs the attacker out. |

Known limits: access tokens issued before a logout or a reuse detection stay valid until
they expire (15 minutes at most); expired refresh token rows are not purged by the service
(a periodic `DELETE ... WHERE expires_at < now()` does it); behind a reverse proxy set
uvicorn's `FORWARDED_ALLOW_IPS` so the per-IP limit sees the real client address.

## Run

```bash
cp .env.example .env    # put a real SECRET_KEY in it: openssl rand -hex 32
docker compose up --build
```

The API listens on http://localhost:8000 (docs at `/docs`). The container applies the
migrations on start (`alembic upgrade head`). With the console mail backend the codes are
printed to `docker compose logs api`.

Without Docker for the API:

```bash
docker compose up -d postgres redis
uv sync
uv run alembic upgrade head
uv run uvicorn auth_service.main:app --reload
```

## Test

```bash
docker compose up -d postgres redis
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

The tests run through the ASGI app against real PostgreSQL and Redis. They create and
migrate a separate `auth_test` database and use Redis database 1, so development data is
left alone. CI runs the same commands with Postgres and Redis as job services.

## Configuration

Environment variables (or `.env`):

| Variable | Default | Meaning |
|---|---|---|
| `SECRET_KEY` | required, 32+ chars | Signs access tokens and keys the code digests. |
| `DATABASE_URL` | `postgresql+asyncpg://auth:auth@localhost:5432/auth` | PostgreSQL (asyncpg driver). |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis. |
| `ACCESS_TOKEN_TTL_SECONDS` | `900` | Access token lifetime. |
| `REFRESH_TOKEN_TTL_DAYS` | `30` | Refresh token lifetime. |
| `EMAIL_BACKEND` | `console` | `console` prints mail to stdout, `smtp` sends it. |
| `EMAIL_FROM` | `no-reply@example.com` | Sender address. |
| `SMTP_HOST`, `SMTP_PORT` | `localhost`, `587` | SMTP server; STARTTLS is used when offered. |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | unset | SMTP credentials. |

## Layout

```
src/auth_service/
  main.py           app, lifespan, domain error to HTTP status mapping
  api/              routers and dependencies (HTTP only)
  service.py        AuthService: the business rules
  repositories.py   PostgreSQL access
  redis_stores.py   one-time codes, login counters, access token deny-list
  security.py       password hashing, JWT
  mailer.py         console and SMTP senders
  models.py         SQLAlchemy models
  schemas.py        request and response models
  settings.py       configuration
migrations/         Alembic
tests/
```
