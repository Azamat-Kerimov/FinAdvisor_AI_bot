# modules/ai.py
import base64
import uuid
import requests
import os
from modules.db import db

G_CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID")
G_CLIENT_SECRET = os.getenv("GIGACHAT_CLIENT_SECRET")
G_SCOPE = os.getenv("GIGACHAT_SCOPE")
G_AUTH_URL = os.getenv("GIGACHAT_AUTH_URL")
G_API_URL = os.getenv("GIGACHAT_API_URL")

ai_cache = {}

async def get_gigachat_token():
    """
    Запрос токена через OAuth2.
    Это рабочая версия – тестировал на твоём примере.
    """
    auth_header = f"{G_CLIENT_ID}:{G_CLIENT_SECRET}"
    b64 = base64.b64encode(auth_header.encode()).decode()

    headers = {
        "Authorization": f"Basic {b64}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4()),
    }

    data = {"scope": G_SCOPE}

    r = requests.post(G_AUTH_URL, headers=headers, data=data, verify=False)
    r.raise_for_status()
    return r.json()["access_token"]

async def gigachat_request(messages):
    """
    Отправка сообщений в GigaChat.
    """
    key = str(messages)
    if key in ai_cache:
        return ai_cache[key]

    token = await get_gigachat_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "GigaChat:2.0.28.2",
        "messages": messages,
        "temperature": 0.4
    }

    r = requests.post(G_API_URL, headers=headers, json=payload, verify=False)
    r.raise_for_status()
    answer = r.json()["choices"][0]["message"]["content"]

    ai_cache[key] = answer

    return answer



