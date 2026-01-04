# Champion Skin Voting App

A Flask web experience for browsing League of Legends champions, previewing every skin, and voting for your favorites. Splash art and skin metadata are pulled from Data Dragon on startup so the catalog stays complete.

## Feature showcase (for developers)
- **Always up-to-date catalog**: Startup sync checks every champion/skin and downloads any missing splash art and JSON metadata.
- **Skin voting**: Authenticated users can vote once per skin, with vote totals stored per skin.
- **Search & filtering**: Browse champions, view skin details, open modal splash previews, and jump to YouTube gameplay searches for any skin ("Champion SkinName SkinSpotlights").
- **Responsive Riot-inspired UI**: Shared layout, hero sections, modal previews, and cohesive light/dark themes with a user toggle.
- **Account management**: Registration with public usernames, login, email verification gating, and session-based access control for voting.
- **Player profiles**: Public usernames with private emails, selectable main champion, and personal favorites gallery.
- **Static JSON storage**: Votes, users, comments, favorites, and feedback are stored as JSON for simple deployments without a database.
- **Admin testing account**: Pre-provisioned admin user for quick QA (see below).
- **Leaderboard & stats**: Dedicated top-voted page plus sitewide champion/skin/vote/comment/favorite counts for quick health checks.
- **Comments with karma**: Champion threads with up/down voting per comment and author karma totals.
- **Admin dashboard**: Stats, verification mix, comment volume, karma leaderboard, inbox view for feedback/contact messages, and a guarded vote-reset tool with automatic backups.
- **Contact & feedback**: Dedicated forms for support/legal requests and product feedback, routed to the admin dashboard.
- **Compliance**: Legal page covering terms, privacy, cookies, and Riot attribution.

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
4. Open http://localhost:8080 to browse, vote, comment, and view About/Legal/Top/Admin pages.
5. Vote history persists across restarts; use the admin dashboard reset (with backup) when you need a clean slate.

## Admin/testing account
A verified admin/testing user is created automatically on startup if missing:
- **Email:** `abdallhhelles97@gmail.com`
- **Password:** `abdallhhelles..`

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
   - Register a new user, open the console log for the verification link, and verify the account.
   - Confirm login is blocked until verification is complete.
   - Log in with the admin testing account.
4. **Voting flow** –
   - Navigate to a champion page, open a skin, cast a vote with a verified account.
   - Attempt a second vote on the same skin (expect a "You already voted" error).
5. **Comments + karma** –
   - Add comments on a champion as a verified user, then up/down vote from another verified account.
   - Confirm scores update and karma totals change for the author.
6. **Admin dashboard** – Visit `/admin` with the admin user to confirm stats populate, comment counts render, and karma leaderboard orders correctly.
   - (Optional) Exercise the guarded vote reset by entering the provided code + admin email; confirm a backup file appears under `backups/`.
7. **Data persistence** – Restart the server and verify votes persist via `votes_db.json` and comments via `comments_db.json`.
8. **Content pages** – Visit `/about` and `/legal` to confirm copy renders.
9. **Profiles & favorites** – Update your username/main on `/profile`, favorite a few skins, and confirm they appear on your profile and public page `/u/<username>`.
10. **Contact & feedback** – Submit both forms and confirm entries appear in the admin dashboard inbox.
11. **Skin videos** – Open a champion page, click "Watch gameplay" on a skin, and verify YouTube opens with a `Champion SkinName SkinSpotlights` search.
12. **Theme toggle** – Switch between light and dark modes with the header toggle and reload to confirm persistence.
13. **Responsive UI** – Resize the browser (mobile/tablet/desktop) and ensure grids/cards adapt.

## Deployment checklist (public release)
- Set `FLASK_SECRET_KEY`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD` to production values.
- Run the app behind HTTPS with a reverse proxy (e.g., Nginx/Fly.io/Render) and disable debug mode.
- Pre-seed or mount persistent storage for `static/splash_arts/`, `users_db.json`, `votes_db.json`, and `comments_db.json`.
- Monitor startup logs for splash sync errors; rerun the sync script if needed.
- Review About/Legal copy for regional/legal requirements and Riot attribution.

## Tech stack
- Python 3.x
- Flask
- Requests (Data Dragon ingestion)
- JSON storage for users/votes
