# 🚀 Colab Bridge API

Easily manage Google Colab notebook sessions via a simple HTTP API. This bridge spawns, monitors, and interacts with Colab notebooks over ngrok tunnels.

---

## 🌐 Endpoint Reference

Replace `${BRIDGE_URL}` with your server's base URL (e.g., `https://abc123.ngrok-free.app`).

---

### 1. ➕ Create a New Colab Session

```bash
curl -X POST ${BRIDGE_URL}/session/create \
     -H "Content-Type: application/json" \
     -d '{
           "duration": 3600,
           "id": "optional-my-session-id"
         }'
```

#### 📄 Response:
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "expires_at": 1711975000.123,
  "public_url": null
}
```

> `public_url` becomes available once the ngrok tunnel is ready.

---

### 2. 🔄 Poll Session Status

```bash
curl ${BRIDGE_URL}/session/status/<SESSION_ID>
```

#### While Starting:
```json
{ "id": "...", "expired": false, "public_url": null, "ready": false }
```

#### Once Ready:
```json
{ "id": "...", "expired": false, "public_url": "https://xyz123.ngrok-free.app", "ready": true }
```

---

### 3. 🔢 List All Sessions

```bash
curl ${BRIDGE_URL}/sessions
```

#### Response:
```json
{
  "bridge_url": "https://abc123.ngrok-free.app",
  "sessions": [
    {
      "id": "123e4567-...",
      "expires_at": 1711975000.123,
      "expired": false,
      "public_url": "https://xyz123.ngrok-free.app",
      "ready": true
    },
    {
      "id": "89abcdef-...",
      "expires_at": 1711975600.456,
      "expired": false,
      "public_url": null,
      "ready": false
    }
  ]
}
```

---

### 4. ❌ Kill a Session Immediately (SESSION SELENIUM KILL)

```bash
curl -X POST ${BRIDGE_URL}/session/kill \
     -H "Content-Type: application/json" \
     -d '{ "id": "<SESSION_ID>" }'
```

#### Response:
```json
{ "id": "<SESSION_ID>", "killed": true }
```

---

### 5. 🔧 Upload Cookies (cookies.json)

```bash
curl -X POST ${BRIDGE_URL}/cookies/create \
     -H "Content-Type: application/json" \
     -d '[
           { "name": "SID", "value": "XYZ", "domain": ".google.com", "path": "/" },
           { "name": "HSID", "value": "ABC", "domain": ".google.com", "path": "/" }
         ]'
```

#### Response:
```json
{ "status": "cookies.json created", "count": 2 }
```

---

## ⏳ Polling Workflow Example

### Create Session
```bash
CREATE=$(curl -s -X POST ${BRIDGE_URL}/session/create \
         -H 'Content-Type:application/json' \
         -d '{"duration":3600}')
SID=$(echo "$CREATE" | jq -r .id)
echo "Session ID: $SID"
```

### Wait Until Ready
```bash
until curl -s ${BRIDGE_URL}/session/status/$SID | jq -r .ready | grep -q true; do
  echo -n "."
  sleep 5
done
URL=$(curl -s ${BRIDGE_URL}/session/status/$SID | jq -r .public_url)
echo "→ Public URL: $URL"
```

---

### ⚡ Instant Kill Endpoint (DISCONNECT COLAB)

```bash
curl -X POST https://YOUR_NGROK_URL/kill
```

---

## 👋 Contributing
PRs and issues welcome! This is an early-stage tool designed for automation flows with Google Colab notebooks.

---

## 🌐 License
DO NOT TOUCH IM OWNER  !!!

