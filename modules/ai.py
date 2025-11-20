# modules/ai.py
import os
import uuid
import base64
import httpx
from dotenv import load_dotenv

load_dotenv()

GIGACHAT_CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID")
GIGACHAT_CLIENT_SECRET = os.getenv("GIGACHAT_CLIENT_SECRET")
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE")
GIGACHAT_AUTH_URL = os.getenv("GIGACHAT_AUTH_URL")
GIGACHAT_API_URL = os.getenv("GIGACHAT_API_URL")
GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat:2.0.28.2")

async def get_gigachat_token():
    auth = f"{GIGACHAT_CLIENT_ID}:{GIGACHAT_CLIENT_SECRET}"
    b64 = base64.b64encode(auth.encode()).decode()
    headers = {
        "Authorization": f"Basic {b64}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4()),
    }
    data = {"scope": GIGACHAT_SCOPE}
    async with httpx.AsyncClient(verify=False, timeout=20.0) as client:
        r = await client.post(GIGACHAT_AUTH_URL, headers=headers, data=data)
        r.raise_for_status()
        return r.json()["access_token"]

async def gigachat_request(messages, model=None, timeout=40.0):
    if model is None:
        model = GIGACHAT_MODEL
    token = await get_gigachat_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "messages": messages, "temperature": 0.3}
    async with httpx.AsyncClient(verify=False, timeout=timeout) as client:
        r = await client.post(GIGACHAT_API_URL, headers=headers, json=payload)
        r.raise_for_status()
        j = r.json()
        # safe access
        try:
            return j["choices"][0]["message"]["content"]
        except Exception:
            return str(j)
