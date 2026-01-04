import os
import csv
import json
import uuid
from io import StringIO

import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
from werkzeug.security import generate_password_hash, check_password_hash

from lol_splash_downloader.splash_art_update import sync_splash_assets

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_secret_key_here')

ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'abdallhhelles97@gmail.com').lower()
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'abdallhhelles')
FEEDBACK_DB_FILE = 'feedback_db.json'

USERS_DB_FILE = 'users_db.json'
VOTES_DB_FILE = 'votes_db.json'  # Store votes per skin, including who voted
COMMENTS_DB_FILE = 'comments_db.json'
CHAMPION_LORE_CACHE = 'champion_lore_cache.json'

def load_users():
    if not os.path.exists(USERS_DB_FILE):
        with open(USERS_DB_FILE, 'w') as f:
            json.dump({}, f)
        return {}
    with open(USERS_DB_FILE, 'r') as f:
        return json.load(f)

def save_users(users):
    with open(USERS_DB_FILE, 'w') as f:
        json.dump(users, f, indent=4)

def load_votes():
    if not os.path.exists(VOTES_DB_FILE):
        # Create empty votes file if missing
        with open(VOTES_DB_FILE, 'w') as f:
            json.dump({}, f)
        return {}
    with open(VOTES_DB_FILE, 'r') as f:
        return json.load(f)

def save_votes(votes):
    with open(VOTES_DB_FILE, 'w') as f:
        json.dump(votes, f, indent=4)


def load_comments():
    if not os.path.exists(COMMENTS_DB_FILE):
        with open(COMMENTS_DB_FILE, 'w') as f:
            json.dump({}, f)
        return {}
    with open(COMMENTS_DB_FILE, 'r') as f:
        return json.load(f)


def save_comments(comments):
    with open(COMMENTS_DB_FILE, 'w') as f:
        json.dump(comments, f, indent=4)


def load_feedback():
    if not os.path.exists(FEEDBACK_DB_FILE):
        with open(FEEDBACK_DB_FILE, 'w') as f:
            json.dump([], f)
        return []
    with open(FEEDBACK_DB_FILE, 'r') as f:
        return json.load(f)


def save_feedback(entries):
    with open(FEEDBACK_DB_FILE, 'w') as f:
        json.dump(entries, f, indent=4)


def load_lore_cache():
    if not os.path.exists(CHAMPION_LORE_CACHE):
        return {}
    with open(CHAMPION_LORE_CACHE, 'r') as f:
        return json.load(f)


def save_lore_cache(cache):
    with open(CHAMPION_LORE_CACHE, 'w') as f:
        json.dump(cache, f, indent=2)

# Load users and votes into memory
users = load_users()
votes = load_votes()
comments = load_comments()
feedback_entries = load_feedback()


def get_display_name(email: str) -> str:
    profile = users.get(email, {})
    return profile.get('username') or email.split('@')[0]


@app.context_processor
def inject_globals():
    return {"ADMIN_EMAIL": ADMIN_EMAIL, "users": users}


def reset_votes(log_message=False):
    """Clear all votes for a fresh launch or environment reset."""

    global votes
    votes = {}
    save_votes(votes)
    if log_message:
        print("All votes have been reset for a clean start.")


def backup_votes():
    """Create a timestamped backup of current votes before any destructive action."""

    from datetime import datetime

    os.makedirs('backups', exist_ok=True)
    backup_name = f"backups/votes_backup_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
    with open(backup_name, 'w') as f:
        json.dump(votes, f, indent=4)
    return backup_name


def ensure_admin_user():
    """Create a default admin/testing account if it doesn't exist."""

    admin_profile = users.get(ADMIN_EMAIL)
    hashed_admin_password = generate_password_hash(ADMIN_PASSWORD)

    if not admin_profile:
        users[ADMIN_EMAIL] = {
            'password': hashed_admin_password,
            'verified': True,
            'token': '',
            'username': 'admin',
            'main_champion': '',
            'favorite_champion': '',
            'favorites': [],
            'reset_token': '',
            'server': '',
            'main_role': '',
        }
        save_users(users)
        print(f"Provisioned admin account: {ADMIN_EMAIL}")
    else:
        admin_profile['password'] = hashed_admin_password
        admin_profile['verified'] = True
        admin_profile['token'] = ''
        admin_profile['username'] = 'admin'
        admin_profile.setdefault('main_champion', '')
        admin_profile.setdefault('favorite_champion', '')
        admin_profile.setdefault('favorites', [])
        admin_profile.setdefault('reset_token', '')
        admin_profile.setdefault('server', '')
        admin_profile.setdefault('main_role', '')
        save_users(users)
        print(f"Verified admin account: {ADMIN_EMAIL}")


