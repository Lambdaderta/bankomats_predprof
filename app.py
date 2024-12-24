from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS users')
    cursor.execute('DROP TABLE IF EXISTS events')
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
            FOREIGN KEY (user_id) REFERENCES users (id)
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

        session['name'] = name

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
    file = request.files['file']
    filename = os.path.join('uploads', file.filename)
    file.save(filename)

    df = pd.read_csv(filename)
    user_id = session.get('user_id')

    incassators = ["ЗаменаКассеты", "ЗаполнениеКассеты"]
    mechanic = ["ЗажеваннаяКупюра", "ЗагрузкаПроцессораВысокая", "ОжиданиеПользователя", "АварийноеВыключение", "ОшибкаОбновления", "ОшибкаПечати", "ОшибкаПриемаКупюр", "ОшибкаКарт", "ОшибкаВыдачиНаличности", "ОшибкаТехническая", "ОшибкаЖесткогоДиска", "ОтказВОбслуживании", "СигнализацияОшибки", "ОбслуживаниеТребуется", "ОшибкаСинхронизацииДанных", "ОшибкаСети", "ПроблемаСоСвязью"]
    all_good = ["ВосстановлениеСвязи", "ВыходПользователя", "ПроверкаБаланс", "ОбработкаЗапроса", "СнятиеНаличными", "ВнесениеНаличных", "ВходПользователя", "ПроверкаЖесткогоДиска", "ПерезагрузкаУстройства"]
    chek_need = ["СостояниеКартриджа", "СостояниеПриемаКупюр", "Предупреждение", "ПроверкаСостоянияКлавиатуры", "ПроверкаСостоянияКарт", "ПроверкаЭнергоснабжения", "ОбновлениеПрограммногоОбеспечения", "ТестированиеУстройства", "СостояниеУстройстваИзменено", "ПроверкаКассеты", "ОбновлениеБезопасности", "ЗавершениеТранзакции", "ПроверкаОбновлений", "ПроверкаСистемныхЛогов", "ТестированиеСистемы", "УстановкаОбновлений", "ПроверкаСостоянияСвязи", "ПроверкаСостоянияПечати"]
    incassator_values = ['Низкий уровень наличных', 'Нет наличных', 'Купюры отсутствуют']
    good_values = ['Клавиатура работает', 'Все карты в порядке', 'Энергоснабжение в порядке', 'Успешно', 'Хорошее', 'Полный', 'Работает', 'Обновления отсутствуют', 'Ошибок не найдено', 'Все системы работают', 'Принтер работает']

    def determine_label(row):
        if row['EventType'] in incassators:
            return 'нужна инкассаторская машина'
        elif row['EventType'] in mechanic:
            return 'нужен механик'
        elif row['EventType'] in all_good:
            return 'все в порядке'
        elif row['EventType'] in chek_need:
            if pd.notna(row['Value']):
                if row['Value'] in incassator_values:
                    return 'нужна инкассаторская машина'
                elif row['Value'] in good_values:
                    return 'все в порядке'
                else:
                    return 'нужен механик'
            else:
                return 'нужен механик'
        else:
            return 'неизвестно'

    df['Label'] = df.apply(determine_label, axis=1)

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    for index, row in df.iterrows():
        cursor.execute('INSERT INTO events (user_id, device_id, event_type, value, label) VALUES (?, ?, ?, ?, ?)',
                       (user_id, row['DeviceID'], row['EventType'], row['Value'], row['Label']))
    conn.commit()
    conn.close()

    flash('File uploaded and processed successfully', 'success')
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
