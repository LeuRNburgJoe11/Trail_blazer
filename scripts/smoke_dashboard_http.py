"""Exercise a running dashboard proxy with synthetic SHM data, without API calls."""
import argparse
import json
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    parser.add_argument("--host-header", default="127.0.0.1:5173", help="Browser Host preserved by the proxy")
    args = parser.parse_args()

    def request(path, body=None, content_type="application/json"):
        req = Request(args.base_url.rstrip("/") + path, data=body, headers={
            "Host": args.host_header, "Origin": "http://127.0.0.1:5173", "Content-Type": content_type})
        with urlopen(req, timeout=120) as response:
            assert "application/json" in response.headers.get("Content-Type", ""), "API returned HTML"
            return json.load(response)

    def ask(**payload):
        return request("/api/assistant/ask", json.dumps(payload).encode())

    assert request("/api/assistant/context")["models"]
    definition = ask(subsystem="general", question="What does SHM mean?")
    assert definition["answer"] == "SHM means Structural Health Monitoring."
    boundary = "railpulse-smoke-boundary"
    samples = "\n".join(map(str, [0, 10, 0, -10, 0, 20, 0, -20, 0, 10, 0, -10, 0, 5, 0, -5, 0]))
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="docker-smoke.csv"\r\n'
            f'Content-Type: text/csv\r\n\r\n{samples}\r\n--{boundary}--\r\n').encode()
    result = request("/api/shm/predict", body, f"multipart/form-data; boundary={boundary}")
    assert result["rows"][0]["file_id"] == "docker-smoke.csv"
    answer = ask(subsystem="shm", question="Explain this result", snapshot=result["assistant_snapshot"], row_index=0)
    assert "docker-smoke.csv" in answer["answer"]
    assert "Current dashboard" in answer["dataset_label"]
    print("PASS: proxy JSON routing, General definition, synthetic SHM upload/inference and scoped chat.")
    print("Integration check only; not a model-accuracy or paid-provider test.")


if __name__ == "__main__":
    main()
