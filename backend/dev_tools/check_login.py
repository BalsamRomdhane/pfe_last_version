import json
import requests

url = 'http://localhost:8000/api/auth/login/'

payloads = [
    ('admin1', 'Admin1234!'),
    ('admin', 'Admin1234!'),
    ('admin', 'admin'),
]

for username, password in payloads:
    try:
        resp = requests.post(url, json={'login': username, 'password': password}, timeout=20)
        print(f'LOGIN TRY username={username} status={resp.status_code}')
        print(resp.text)
    except Exception as exc:
        print(f'LOGIN TRY username={username} ERROR={exc}')