def hydrate_user_profiles():
    """Backfill profile fields for legacy users."""

    changed = False
    for email, profile in users.items():
        if 'username' not in profile:
            profile['username'] = email.split('@')[0]
            changed = True
        if 'main_champion' not in profile:
            profile['main_champion'] = ''
            changed = True
        if 'favorites' not in profile:
            profile['favorites'] = []
            changed = True
        if 'reset_token' not in profile:
            profile['reset_token'] = ''
            changed = True
        if 'server' not in profile:
            profile['server'] = ''
            changed = True
        if 'main_role' not in profile:
            profile['main_role'] = ''
            changed = True
        if 'favorite_champion' not in profile:
            profile['favorite_champion'] = ''
            changed = True
    if changed:
        save_users(users)


def bootstrap_splash_assets():
    """Refresh missing splash assets on startup for a consistent experience."""

    try:
        report = sync_splash_assets(verbose=False)
        print(f"Splash assets synced: {report}")
    except Exception as exc:  # pragma: no cover - startup safety
        print(f"Splash asset sync failed: {exc}")


ensure_admin_user()
hydrate_user_profiles()
bootstrap_splash_assets()
lore_cache = load_lore_cache()


def get_latest_ddragon_version():
    try:
        resp = requests.get("https://ddragon.leagueoflegends.com/api/versions.json", timeout=6)
        resp.raise_for_status()
        versions = resp.json()
        return versions[0] if versions else "latest"
    except Exception:
        return "latest"


def fetch_champion_lore(champ_name):
    global lore_cache
    cached = lore_cache.get(champ_name)
    if cached:
        return cached

    version = get_latest_ddragon_version()
    url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion/{champ_name}.json"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        lore = payload.get('data', {}).get(champ_name, {}).get('lore')
        if lore:
            lore_cache[champ_name] = lore
            save_lore_cache(lore_cache)
        return lore or ""
    except Exception:
        return cached or ""

def load_all_skins():
    all_champions = {}
    base_folder = "static/splash_arts"

    if not os.path.exists(base_folder):
        return all_champions

    for champ in os.listdir(base_folder):
        champ_folder = os.path.join(base_folder, champ)
        if not os.path.isdir(champ_folder):
            continue
        json_path = os.path.join(champ_folder, "skin_names.json")
        if not os.path.exists(json_path):
            continue

        with open(json_path) as f:
            skin_info = json.load(f)

        images = []
        for skin in skin_info:
            skin_num = str(skin['num'])
            skin_name = skin['name']
            filename = f"{champ}_{skin_num}.jpg"
            file_path = f"splash_arts/{champ}/{filename}"
            images.append({"file_path": file_path, "skin_name": skin_name, "skin_num": skin_num})

        all_champions[champ] = images

    return all_champions


def compute_site_stats(all_champions):
    total_champions = len(all_champions)
    total_skins = sum(len(skins) for skins in all_champions.values())
    total_votes = sum(entry.get("count", 0) for entry in votes.values())
    total_comments = sum(len(comment_list) for comment_list in comments.values())
    total_favorites = sum(len(profile.get('favorites', [])) for profile in users.values())
    return {
        "champions": total_champions,
        "skins": total_skins,
        "votes": total_votes,
        "comments": total_comments,
        "favorites": total_favorites,
    }


def compute_user_karma(user_email):
    score = 0
    for champ_comments in comments.values():
        for comment in champ_comments:
            if comment.get("author") == user_email:
                upvotes = len(comment.get("upvoters", []))
                downvotes = len(comment.get("downvoters", []))
                score += upvotes - downvotes
    return score


def top_voted_skins(all_champions, limit=20):
    """Return a list of the top voted skins with their metadata."""

    leaderboard = []

    for vote_key, data in votes.items():
        champ_name, _, skin_id = vote_key.partition("-")
        if not champ_name or not skin_id:
            continue

        champ_skins = all_champions.get(champ_name)
        if not champ_skins:
            continue

        skin = next((s for s in champ_skins if str(s.get("skin_num")) == skin_id), None)
        if not skin:
            continue

        leaderboard.append({
            "champion": champ_name,
            "skin_name": skin.get("skin_name"),
            "file_path": skin.get("file_path"),
            "votes": data.get("count", 0),
        })

    leaderboard.sort(key=lambda item: item["votes"], reverse=True)
    return leaderboard[:limit]


