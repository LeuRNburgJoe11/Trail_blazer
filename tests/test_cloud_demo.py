"""Public demo isolation and limits; no Google Cloud or paid API calls."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_cloud_boundary_in_isolated_dashboard_process():
    # Nested dashboard package must never shadow canonical imports in this suite.
    code = '''
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from backend.cloud import DemoBoundary, COOKIE
from backend.assistant_bridge import remember, snapshot_for, UPLOAD_DIRECTORY
from pathlib import Path
app = FastAPI()
directories = []
@app.get('/api/context')
def context(): return {'ready': True}
@app.post('/api/save')
def save():
    directory = UPLOAD_DIRECTORY.get()
    directories.append(directory)
    Path(directory, 'private.csv').write_text('private')
    return remember('shm', {'rows': [{'prediction': 0.1}]})
@app.post('/api/read')
async def read(request: Request):
    try: return snapshot_for((await request.json())['token'], 'shm')
    except ValueError: return {'denied': True}
boundary = DemoBoundary(app, 'https://demo.example', max_requests=100, per_session=50)
a = TestClient(boundary, base_url='https://demo.example')
b = TestClient(boundary, base_url='https://demo.example')
headers = {'origin': 'https://demo.example'}
assert a.post('/api/save', headers=headers).status_code == 403
boot = a.get('/api/context')
assert 'HttpOnly' in boot.headers['set-cookie'] and 'Secure' in boot.headers['set-cookie']
b.get('/api/context')
token = a.post('/api/save', headers=headers).json()['assistant_snapshot']
assert all(not Path(p).exists() for p in directories)
assert a.post('/api/read', headers=headers, json={'token': token}).json()['rows']
assert b.post('/api/read', headers=headers, json={'token': token}).json()['denied']
assert a.post('/api/save', headers={'origin': 'https://evil.example'}).status_code == 403
assert a.get('/api/context', headers={'host': 'evil.example'}).status_code == 403
assert a.post('/api/save', headers=headers | {'content-length': str(25*1024*1024)}).status_code == 413
assert a.post('/api/assistant/ask', headers=headers, content=b'x'*17000).status_code == 413
c = TestClient(DemoBoundary(app, 'https://demo.example', max_requests=1), base_url='https://demo.example')
assert c.get('/api/context').status_code == 200
assert c.get('/api/context').status_code == 429
d = TestClient(DemoBoundary(app, ''), base_url='https://demo.example')
assert d.get('/healthz').status_code == 200
assert d.get('/api/context').status_code == 503
print('cloud boundary checks passed')
'''
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT / "app/railpulse", capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
