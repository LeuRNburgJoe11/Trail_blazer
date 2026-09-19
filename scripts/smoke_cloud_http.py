"""Test the public HTTPS demo using browser-style cookies, without paid API calls."""
import argparse
import http.cookiejar
import json
from urllib.request import HTTPCookieProcessor, Request, build_opener


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    if not base.startswith("https://"):
        raise SystemExit("Use the actual HTTPS Cloud Run URL")
    client = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(path, body=None, kind="application/json"):
        request = Request(base + path, data=body, headers={"Origin": base, "Content-Type": kind})
        with client.open(request, timeout=210) as response:
            return json.load(response)

    assert call("/healthz")["configured"]
    status = call("/api/status")
    assert all(status[d]["available"] for d in ("door", "acv", "rail", "shm")), status
    definition = call("/api/assistant/ask", json.dumps({"subsystem": "general", "question": "What does SHM mean?"}).encode())
    assert definition["answer"] == "SHM means Structural Health Monitoring."
    boundary = "railpulse-cloud-smoke"
    values = "\n".join(map(str, [0, 10, 0, -10, 0, 20, 0, -20, 0, 5, 0, -5, 0]))
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="cloud-smoke.csv"\r\n'
            f'Content-Type: text/csv\r\n\r\n{values}\r\n--{boundary}--\r\n').encode()
    result = call("/api/shm/predict", body, f"multipart/form-data; boundary={boundary}")
    answer = call("/api/assistant/ask", json.dumps({"subsystem": "shm", "question": "Explain this result", "snapshot": result["assistant_snapshot"], "row_index": 0}).encode())
    assert "cloud-smoke.csv" in answer["answer"]
    print("PASS: all model assets available; definition, synthetic SHM upload and scoped chat work over HTTPS.")


if __name__ == "__main__":
    main()