def favorite_skin_for_user(email, champ_name, skin_id):
    user_profile = users.get(email)
    if not user_profile:
        return False

    favorites = user_profile.setdefault('favorites', [])
    key = f"{champ_name}-{skin_id}"
    if key in favorites:
        favorites.remove(key)
        changed = False
    else:
        favorites.append(key)
        changed = True

    save_users(users)
    return changed


def list_user_favorites(email, all_champions):
    profile = users.get(email, {})
    favorites = profile.get('favorites', [])
    favorite_cards = []

    for fav_key in favorites:
        champ_name, _, skin_id = fav_key.partition('-')
        champ_skins = all_champions.get(champ_name)
        if not champ_skins:
            continue
        skin = next((s for s in champ_skins if str(s.get('skin_num')) == skin_id), None)
        if not skin:
            continue
        favorite_cards.append({
            'champion': champ_name,
            'skin_name': skin.get('skin_name'),
            'file_path': skin.get('file_path'),
            'skin_id': skin_id,
        })
    return favorite_cards

@app.route('/')
def index():
    all_champions = load_all_skins()
    user_email = session.get('email')
    stats = compute_site_stats(all_champions)
    return render_template('index.html', all_champions=all_champions, user=user_email, stats=stats)

@app.route('/champion/<champ_name>')
def champion_page(champ_name):
    all_champions = load_all_skins()
    champ_skins = all_champions.get(champ_name)
    if not champ_skins:
        return "Champion not found", 404

    champion_lore = fetch_champion_lore(champ_name)

    user_email = session.get('email')
    user_karma = compute_user_karma(user_email) if user_email else 0
    user_profile = users.get(user_email, {}) if user_email else {}
    favorites = set(user_profile.get('favorites', [])) if user_email else set()

    champ_votes = {}
    for skin in champ_skins:
        vote_key = f"{champ_name}-{skin['skin_num']}"
        skin_vote_data = votes.get(vote_key, {"count": 0, "voters": []})
        voted = user_email in skin_vote_data["voters"] if user_email else False
        champ_votes[skin['skin_num']] = {
            "count": skin_vote_data["count"],
            "voted": voted,
            "favorite": vote_key in favorites,
        }

    champ_comments = comments.get(champ_name, [])
    # Sort comments by karma then recency
    sorted_comments = sorted(
        champ_comments,
        key=lambda c: (len(c.get("upvoters", [])) - len(c.get("downvoters", [])), c.get("created_at", "")),
        reverse=True,
    )
    enriched_comments = []
    for comment in sorted_comments:
        enriched_comments.append({
            **comment,
            'display_name': get_display_name(comment.get('author', '')),
        })

    return render_template(
        'champion.html',
        champ_name=champ_name,
        skins=champ_skins,
        user=user_email,
        champ_votes=champ_votes,
        comments=enriched_comments,
        karma=user_karma,
        favorites=favorites,
        champion_lore=champion_lore,
    )


@app.route('/top')
def top_skins():
    all_champions = load_all_skins()
    stats = compute_site_stats(all_champions)
    leaderboard = top_voted_skins(all_champions, limit=30)
    return render_template('top.html', leaderboard=leaderboard, stats=stats)


def issue_reset_token():
    token = session.get('vote_reset_token')
    if not token:
        token = uuid.uuid4().hex[:8].upper()
        session['vote_reset_token'] = token
    return token


@app.route('/admin')
def admin_dashboard():
    user_email = session.get('email')
    if user_email != ADMIN_EMAIL:
        flash('Admin access required.')
        return redirect(url_for('login'))

    all_champions = load_all_skins()
    stats = compute_site_stats(all_champions)

    total_users = len(users)
    verified_users = sum(1 for profile in users.values() if profile.get('verified'))
    champion_comment_totals = {
        champ: len(comment_list) for champ, comment_list in comments.items()
    }
    karma_board = [
        {
            "email": email,
            "username": profile.get('username') or email.split('@')[0],
            "karma": compute_user_karma(email),
            "verified": profile.get('verified'),
        }
        for email, profile in users.items()
    ]
    karma_board.sort(key=lambda entry: entry["karma"], reverse=True)
    feedback_sorted = sorted(feedback_entries, key=lambda f: f.get('created_at', ''), reverse=True)
    reset_token = issue_reset_token()

    return render_template(
        'admin.html',
        stats=stats,
        total_users=total_users,
        verified_users=verified_users,
        champion_comment_totals=champion_comment_totals,
        karma_board=karma_board,
        feedback=feedback_sorted,
        reset_token=reset_token,
    )


