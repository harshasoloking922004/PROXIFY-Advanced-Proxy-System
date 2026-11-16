"""Run multiple proxy clients concurrently and report each result."""
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
CLIENT_SCRIPT = PROJECT_ROOT / "client" / "fetch_test.py"
TOTAL_CLIENTS = 5
TEST_URL = "https://example.com"
TIMEOUT_SECONDS = 45


def run_client(client_number):
    try:
        result = subprocess.run(
            [sys.executable, str(CLIENT_SCRIPT), TEST_URL],
            cwd=str(PROJECT_ROOT),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
        return {
            "client": client_number,
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "output": result.stdout.strip(),
            "error": result.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        return {
            "client": client_number,
            "success": False,
            "returncode": None,
            "output": "",
            "error": f"Request timed out after {TIMEOUT_SECONDS} seconds",
        }
    except Exception as exc:
        return {
            "client": client_number,
            "success": False,
            "returncode": None,
            "output": "",
            "error": str(exc),
        }


if not CLIENT_SCRIPT.is_file():
    raise SystemExit(f"Client script not found: {CLIENT_SCRIPT}")

print(f"Starting {TOTAL_CLIENTS} clients simultaneously...")
print(f"Test URL: {TEST_URL}\n")

results = []
with ThreadPoolExecutor(max_workers=TOTAL_CLIENTS) as executor:
    futures = [executor.submit(run_client, i) for i in range(1, TOTAL_CLIENTS + 1)]
    for future in as_completed(futures):
        result = future.result()
        results.append(result)
        status = "SUCCESS" if result["success"] else "FAILED"
        print(f"\n--- Client {result['client']}: {status} ---")
        if result["output"]:
            print(result["output"])
        if result["error"]:
            print("Error:", result["error"])
        if result["returncode"] not in (None, 0):
            print("Exit code:", result["returncode"])

successful = sum(item["success"] for item in results)
failed = len(results) - successful
print("\n========== TEST SUMMARY ==========")
print(f"Total clients: {TOTAL_CLIENTS}")
print(f"Successful: {successful}")
print(f"Failed: {failed}")
print("==================================")

if failed:
    raise SystemExit(1)
