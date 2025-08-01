import time
import threading
import uuid
import json
import os
from flask import Flask, request, jsonify
from pyngrok import ngrok, conf
from colab_controller import (
    start_colab_session,
    extract_public_url,
    interrupt_colab
)

from selenium.webdriver.common.by import By
import time


# ---- CONFIGURATION ----
NGROK_TOKEN = os.getenv('NGROK_TOKEN', '30dpq1UC8r9X6GLzHuljwYFCluO_2wry8UU7LWzRYctzz8UF9')
from colab_controller import start_colab_session, extract_public_url

app = Flask(__name__)

# Session store: session_id -> {'driver': webdriver or None, 'expiry': timestamp, 'public_url': str or None}
sessions = {}
lock = threading.Lock()



def interrupt_colab(driver):
    """
    Click the Colab “Interrupt execution” button (the ⏸️ icon)
    so the Python cell actually stops before we tear down.
    """
    try:
        # There are two paper-icon-buttons with aria-label="Interrupt execution"
        # depending on runtime state—so pick whichever is present:
        btn = driver.find_element(
            By.CSS_SELECTOR,
            'paper-icon-button[aria-label="Interrupt execution"]'
        )
        # The actual clickable element lives inside its shadowRoot:
        driver.execute_script(
            "arguments[0].shadowRoot.querySelector('button').click();",
            btn
        )
        # give it a moment to actually interrupt
        time.sleep(2)
        print("✅ Colab interrupt button clicked.")
    except Exception as e:
        print("⚠️ Could not click interrupt:", e)


# Expose bridge API via ngrok
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
                if info and info.get('driver'):
                    try:
                        # Interrupt any running cell
                        info['driver'].execute_script("""
                            let btn = document.querySelector('colab-toolbar-button[icon="pause-circle"]');
                            if(btn && btn.shadowRoot) {
                                let interruptBtn = btn.shadowRoot.querySelector('button');
                                if(interruptBtn) interruptBtn.click();
                            }
                        """)
                        time.sleep(1)
                        info['driver'].quit()
                        app.logger.info(f"Session {sid} expired and closed")
                    except Exception as e:
                        app.logger.error(f"Error closing expired session {sid}: {e}")
        time.sleep(30)

threading.Thread(target=cleanup_expired, daemon=True).start()

# Worker to start and track a Colab session asynchronously
def session_worker(sid):
    try:
        driver = start_colab_session()
        url = extract_public_url(driver)
        with lock:
            if sid in sessions:
                sessions[sid]['driver'] = driver
                sessions[sid]['public_url'] = url
    except Exception as e:
        app.logger.error(f"Error in session setup {sid}: {e}")

@app.route('/session/create', methods=['POST'])
def create_session():
    data = request.get_json(force=True) or {}
    duration = data.get('duration', 3600)
    sid = data.get('id') or str(uuid.uuid4())

    with lock:
        if sid in sessions:
            return jsonify({"error": "Session ID already exists"}), 400
        expiry = time.time() + duration
        # Initialize placeholder
        sessions[sid] = {'driver': None, 'expiry': expiry, 'public_url': None}

    # Launch async setup thread
    threading.Thread(target=session_worker, args=(sid,), daemon=True).start()

    return jsonify({"id": sid, "expires_at": expiry, "public_url": None}), 201

@app.route('/session/kill', methods=['POST'])
def kill_session():
    data = request.get_json(force=True) or {}
    sid = data.get('id')
    if not sid:
        return jsonify({"error": "No session ID provided"}), 400
    with lock:
        info = sessions.pop(sid, None)
    if not info:
        return jsonify({"error": "Session not found"}), 404
    driver = info.get('driver')
    if driver:
        try:
            # Interrupt any running cell in Colab

            interrupt_colab(driver) 
            time.sleep(2)
            driver.quit()
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
            result.append({
                'id': sid,
                'expires_at': info['expiry'],
                'expired': now >= info['expiry'],
                'public_url': info['public_url'],
                'ready': info['public_url'] is not None
            })
    return jsonify({ 'bridge_url': BRIDGE_PUBLIC_URL, 'sessions': result }), 200

@app.route('/session/status/<sid>', methods=['GET'])
def session_status(sid):
    with lock:
        info = sessions.get(sid)
    if not info:
        return jsonify({"error": "Session not found"}), 404
    expired = time.time() >= info['expiry']
    return jsonify({
        "id": sid,
        "expired": expired,
        "public_url": info['public_url'],
        "ready": info['public_url'] is not None
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