@app.route('/admin/export/messages')
def export_messages():
    user_email = session.get('email')
    if user_email != ADMIN_EMAIL:
        flash('Admin access required.')
        return redirect(url_for('login'))

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'id', 'type', 'topic', 'category', 'display_name', 'contact_email', 'server', 'main_role', 'favorite_champion', 'message', 'created_at'
    ])
    for entry in feedback_entries:
        writer.writerow([
            entry.get('id'),
            entry.get('type'),
            entry.get('topic'),
            entry.get('category', ''),
            entry.get('display_name'),
            entry.get('contact_email', entry.get('from', '')),
            entry.get('server', ''),
            entry.get('main_role', ''),
            entry.get('favorite_champion', ''),
            entry.get('message'),
            entry.get('created_at'),
        ])

    csv_data = output.getvalue()
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={
            'Content-Disposition': 'attachment; filename="league-of-skins-messages.csv"'
        }
    )


@app.route('/admin/reset_votes', methods=['POST'])
def admin_reset_votes():
    user_email = session.get('email')
    if user_email != ADMIN_EMAIL:
        flash('Admin access required.')
        return redirect(url_for('login'))

    token = session.get('vote_reset_token')
    provided_token = request.form.get('token_input', '').strip().upper()
    provided_email = request.form.get('confirm_email', '').strip().lower()
    acknowledgment = request.form.get('acknowledge') == 'on'

    if not (token and provided_token == token):
        flash('Reset halted: confirmation code mismatch.')
        return redirect(url_for('admin_dashboard'))

    if provided_email != ADMIN_EMAIL:
        flash('Reset halted: admin email confirmation failed.')
        return redirect(url_for('admin_dashboard'))

    if not acknowledgment:
        flash('Reset halted: you must acknowledge the backup + irreversible action.')
        return redirect(url_for('admin_dashboard'))

    backup_path = backup_votes()
    reset_votes(log_message=True)
    session.pop('vote_reset_token', None)
    flash(f'Votes reset. Backup saved to {backup_path}.')
    return redirect(url_for('admin_dashboard'))


@app.route('/about', endpoint='about_page')
def about_page():
    return render_template('about.html')


@app.route('/legal')
def legal():
    return render_template('legal.html')


@app.route('/vote/<champ_name>/<skin_id>', methods=['POST'])
def vote_skin(champ_name, skin_id):
    if 'email' not in session:
        return jsonify({'error': 'You must be logged in to vote.'}), 401

    user_email = session['email']
    all_champions = load_all_skins()

    # Verify champion exists
    champ_skins = all_champions.get(champ_name)
    if not champ_skins:
        return jsonify({'error': 'Champion not found.'}), 404

    # Verify skin exists for that champion
    skin_found = next((skin for skin in champ_skins if skin['skin_num'] == skin_id), None)
    if not skin_found:
        return jsonify({'error': 'Skin not found.'}), 404

    vote_key = f"{champ_name}-{skin_id}"

    user_profile = users.get(user_email)
    if not user_profile or not user_profile.get('verified'):
        return jsonify({'error': 'Please verify your email before voting.'}), 403

    # Initialize vote record if missing
    if vote_key not in votes:
        votes[vote_key] = {"count": 0, "voters": []}

    skin_vote_data = votes[vote_key]

    # Prevent double voting
    if user_email in skin_vote_data["voters"]:
        return jsonify({'error': 'You already voted for this skin.'}), 403

    # Register the vote
    skin_vote_data["count"] += 1
    skin_vote_data["voters"].append(user_email)

    save_votes(votes)

    return jsonify({'votes': skin_vote_data["count"]})


@app.route('/favorite/<champ_name>/<skin_id>', methods=['POST'])
def favorite_skin(champ_name, skin_id):
    if 'email' not in session:
        return jsonify({'error': 'You must be logged in to favorite skins.'}), 401

    user_email = session['email']
    user_profile = users.get(user_email)
    if not user_profile or not user_profile.get('verified'):
        return jsonify({'error': 'Please verify your email before saving favorites.'}), 403

    all_champions = load_all_skins()
    champ_skins = all_champions.get(champ_name)
    if not champ_skins:
        return jsonify({'error': 'Champion not found.'}), 404

    skin_found = next((skin for skin in champ_skins if str(skin['skin_num']) == str(skin_id)), None)
    if not skin_found:
        return jsonify({'error': 'Skin not found.'}), 404

    added = favorite_skin_for_user(user_email, champ_name, skin_id)
    status = 'added' if added else 'removed'
    return jsonify({'status': status})


