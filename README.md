# Shubhdra Imitation Jawellary - Website

Flask + SQLite (PostgreSQL-ready). Catalogue, wholesale enquiries, admin panel at `/admin`.

## Run locally
    python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
    pip install Flask Flask-SQLAlchemy
    export ADMIN_PASSWORD='YourStrongPassword'            # Windows: set ADMIN_PASSWORD=...
    export FLASK_APP=app.py
    flask init-db                                         # creates tables, categories, demo products, admin user
    flask run                                             # http://127.0.0.1:5000  (admin: /admin, user: admin)

## Deploy (PythonAnywhere free/low cost, or Render)
1. Upload the project (git or zip). Create venv, `pip install -r requirements.txt`.
2. Set env vars from `.env.example` (SECRET_KEY random, FLASK_ENV=production, ADMIN_PASSWORD, SITE_URL).
3. Run `flask init-db` once. Point the WSGI file at `app:app` (Render: start command `gunicorn app:app`).
4. Keep `static/uploads` and `si.db` on persistent storage (PythonAnywhere disk is persistent; Render free disk is NOT, so use a paid disk or PostgreSQL + a cloud storage later).
5. Buy the domain from a registrar yourself (not automatic). Add the DNS records your host shows: CNAME `www` -> host address; redirect the bare domain to `www` at the registrar. HTTPS is issued by the host (one click on PythonAnywhere/Render).
6. Update later: replace changed files, reload the app. Products need no code changes.
7. Backup: copy `si.db` and `static/uploads/` regularly (e.g. `cp si.db backup-$(date +%F).db`).

## Replace with real info (Admin > Website)
WhatsApp number, phone, Instagram URL, shop address, about text, banner photo. Delete DEMO products after adding real ones.
