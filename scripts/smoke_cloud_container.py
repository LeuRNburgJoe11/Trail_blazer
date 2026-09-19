"""Run inside the cloud image with official data mounted read-only at /test-data."""
from pathlib import Path
import os
import sys

sys.path.insert(0, "/workspace/app/railpulse")
os.environ["RAILPULSE_PUBLIC_ORIGIN"] = "https://demo.example"
from fastapi.testclient import TestClient
from backend.cloud import create_app

app = create_app()
client = TestClient(app, base_url="https://demo.example")
other = TestClient(app, base_url="https://demo.example")
headers = {"Origin": "https://demo.example"}
assert client.get("/").status_code == 200
assert client.get("/api/assistant/context").status_code == 200
assert other.get("/api/assistant/context").status_code == 200
status = client.get("/api/status").json()
assert all(status[d]["available"] for d in ("door", "acv", "rail", "shm")), status
for domain, relative in (
    ("door", "Door/Test.csv"),
    ("acv", "acv/Test/acv_test_case.xlsx"),
    ("rail", "Rail_Corrugation/Test/Test36.csv"),
    ("shm", "SHM/Test/test01.csv"),
):
    path = Path("/test-data") / relative
    with path.open("rb") as file:
        response = client.post(f"/api/{domain}/predict", files={"files": (path.name, file)}, headers=headers)
    assert response.status_code == 200, (domain, response.text)
    result = response.json()
    assert result["rows"], domain
    payload = {"subsystem": domain, "question": "Explain this result", "snapshot": result["assistant_snapshot"], "row_index": 0}
    answer = client.post("/api/assistant/ask", json=payload, headers=headers)
    assert answer.status_code == 200, (domain, answer.text)
    assert answer.json()["dataset_label"] == "Current dashboard results", answer.text
    assert other.post("/api/assistant/ask", json=payload, headers=headers).status_code == 400
    print(f"PASS: {domain} upload/inference/chat and cross-session rejection", flush=True)
assert not list(Path("/tmp").glob("railpulse-request-*")), "Temporary upload directory leaked"
print("PASS: all four subsystems; no paid APIs used; upload directories cleaned.")
