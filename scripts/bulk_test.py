import io
import json
import sys
import time
import urllib.request
import zipfile

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
TOTAL = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
BAD_EVERY = 50


def call(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    request = urllib.request.Request(
        BASE + path, method=method, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


recipients = [
    {"name": "" if index % BAD_EVERY == 0 else f"Person {index}", "email": f"person{index}@example.com"}
    for index in range(1, TOTAL + 1)
]
payload = {
    "certificate": {"title": "Load Test", "issuer": "QA", "issue_date": "2026-10-01"},
    "recipients": recipients,
}

start = time.time()
job = call("POST", "/api/v1/certificate-jobs", payload)
print(f"accepted in {time.time() - start:.2f}s, total={job['total']}")

while True:
    status = call("GET", f"/api/v1/certificate-jobs/{job['id']}")
    elapsed = time.time() - start
    print(f"{elapsed:6.1f}s {status['status']:<22} {status['progress_percent']:5.1f}% {status['counts']}")
    if status["status"] not in ("PENDING", "PROCESSING"):
        break
    time.sleep(1)

elapsed = time.time() - start
print(f"finished in {elapsed:.1f}s, {TOTAL / elapsed:.0f} certificates/s")

archive = urllib.request.urlopen(f"{BASE}/api/v1/certificate-jobs/{job['id']}/download").read()
count = len(zipfile.ZipFile(io.BytesIO(archive)).namelist())
print(f"zip contains {count} PDFs, expected {status['counts']['succeeded']}")
print(f"open in the app: {BASE}/#/jobs/{job['id']}")
