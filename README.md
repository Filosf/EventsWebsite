# Wedding Event Registration

Django monolith for creating multilingual event pages and collecting RSVP responses.

## Features

- Django admin login and management UI.
- Two administrative access levels: staff and administrator.
- Audit log for critical administrative actions.
- Event translations for `ru`, `en`, and `he`.
- Public event pages with language switching and Hebrew RTL support.
- Protected RSVP form with attendance, guest count, email, phone, and comment.
- Basic page-view and unique-visitor analytics.
- Admin CSV export for registrations.
- Docker Compose for PostgreSQL, Redis, Django, and Caddy with automatic HTTPS.

## Local Setup

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.lock
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Open `http://127.0.0.1:8000/admin/`. The demo login is `admin@example.com` / `admin1`.

## Docker

```powershell
Copy-Item .env.example .env
# Replace SECRET_KEY and POSTGRES_PASSWORD in .env.
docker compose up --build
```

The app will be available at `http://127.0.0.1:8000/`.

Create the first administrator without putting the password in command history:

```powershell
$env:ADMIN_EMAIL = "admin@example.com"
$securePassword = Read-Host "Administrator password" -AsSecureString
$env:ADMIN_PASSWORD = [Net.NetworkCredential]::new("", $securePassword).Password
docker compose exec -e ADMIN_EMAIL -e ADMIN_PASSWORD web python manage.py bootstrap_admin
Remove-Item Env:ADMIN_EMAIL, Env:ADMIN_PASSWORD
```

`seed_demo` is intentionally blocked when `DEBUG=False`.

## Public Release

For the recommended managed deployment with Render PostgreSQL, Render Key Value,
Cloudflare R2, automatic TLS, and Git-driven releases, follow
[`docs/RENDER_DEPLOYMENT.md`](docs/RENDER_DEPLOYMENT.md).

Point the domain to the server and make ports 80 and 443 reachable. Set these
values in `.env` before starting Compose:

```dotenv
SITE_ADDRESS=events.example.com
HTTP_PORT=80
HTTPS_PORT=443
ALLOWED_HOSTS=events.example.com
CSRF_TRUSTED_ORIGINS=https://events.example.com
SECURE_SSL_REDIRECT=True
```

Caddy obtains and renews the TLS certificate automatically. After creating the
administrator, verify the complete production environment:

```powershell
docker compose exec web python manage.py release_preflight
Invoke-WebRequest https://events.example.com/healthz/
```

Application and proxy logs are written to stdout and can be collected with the
hosting platform or `docker compose logs`.

## Backup And Restore

Create a matched PostgreSQL and media backup with checksums:

```powershell
.\scripts\backup.ps1
```

Copy the resulting files from `backups/` to storage outside the server. Schedule
the script daily and retain multiple generations. Test restoration before release:

```powershell
.\scripts\restore.ps1 -BackupName wedding-events_YYYYMMDD_HHMMSS -IUnderstandThisWillOverwriteData
```

Restoration stops the web and proxy services, verifies checksums, replaces the
database and media volume, and then starts the application again.
