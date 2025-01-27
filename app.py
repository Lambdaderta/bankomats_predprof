from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import pandas as pd
import os
from classificator import process_csv, analyze_timestamps, get_latest_status

app = Flask(__name__)
app.secret_key = 'ключик_секретик'

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS users')
    cursor.execute('DROP TABLE IF EXISTS events')
    cursor.execute('DROP TABLE IF EXISTS placemarks')
    cursor.execute('DROP TABLE IF EXISTS atms')
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            device_id TEXT,
            event_type TEXT,
            value TEXT,
            label TEXT,
            timestamp TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE placemarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            latitude REAL,
            longitude REAL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE atms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            device_id TEXT,
            latitude REAL,
            longitude REAL,
            working_times TEXT,
            non_working_times TEXT,
            latest_status TEXT,
            atm_counter INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (device_id) REFERENCES events (device_id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def home():
    name = session.get('name', None)
    return render_template('index.html', name=name)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash('Email already exists. Please choose a different email.', 'error')
            return redirect(url_for('register'))

        cursor.execute('INSERT INTO users (name, email, password) VALUES (?, ?, ?)', (name, email, password))
        conn.commit()
        conn.close()

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password))
        user = cursor.fetchone()
        conn.close()

        session['name'] = name
        session['user_id'] = user[0]

        return redirect(url_for('home'))

    return render_template('reg.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['name'] = user[1]
            session['user_id'] = user[0]
            return redirect(url_for('home'))
        else:
            flash('Login failed. Please check your email and password.', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('name', None)
    session.pop('user_id', None)
    return redirect(url_for('home'))

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('home'))
    file = request.files['file']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('home'))
    if file:
        upload_dir = 'uploads'
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
        filename = os.path.join(upload_dir, file.filename)
        file.save(filename)

        try:
            df = process_csv(filename)
        except Exception as e:
            flash(f'Error reading CSV file: {e}', 'error')
            return redirect(url_for('home'))

        user_id = session.get('user_id')

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        for index, row in df.iterrows():
            cursor.execute('INSERT INTO events (user_id, device_id, event_type, value, label, timestamp) VALUES (?, ?, ?, ?, ?, ?)',
                           (user_id, row['DeviceID'], row['EventType'], row['Value'], row['Label'], row['Timestamp']))
        conn.commit()
        conn.close()

        atm_working_times, atm_non_working_times = analyze_timestamps(df)
        latest_status = get_latest_status(df)

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        for device_id, working_times in atm_working_times.items():
            working_times_str = ', '.join([f'{start} - {end}' for start, end in working_times])
            non_working_times_str = ', '.join([f'{start} - {end}' for start, end in atm_non_working_times[device_id]])
            cursor.execute('SELECT * FROM atms WHERE user_id = ? AND device_id = ?', (user_id, device_id))
            existing_atm = cursor.fetchone()
            if existing_atm:
                cursor.execute('UPDATE atms SET working_times = ?, non_working_times = ?, latest_status = ? WHERE user_id = ? AND device_id = ?',
                               (working_times_str, non_working_times_str, latest_status[device_id], user_id, device_id))
            else:
                cursor.execute('INSERT INTO atms (user_id, device_id, working_times, non_working_times, latest_status) VALUES (?, ?, ?, ?, ?)',
                               (user_id, device_id, working_times_str, non_working_times_str, latest_status[device_id]))
        conn.commit()
        conn.close()

        flash('File uploaded and processed successfully', 'success')
        return redirect(url_for('home'))

@app.route('/save_placemark', methods=['POST'])
def save_placemark():
    user_id = session.get('user_id')
    type = request.json['type']
    latitude = request.json['latitude']
    longitude = request.json['longitude']

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM placemarks WHERE user_id = ? AND type = ?', (user_id, type))
    existing_placemark = cursor.fetchone()

    if existing_placemark:
        cursor.execute('UPDATE placemarks SET latitude = ?, longitude = ? WHERE user_id = ? AND type = ?',
                       (latitude, longitude, user_id, type))
    else:
        cursor.execute('INSERT INTO placemarks (user_id, type, latitude, longitude) VALUES (?, ?, ?, ?)',
                       (user_id, type, latitude, longitude))

    conn.commit()
    conn.close()

    return jsonify({'status': 'success'})