@app.route('/comment/<champ_name>', methods=['POST'])
def add_comment(champ_name):
    if 'email' not in session:
        return jsonify({'error': 'You must be logged in to comment.'}), 401

    user_email = session['email']
    user_profile = users.get(user_email)
    if not user_profile or not user_profile.get('verified'):
        return jsonify({'error': 'Please verify your email before commenting.'}), 403

    payload = request.get_json(force=True)
    text = (payload.get('text') or '').strip()

    if not text:
        return jsonify({'error': 'Comment cannot be empty.'}), 400

    new_comment = {
        "id": str(uuid.uuid4()),
        "author": user_email,
        "text": text,
        "upvoters": [],
        "downvoters": [],
        "created_at": uuid.uuid1().hex,
    }

    champ_comments = comments.setdefault(champ_name, [])
    champ_comments.append(new_comment)
    save_comments(comments)

    return jsonify({
        'id': new_comment['id'],
        'author': get_display_name(user_email),
        'display_name': get_display_name(user_email),
        'text': text,
        'upvotes': 0,
        'downvotes': 0,
        'score': 0,
    }), 201


@app.route('/comment/<champ_name>/<comment_id>/vote', methods=['POST'])
def vote_comment(champ_name, comment_id):
    if 'email' not in session:
        return jsonify({'error': 'You must be logged in to vote on comments.'}), 401

    user_email = session['email']
    user_profile = users.get(user_email)
    if not user_profile or not user_profile.get('verified'):
        return jsonify({'error': 'Please verify your email before voting on comments.'}), 403

    payload = request.get_json(force=True)
    direction = payload.get('direction')

    if direction not in ['up', 'down']:
        return jsonify({'error': 'Invalid vote direction.'}), 400

    champ_comments = comments.get(champ_name, [])
    comment = next((c for c in champ_comments if c.get('id') == comment_id), None)
    if not comment:
        return jsonify({'error': 'Comment not found.'}), 404

    # Remove from opposite direction if present
    if direction == 'up':
        if user_email in comment.get('upvoters', []):
            return jsonify({'error': 'You already upvoted this comment.'}), 400
        if user_email in comment.get('downvoters', []):
            comment['downvoters'].remove(user_email)
        comment.setdefault('upvoters', []).append(user_email)
    else:
        if user_email in comment.get('downvoters', []):
            return jsonify({'error': 'You already downvoted this comment.'}), 400
        if user_email in comment.get('upvoters', []):
            comment['upvoters'].remove(user_email)
        comment.setdefault('downvoters', []).append(user_email)

    save_comments(comments)

    upvotes = len(comment.get('upvoters', []))
    downvotes = len(comment.get('downvoters', []))
    score = upvotes - downvotes

    return jsonify({
        'upvotes': upvotes,
        'downvotes': downvotes,
        'score': score,
    })


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    user_email = session.get('email')
    if not user_email:
        flash('Log in to manage your profile.')
        return redirect(url_for('login'))

    all_champions = load_all_skins()
    profile = users.get(user_email, {})

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        main_champion = request.form.get('main_champion', '').strip()
        server = request.form.get('server', '').strip()
        main_role = request.form.get('main_role', '').strip()
        favorite_champion = request.form.get('favorite_champion', '').strip()

        if not username:
            flash('Username is required.')
            return redirect(url_for('profile'))

        # Ensure username uniqueness
        for email, existing in users.items():
            if email == user_email:
                continue
            if (existing.get('username') or '').lower() == username.lower():
                flash('Username already in use. Please pick another.')
                return redirect(url_for('profile'))

        profile['username'] = username
        profile['main_champion'] = main_champion
        profile['server'] = server
        profile['main_role'] = main_role
        profile['favorite_champion'] = favorite_champion
        users[user_email] = profile
        save_users(users)
        flash('Profile updated.')
        return redirect(url_for('profile'))

    favorites = list_user_favorites(user_email, all_champions)
    champion_names = sorted(all_champions.keys())
    return render_template('profile.html', profile=profile, favorites=favorites, champions=champion_names)


