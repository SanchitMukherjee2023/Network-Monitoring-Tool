from flask import Flask, render_template, jsonify, request
import subprocess
import platform
import time
from datetime import datetime
import sqlite3
import threading

app = Flask(__name__)

# Database setup
def init_db():
    conn = sqlite3.connect('network_monitor.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS devices
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 ip TEXT NOT NULL,
                 name TEXT,
                 status TEXT,
                 last_checked TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ping_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 device_id INTEGER,
                 timestamp TEXT,
                 response_time REAL,
                 status TEXT,
                 FOREIGN KEY(device_id) REFERENCES devices(id))''')
    conn.commit()
    conn.close()

init_db()

# Sample data - in a real app, this would come from the database
devices = [
    {"id": 1, "ip": "8.8.8.8", "name": "Google DNS", "status": "up", "last_checked": "2023-05-01 12:00:00"},
    {"id": 2, "ip": "1.1.1.1", "name": "Cloudflare DNS", "status": "up", "last_checked": "2023-05-01 12:01:00"},
    {"id": 3, "ip": "192.168.1.1", "name": "Local Router", "status": "down", "last_checked": "2023-05-01 11:59:00"},
]

def ping_device(ip):
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    command = ['ping', param, '1', ip]
    try:
        output = subprocess.check_output(command, stderr=subprocess.STDOUT, universal_newlines=True)
        return True, float(output.split('time=')[-1].split()[0].replace('ms', ''))
    except subprocess.CalledProcessError:
        return False, None

def monitor_devices():
    while True:
        conn = sqlite3.connect('network_monitor.db')
        c = conn.cursor()
        c.execute("SELECT id, ip FROM devices")
        devices = c.fetchall()
        
        for device in devices:
            device_id, ip = device
            status, response_time = ping_device(ip)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Update device status
            c.execute("UPDATE devices SET status=?, last_checked=? WHERE id=?", 
                     ('up' if status else 'down', timestamp, device_id))
            
            # Record ping history
            c.execute("INSERT INTO ping_history (device_id, timestamp, response_time, status) VALUES (?, ?, ?, ?)",
                      (device_id, timestamp, response_time, 'up' if status else 'down'))
            
            conn.commit()
        
        conn.close()
        time.sleep(60)  # Check every minute

# Start monitoring thread
monitor_thread = threading.Thread(target=monitor_devices)
monitor_thread.daemon = True
monitor_thread.start()

@app.route('/')
def dashboard():
    conn = sqlite3.connect('network_monitor.db')
    c = conn.cursor()
    c.execute("SELECT * FROM devices")
    devices = c.fetchall()
    conn.close()
    
    device_list = []
    for device in devices:
        device_list.append({
            "id": device[0],
            "ip": device[1],
            "name": device[2],
            "status": device[3],
            "last_checked": device[4]
        })
    
    return render_template('dashboard.html', devices=device_list)

@app.route('/devices')
def device_management():
    conn = sqlite3.connect('network_monitor.db')
    c = conn.cursor()
    c.execute("SELECT * FROM devices")
    devices = c.fetchall()
    conn.close()
    
    device_list = []
    for device in devices:
        device_list.append({
            "id": device[0],
            "ip": device[1],
            "name": device[2],
            "status": device[3],
            "last_checked": device[4]
        })
    
    return render_template('devices.html', devices=device_list)

@app.route('/settings')
def settings():
    return render_template('settings.html')

@app.route('/api/devices', methods=['GET', 'POST'])
def api_devices():
    if request.method == 'GET':
        conn = sqlite3.connect('network_monitor.db')
        c = conn.cursor()
        c.execute("SELECT * FROM devices")
        devices = c.fetchall()
        conn.close()
        
        device_list = []
        for device in devices:
            device_list.append({
                "id": device[0],
                "ip": device[1],
                "name": device[2],
                "status": device[3],
                "last_checked": device[4]
            })
        
        return jsonify(device_list)
    
    elif request.method == 'POST':
        data = request.json
        ip = data.get('ip')
        name = data.get('name', '')
        
        conn = sqlite3.connect('network_monitor.db')
        c = conn.cursor()
        c.execute("INSERT INTO devices (ip, name, status, last_checked) VALUES (?, ?, ?, ?)",
                 (ip, name, 'unknown', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        device_id = c.lastrowid
        conn.close()
        
        return jsonify({"message": "Device added", "id": device_id}), 201

@app.route('/api/devices/<int:device_id>', methods=['DELETE'])
def api_device(device_id):
    conn = sqlite3.connect('network_monitor.db')
    c = conn.cursor()
    c.execute("DELETE FROM devices WHERE id=?", (device_id,))
    conn.commit()
    conn.close()
    
    return jsonify({"message": "Device deleted"}), 200

@app.route('/api/devices/<int:device_id>/history')
def device_history(device_id):
    conn = sqlite3.connect('network_monitor.db')
    c = conn.cursor()
    c.execute("SELECT timestamp, response_time, status FROM ping_history WHERE device_id=? ORDER BY timestamp DESC LIMIT 24", (device_id,))
    history = c.fetchall()
    conn.close()
    
    history_list = []
    for record in history:
        history_list.append({
            "timestamp": record[0],
            "response_time": record[1],
            "status": record[2]
        })
    
    return jsonify(history_list)

if __name__ == '__main__':
    app.run(debug=True)