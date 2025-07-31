import time
import threading
import uuid
import json
import os
from flask import Flask, request, jsonify
from pyngrok import ngrok, conf

# ---- CONFIGURATION ----
# Paste your bridge's own ngrok authtoken here or set via NGROK_TOKEN env var.
NGROK_TOKEN = os.getenv('NGROK_TOKEN', '30dpq1UC8r9X6GLzHuljwYFCluO_2wry8UU7LWzRYctzz8UF9')

# Import your existing session controller
# Ensure 'colab_controller.py' defines 'start_colab_session' and 'extract_public_url'.
from colab_controller import start_colab_session, extract_public_url

app = Flask(__name__)

# In-memory session store: session_id -> { driver, expiry, public_url }
sessions = {}
lock = threading.Lock()

# Start bridge's public endpoint via ngrok
def setup_ngrok():
    conf.get_default().auth_token = NGROK_TOKEN
    tunnel = ngrok.connect(addr="5000", bind_tls=True)
    return tunnel.public_url

BRIDGE_PUBLIC_URL = setup_ngrok()
print(f"🔗 Bridge API public URL: {BRIDGE_PUBLIC_URL}")

# Background cleaner to purge expired sessions
def cleanup_expired():
    while True:
        now = time.time()
        with lock:
            expired = [sid for sid, info in sessions.items() if now >= info['expiry']]
            for sid in expired:
                info = sessions.pop(sid, None)
                if info:
                    try:
                        info['driver'].quit()
                        app.logger.info(f"Session {sid} expired and closed")
                    except Exception as e:
                        app.logger.error(f"Error closing expired session {sid}: {e}")
        time.sleep(30)

threading.Thread(target=cleanup_expired, daemon=True).start()

@app.route('/session/create', methods=['POST'])
def create_session():
    data = request.get_json(force=True)
    duration = data.get('duration', 3600)
    sid = data.get('id') or str(uuid.uuid4())

    with lock:
        if sid in sessions:
            return jsonify({"error": "Session ID already exists"}), 400
        try:
            driver = start_colab_session()
            public_url = extract_public_url(driver)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        expiry = time.time() + duration
        sessions[sid] = { 'driver': driver, 'expiry': expiry, 'public_url': public_url }

    return jsonify({"id": sid, "expires_at": expiry, "public_url": public_url}), 201

@app.route('/session/kill', methods=['POST'])
def kill_session():
    data = request.get_json(force=True)
    sid = data.get('id')
    if not sid:
        return jsonify({"error": "No session ID provided"}), 400
    with lock:
        info = sessions.pop(sid, None)
    if not info:
        return jsonify({"error": "Session not found"}), 404
    try:
        info['driver'].quit()
    except Exception as e:
        app.logger.error(f"Error quitting driver for session {sid}: {e}")
    return jsonify({"id": sid, "killed": True}), 200

@app.route('/cookies/create', methods=['POST'])
def create_cookies_file():
    cookies = request.get_json(force=True)
    if not isinstance(cookies, list):
        return jsonify({"error": "Payload must be a list of cookies"}), 400
    with open('cookies.json', 'w') as f:
        json.dump(cookies, f)
    return jsonify({"status": "cookies.json created", "count": len(cookies)}), 201

@app.route('/sessions', methods=['GET'])
def list_sessions():
    now = time.time()
    result = []
    with lock:
        for sid, info in sessions.items():
            try:
                cookies = info['driver'].get_cookies()
            except:
                cookies = []
            result.append({
                'id': sid,
                'expires_at': info['expiry'],
                'expired': now >= info['expiry'],
                'public_url': info['public_url'],
                'cookies': cookies
            })
    return jsonify({
        'bridge_url': BRIDGE_PUBLIC_URL,
        'sessions': result
    }), 200

@app.route('/session/status/<sid>', methods=['GET'])
def session_status(sid):
    with lock:
        info = sessions.get(sid)
    if not info:
        return jsonify({"error": "Session not found"}), 404
    expired = time.time() >= info['expiry']
    return jsonify({"id": sid, "expired": expired, "public_url": info['public_url']}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
