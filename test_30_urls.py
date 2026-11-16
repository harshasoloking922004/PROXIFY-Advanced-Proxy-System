import subprocess
import sys
from pathlib import Path

urls = [
    "https://example.com",
    "https://www.python.org",
    "https://www.wikipedia.org",
    "https://www.iana.org",
    "https://www.gnu.org",
    "https://www.kernel.org",
    "https://www.djangoproject.com",
    "https://www.mozilla.org",
    "https://www.debian.org",
    "https://www.w3.org",
    "https://www.github.com",
    "https://www.python.org/about/",
    "https://www.raspberrypi.com",
    "https://www.apache.org",
    "https://www.postgresql.org",
    "https://www.mysql.com",
    "https://www.linux.org",
    "https://www.ubuntu.com",
    "https://www.microsoft.com",
    "https://www.apple.com",
    "https://www.nasa.gov",
    "https://www.noaa.gov",
    "https://www.britannica.com",
    "https://www.un.org",
    "https://www.who.int",
    "https://www.openstreetmap.org",
    "https://www.djangoproject.com/start/",
    "https://www.tensorflow.org",
    "https://pytorch.org",
    "https://scikit-learn.org"
]

success = 0
failed = 0

for i, url in enumerate(urls, 1):
    print(f"\n[{i}/30] Fetching: {url}")

    result = subprocess.run(
        [sys.executable, "client/fetch_test.py", url],
        capture_output=True,
        text=True,
        timeout=45
    )

    if result.returncode == 0:
        success += 1
        print("SUCCESS")
    else:
        failed += 1
        print("FAILED")
        print(result.stdout)
        print(result.stderr)

print("\n========== FINAL SUMMARY ==========")
print("Total URLs:", len(urls))
print("Successful:", success)
print("Failed:", failed)
print("===================================")