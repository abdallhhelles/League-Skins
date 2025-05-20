import os
import json
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Replace with a secure key

USERS_DB_FILE = 'users_db.json'
VOTES_DB_FILE = 'votes_db.json'  # Store votes per skin, including who voted

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

# Load users and votes into memory
users = load_users()
votes = load_votes()

def load_all_skins():
    all_champions = {}
    base_folder = "static/splash_arts"

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

@app.route('/')
def index():
    all_champions = load_all_skins()
    user_email = session.get('email')
    return render_template('index.html', all_champions=all_champions, user=user_email, votes=votes)

@app.route('/champion/<champ_name>')
def champion_page(champ_name):
    all_champions = load_all_skins()
    champ_skins = all_champions.get(champ_name)
    if not champ_skins:
        return "Champion not found", 404

    user_email = session.get('email')

    champ_votes = {}
    for skin in champ_skins:
        vote_key = f"{champ_name}-{skin['skin_num']}"
        skin_vote_data = votes.get(vote_key, {"count": 0, "voters": []})
        voted = user_email in skin_vote_data["voters"] if user_email else False
        champ_votes[skin['skin_num']] = {
            "count": skin_vote_data["count"],
            "voted": voted
        }

    return render_template('champion.html', champ_name=champ_name, skins=champ_skins, user=user_email, champ_votes=champ_votes)


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



# --- User auth routes ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email'].lower()
        password = request.form['password']
        password_confirm = request.form.get('password_confirm')

        if not email or not password or not password_confirm:
            flash('Please fill all fields.')
            return redirect(url_for('register'))

        if password != password_confirm:
            flash('Passwords do not match.')
            return redirect(url_for('register'))

        if email in users:
            flash('Email already registered.')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        verification_token = str(uuid.uuid4())

        users[email] = {
            'password': hashed_password,
            'verified': True,
            'token': verification_token
        }
        save_users(users)

        print(f"Verification link (fake): http://localhost:5000/verify_email/{verification_token}")

    #    flash('Registration successful! Check your email to verify your account.')
        flash('Registration successful!')
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

