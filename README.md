# Champion Skin Voting App

A Flask web experience for browsing League of Legends champions, previewing every skin, and voting for your favorites. Splash art and skin metadata are pulled from Data Dragon on startup so the catalog stays complete.

## Feature showcase (for developers)
- **Always up-to-date catalog**: Startup sync checks every champion/skin and downloads any missing splash art and JSON metadata.
- **Skin voting**: Authenticated users can vote once per skin, with vote totals stored per skin.
- **Search & filtering**: Browse champions, view skin details, and open modal splash previews.
- **Responsive Riot-inspired UI**: Shared layout, hero sections, modal previews, and consistent palette across pages.
- **Account management**: Registration, login, verification token storage, and session-based access control for voting.
- **Static JSON storage**: Votes and users are stored as JSON for simple deployments without a database.
- **Admin testing account**: Pre-provisioned admin user for quick QA (see below).
- **Leaderboard & stats**: Dedicated top-voted page plus sitewide champion/skin/vote counts for quick health checks.

## Quickstart
1. Create and activate a virtual environment, then install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. (Optional) Set environment overrides for production:
   ```bash
   export FLASK_SECRET_KEY="change-me"
   export ADMIN_EMAIL="admin@yourdomain"
   export ADMIN_PASSWORD="StrongPassword!"
   ```
3. Run the app:
   ```bash
   python app.py
   ```
4. Open http://localhost:8080 to browse, vote, and view About/Legal/Top pages.

## Admin/testing account
A verified admin/testing user is created automatically on startup if missing:
- **Email:** `admin@riftvote.test`
- **Password:** `TestAdmin#2024`

Override the email/password with `ADMIN_EMAIL` and `ADMIN_PASSWORD` environment variables for production.

## Startup splash sync
On every server start, `lol_splash_downloader.sync_splash_assets()`:
- Reads the latest champion roster and skin lists from Data Dragon.
- Ensures `static/splash_arts/<champion>/` exists with `skin_names.json`.
- Downloads any missing splash art images, skipping files that already exist.

You can also run it manually:
```bash
python lol_splash_downloader/splash_art_update.py
```

## Testing plan
1. **Dependency check** – `pip install -r requirements.txt` completes without errors.
2. **Static sync** – Start the app and confirm the startup log prints a splash sync summary; spot-check that new champion folders/images appear in `static/splash_arts/`.
3. **Authentication** –
   - Register a new user, verify login succeeds.
   - Log in with the admin testing account.
4. **Voting flow** –
   - Navigate to a champion page, open a skin, cast a vote.
   - Attempt a second vote on the same skin (expect a "You already voted" error).
5. **Data persistence** – Restart the server and verify votes and user sessions persist via `votes_db.json`/`users_db.json` contents.
6. **Content pages** – Visit `/about` and `/legal` to confirm copy renders.
7. **Responsive UI** – Resize the browser (mobile/tablet/desktop) and ensure grids/cards adapt.

## Deployment checklist (public release)
- Set `FLASK_SECRET_KEY`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD` to production values.
- Run the app behind HTTPS with a reverse proxy (e.g., Nginx/Fly.io/Render) and disable debug mode.
- Pre-seed or mount persistent storage for `static/splash_arts/`, `users_db.json`, and `votes_db.json`.
- Monitor startup logs for splash sync errors; rerun the sync script if needed.
- Review About/Legal copy for regional/legal requirements and Riot attribution.

## Tech stack
- Python 3.x
- Flask
- Requests (Data Dragon ingestion)
- JSON storage for users/votes
