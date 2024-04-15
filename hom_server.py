from flask import Flask, render_template, redirect, url_for, request, session, flash
import os
import shutil
import json
import hashlib
from apscheduler.schedulers.background import BackgroundScheduler
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'your_secret_key'

USERS_FILE = "users.json"

def load_users_from_file():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            content = f.read()
            print("File Content:", content)  # Print file content for debugging
            return json.loads(content)
    return {}


def save_users_to_file(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

def sync_files():
    for username, data in users.items():
        user_dir = os.path.join('user_files', username)
        if not os.path.exists(user_dir):
            os.makedirs(user_dir)
        for filename in data['files']:
            file_path = os.path.join(user_dir, filename)
            if not os.path.exists(file_path):
                shutil.copy2(os.path.join('user_files', filename), file_path)
    save_users_to_file(users)

def capture_file_metadata(username, filename):
    if username in users:
        users[username]['files'].append({'filename': filename, 'timestamp': str(datetime.now())})  # Convert datetime to string
        save_users_to_file(users)

scheduler = BackgroundScheduler()
scheduler.add_job(sync_files, 'interval', minutes=5)
scheduler.start()

users = load_users_from_file()

@app.route('/')
def index():
    if 'user' in session:
        user_files = users.get(session['user'], {}).get('files', [])
        return render_template('index.html', files=user_files)
    else:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and hashlib.sha256(password.encode()).hexdigest() == users[username].get('password', ''):
            session['user'] = username
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid username or password')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username not in users:
            users[username] = {'password': hashlib.sha256(password.encode()).hexdigest(), 'files': []}
            save_users_to_file(users)
            session['user'] = username
            return redirect(url_for('index'))
        else:
            return render_template('signup.html', error='Username already exists')
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

@app.route('/files/add', methods=['POST'])
def add_file():
    if 'user' in session:
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        user_dir = os.path.join('user_files', session['user'])
        if not os.path.exists(user_dir):
            os.makedirs(user_dir)
        filename = secure_filename(file.filename)
        file_path = os.path.join(user_dir, filename)
        file.save(file_path)
        capture_file_metadata(session['user'], filename)  # Capture file metadata
        return redirect(url_for('index'))
    else:
        return redirect(url_for('login'))

@app.route('/files/remove/<filename>', methods=['POST'])
def remove_file(filename):
    if 'user' in session:
        user_dir = os.path.join('user_files', session['user'])
        file_path = os.path.join(user_dir, filename)
        if os.path.exists(file_path):
            # Create a 'Trash' directory if it doesn't exist
            trash_dir = os.path.join(user_dir, 'Trash')
            if not os.path.exists(trash_dir):
                os.makedirs(trash_dir)
            # Move the file to the 'Trash' directory
            trash_path = os.path.join(trash_dir, filename)
            shutil.move(file_path, trash_path)
            # Update user's file list
            users[session['user']]['files'].remove(filename)
            save_users_to_file(users)
            return redirect(url_for('index'))  # Redirect to the index page after moving the file to trash
        else:
            # Handle case where file does not exist
            return "File not found", 404
    else:
        return redirect(url_for('login'))

@app.route('/trash')
def trash():
    if 'user' in session:
        user_dir = os.path.join('user_files', session['user'])
        trash_dir = os.path.join(user_dir, 'Trash')
        if os.path.exists(trash_dir):
            trash_files = os.listdir(trash_dir)
            return render_template('trash.html', files=trash_files)
        else:
            return render_template('trash.html', files=[])  # Empty trash
    else:
        return redirect(url_for('login'))

@app.route('/files/download/<filename>', methods=['GET'])
def download_file(filename):
    user_dir = os.path.join('user_files', session.get('user', ''))
    file_path = os.path.join(user_dir, filename)
    return send_from_directory(user_dir, filename, as_attachment=True)

@app.route('/sync', methods=['POST'])
def sync():
    sync_files    
    return redirect(url_for('index'))

@app.route('/search', methods=['POST'])
def search():
    if 'user' in session:
        search_term = request.form['search']
        user_files = users.get(session['user'], {}).get('files', [])
        search_results = [file for file in user_files if search_term.lower() in file.lower()]
        return render_template('index.html', files=search_results)
    else:
        return redirect(url_for('login'))

@app.route('/files/my_files', methods=['GET'])
def my_files():
    # Logic to retrieve user's files
    return render_template('my_files.html', files=user_files)

@app.route('/shared_with_me', methods=['GET'])
def shared_with_me():
    # Logic to retrieve files shared with the current user
    return render_template('shared_with_me.html', shared_files=shared_files)

from datetime import datetime, timedelta

@app.route('/recent', methods=['GET'])
def recent():
    current_time = datetime.now()
    time_window = timedelta(days=7)
    
    recent_files = []
    for username, data in users.items():
        user_recent_files = data.get('files', [])
        for file_data in user_recent_files:
            if isinstance(file_data, dict):
                timestamp_str = file_data.get('timestamp')
                if timestamp_str:
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str)
                        if current_time - timestamp <= time_window:
                            recent_files.append({"username": username, "filename": file_data['filename'], "last_accessed": timestamp})
                    except ValueError:
                        pass
    
    return render_template('recent.html', recent_files=recent_files)


@app.route('/starred', methods=['GET'])
def starred():
    # Logic to retrieve starred files
    return render_template('starred.html', starred_files=starred_files)

@app.route('/files/restore/<filename>', methods=['POST'])
def restore_file(filename):
    # Logic to restore the file
    return redirect(url_for('trash'))  # Redirect to the trash page after successful restoration

@app.route('/files/delete_permanently/<filename>', methods=['POST'])
def delete_permanently(filename):
    # Logic to permanently delete the file
    return redirect(url_for('trash'))  # Redirect to the trash page after successful deletion

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4040, debug=True)