@app.route('/u/<username>')
def public_profile(username):
    all_champions = load_all_skins()
    email_match = next((email for email, p in users.items() if (p.get('username') or '').lower() == username.lower()), None)
    if not email_match:
        return "User not found", 404
    profile = users[email_match]
    favorites = list_user_favorites(email_match, all_champions)
    return render_template('public_profile.html', profile=profile, favorites=favorites)


@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    flash('Feedback and contact are now in one place.')
    return redirect(url_for('contact'))


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        subject = (request.form.get('subject') or 'General inquiry').strip()
        message = (request.form.get('message') or '').strip()
        category = (request.form.get('category') or 'General').strip()
        user_email = session.get('email')
        name = (request.form.get('name') or '').strip()
        contact_email = (request.form.get('contact_email') or '').strip()

        if not message:
            flash('Message cannot be empty.')
            return redirect(url_for('contact'))

        profile = users.get(user_email, {}) if user_email else {}
        entry = {
            'id': str(uuid.uuid4()),
            'topic': subject,
            'message': message,
            'from': user_email,
            'display_name': name or (get_display_name(user_email) if user_email else 'Guest'),
            'created_at': uuid.uuid1().hex,
            'type': 'contact',
            'category': category,
            'contact_email': contact_email or user_email,
        }
        feedback_entries.append(entry)
        save_feedback(feedback_entries)
        flash('Thanks for reaching out. We log every detail so we can respond quickly.')
        return redirect(url_for('contact'))

    return render_template('contact.html')



# --- User auth routes ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email'].lower()
        username = (request.form.get('username') or '').strip()
        password = request.form['password']
        password_confirm = request.form.get('password_confirm')

        if not email or not password or not password_confirm or not username:
            flash('Please fill all fields.')
            return redirect(url_for('register'))

        if password != password_confirm:
            flash('Passwords do not match.')
            return redirect(url_for('register'))

        if email in users:
            flash('Email already registered.')
            return redirect(url_for('register'))

        for profile in users.values():
            if (profile.get('username') or '').lower() == username.lower():
                flash('Username already taken.')
                return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        verification_token = str(uuid.uuid4())

        users[email] = {
            'password': hashed_password,
            'verified': False,
            'token': verification_token,
            'username': username,
            'main_champion': '',
            'favorite_champion': '',
            'favorites': [],
            'reset_token': '',
            'server': '',
            'main_role': '',
        }
        save_users(users)

        print(f"Verification link (fake): http://localhost:8080/verify_email/{verification_token}")

        flash('Registration successful! Check your email to verify your account before voting.')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/verify_email/<token>')
def verify_email(token):
    for email, user in users.items():
        if user.get('token') == token:
            user['verified'] = True
            user['token'] = ''
            save_users(users)
            flash('Email verified! You can now log in.')
            return redirect(url_for('login'))
    return "Invalid or expired token", 400


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = (request.form.get('email') or '').lower().strip()

        user = users.get(email)
        if user:
            reset_token = str(uuid.uuid4())
            user['reset_token'] = reset_token
            save_users(users)
            print(f"Password reset link (fake): http://localhost:8080/reset_password/{reset_token}")

        flash('If the email exists, a reset link has been sent.')
        return redirect(url_for('forgot_password'))

    return render_template('forgot_password.html')


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    target_email = None
    for email, profile in users.items():
        if profile.get('reset_token') == token:
            target_email = email
            break

    if not target_email:
        return "Invalid or expired reset link", 400

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm = request.form.get('password_confirm', '')

        if not password or not confirm:
            flash('Please fill all fields.')
            return redirect(url_for('reset_password', token=token))

        if password != confirm:
            flash('Passwords do not match.')
            return redirect(url_for('reset_password', token=token))

        users[target_email]['password'] = generate_password_hash(password)
        users[target_email]['reset_token'] = ''
        save_users(users)
        flash('Password updated. You can log in now.')
        return redirect(url_for('login'))

    return render_template('reset_password.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].lower()
        password = request.form['password']

        user = users.get(email)
        if not user:
            flash('Invalid email or password.')
            return redirect(url_for('login'))

        if not user.get('verified'):
            flash('Please verify your email before logging in.')
            return redirect(url_for('login'))

        if not check_password_hash(user['password'], password):
            flash('Invalid email or password.')
            return redirect(url_for('login'))

        session['email'] = email
        flash('Logged in successfully!')
        return redirect(url_for('index'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('email', None)
    flash('Logged out.')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080)