@app.route('/get_placemarks', methods=['GET'])
def get_placemarks():
    user_id = session.get('user_id')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT type, latitude, longitude FROM placemarks WHERE user_id = ?', (user_id,))
    placemarks = cursor.fetchall()
    conn.close()

    return jsonify(placemarks)

@app.route('/save_atm', methods=['POST'])
def save_atm():
    user_id = session.get('user_id')
    device_id = request.json['device_id']
    latitude = request.json['latitude']
    longitude = request.json['longitude']

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM atms WHERE user_id = ? AND device_id = ?', (user_id, device_id))
    existing_atm = cursor.fetchone()

    if existing_atm:
        cursor.execute('UPDATE atms SET latitude = ?, longitude = ? WHERE user_id = ? AND device_id = ?',
                       (latitude, longitude, user_id, device_id))
    else:
        cursor.execute('INSERT INTO atms (user_id, device_id, latitude, longitude) VALUES (?, ?, ?, ?)',
                       (user_id, device_id, latitude, longitude))

    conn.commit()
    conn.close()

    return jsonify({'status': 'success'})

@app.route('/get_atms', methods=['GET'])
def get_atms():
    user_id = session.get('user_id')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT device_id, latitude, longitude, working_times, non_working_times, latest_status FROM atms WHERE user_id = ?', (user_id,))
    atms = cursor.fetchall()
    conn.close()

    return jsonify(atms)

@app.route('/get_atms_with_coords', methods=['GET'])
def get_atms_with_coords():
    user_id = session.get('user_id')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT device_id, latitude, longitude, working_times, non_working_times, latest_status FROM atms WHERE user_id = ? AND latitude IS NOT NULL AND longitude IS NOT NULL', (user_id,))
    atms = cursor.fetchall()
    conn.close()

    return jsonify(atms)

@app.route('/calculate_route', methods=['POST'])
def calculate_route():
    user_id = session.get('user_id')
    type = request.json['type']

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    if type == 'mechanic':
        cursor.execute('SELECT device_id, latitude, longitude FROM atms WHERE user_id = ? AND latest_status = "нужен механик"', (user_id,))
    elif type == 'car':
        cursor.execute('SELECT device_id, latitude, longitude FROM atms WHERE user_id = ? AND latest_status = "нужна инкассаторская машина"', (user_id,))
    else:
        cursor.execute('SELECT device_id, latitude, longitude FROM atms WHERE user_id = ?', (user_id,))
    atms = cursor.fetchall()
    conn.close()

    waypoints = []
    for atm in atms:
        if atm[1] and atm[2]:
            waypoints.append([atm[1], atm[2]])

    return jsonify(waypoints)

@app.route('/delete_placemark', methods=['POST'])
def delete_placemark():
    user_id = session.get('user_id')
    type = request.json['type']
    device_id = request.json.get('device_id')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if type == 'atm' and device_id:
        cursor.execute('DELETE FROM atms WHERE user_id = ? AND device_id = ?', (user_id, device_id))
    else:
        cursor.execute('DELETE FROM placemarks WHERE user_id = ? AND type = ?', (user_id, type))

    conn.commit()
    conn.close()

    return jsonify({'status': 'success'})

@app.route('/get_atm_statistics', methods=['POST'])
def get_atm_statistics():
    user_id = session.get('user_id')
    device_id = request.json['device_id']

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT device_id, working_times, non_working_times, latest_status FROM atms WHERE user_id = ? AND device_id = ?', (user_id, device_id))
    atm = cursor.fetchone()
    conn.close()

    if atm:
        working_times = atm[1].split(', ')
        non_working_times = atm[2].split(', ')

        working_time = sum([(pd.to_datetime(end) - pd.to_datetime(start)).total_seconds() for start, end in [time.split(' - ') for time in working_times]])
        non_working_time = sum([(pd.to_datetime(end) - pd.to_datetime(start)).total_seconds() for start, end in [time.split(' - ') for time in non_working_times]])

        return jsonify({
            'device_id': atm[0],
            'latest_status': atm[3],
            'working_times': atm[1],
            'non_working_times': atm[2],
            'working_time': working_time,
            'non_working_time': non_working_time
        })
    else:
        return jsonify({'status': 'error', 'message': 'ATM not found'})

if __name__ == '__main__':
    app.run(debug=True)