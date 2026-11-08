"""Generate and run a local Siege workload, preserving each run's artifacts."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def read_metrics(console):
    """Find Siege's JSON summary without depending on its surrounding messages."""
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", console):
        try:
            value, _ = decoder.raw_decode(console[match.start():])
        except ValueError:
            continue
        if isinstance(value, dict) and "transactions" in value and "failed_transactions" in value:
            return value
    return None


def write_report(run_dir, status, error=None):
    console_path = run_dir / "console.log"
    console = console_path.read_text() if console_path.exists() else ""
    metrics = read_metrics(console)
    if status == "COMPLETED" and metrics is None:
        status = "COMPLETED — RESULTS UNAVAILABLE"
    elif status == "COMPLETED" and metrics.get("failed_transactions", 0):
        status = "COMPLETED WITH FAILED TRANSACTIONS"
    elif status == "COMPLETED":
        status = "COMPLETED — NO FAILED TRANSACTIONS REPORTED"
    lines = ["CANADIAN WEATHER LOAD TEST — DEMO REPORT", "=" * 44,
             f"Status: {status}", f"Run (UTC): {run_dir.name}",
             "Target: synthetic weather API inside Docker (http://api:8000)", "",
             "WORKLOAD AND TEST SETTINGS",
             f"Requested workload entries: {os.environ.get('REQUESTS', '100')}",
             f"Requested hot-location share: {os.environ.get('CACHED_PERCENT', '20')}%",
             f"Forecast hours: {os.environ.get('HOURS', '24')} (feature_4: 1)",
             f"Random seed: {os.environ.get('SEED', '42')}",
             f"Concurrent users: {os.environ.get('CONCURRENCY', '5')}",
             f"Requested duration: {os.environ.get('DURATION', '10S')}"]
    for line in console.splitlines():
        if line.startswith(("Profile counts:", "Hot-location requests:")):
            lines.append(line)
    lines.extend(["", "RESULTS"])
    if metrics:
        fields = [("transactions", "Transactions", ""),
                  ("successful_transactions", "Successful transactions", ""),
                  ("failed_transactions", "Failed transactions", ""),
                  ("availability", "Availability", "%"),
                  ("elapsed_time", "Actual test duration", " seconds"),
                  ("transaction_rate", "Transaction rate", " requests/second"),
                  ("response_time", "Average response time", " seconds"),
                  ("longest_transaction", "Longest transaction", " seconds"),
                  ("data_transferred", "Data transferred", " MB")]
        for key, label, unit in fields:
            value = metrics.get(key)
            lines.append(f"{label}: {value}{unit}" if value is not None else f"{label}: unavailable")
        lines.append("Response times are rounded by Siege; 0.00 does not mean zero latency.")
        if metrics.get("successful_transactions", 0) > metrics.get("transactions", 0):
            lines.append("Siege reported more successes than total transactions; raw counters are preserved here.")
    else:
        lines.append("No Siege summary available. See console.log for details.")
    if error:
        lines.append(f"Error: {error}")
    lines.extend(["", "WHAT THIS MEANS",
                  "Workload entries are reused throughout the timed run; transaction counts can be higher.",
                  "Hot locations simulate repeated-location traffic, not measured cache hits.",
                  "These results measure the local mock and your machine, not the original weather API.",
                  "", "DETAILED FILES (relative to the project directory)",
                  f"output/{run_dir.name}/", "  urls.siege  — generated requests",
                  "  console.log — execution output", "  siege.log   — aggregate Siege statistics",
                  "  run.json    — tool versions and commands", "  output.txt  — this report", ""])
    report = "\n".join(lines)
    (run_dir / "output.txt").write_text(report)
    # Replace the latest report atomically, retaining a separate copy for each run.
    temporary = run_dir.parent / f".{run_dir.name}.tmp"
    temporary.write_text(report)
    temporary.replace(run_dir.parent / "output.txt")


def run_demo(run_dir):
    concurrency = os.environ.get("CONCURRENCY", "5")
    duration = os.environ.get("DURATION", "10S")
    if not concurrency.isdigit() or int(concurrency) < 1:
        raise SystemExit("CONCURRENCY must be a positive integer")
    if not re.fullmatch(r"[1-9][0-9]*[SMHsmh]", duration):
        raise SystemExit("DURATION must be a positive duration such as 10S, 1M, or 1H")
    workload = run_dir / "urls.siege"
    generate = [sys.executable, "main.py", "--base-url", "http://api:8000",
                "--requests", os.environ.get("REQUESTS", "100"),
                "--cached-percent", os.environ.get("CACHED_PERCENT", "20"),
                "--hours", os.environ.get("HOURS", "24"),
                "--seed", os.environ.get("SEED", "42"), "--output", str(workload)]
    version = subprocess.run(["siege", "--version"], capture_output=True, text=True, check=True)
    siege_version = (version.stdout + version.stderr).strip()
    command = ["siege", "--benchmark", f"--concurrent={concurrency}", f"--time={duration}",
               f"--file={workload}", "--content-type=application/json", "--header=Accept: application/json",
               f"--log={run_dir / 'siege.log'}"]
    metadata = {"siege_version": siege_version, "python_version": sys.version,
                "generate_command": generate, "siege_command": command}
    (run_dir / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Artifacts: {run_dir}", flush=True)
    with (run_dir / "console.log").open("w") as log:
        log.write(siege_version + "\n")
        for args in (generate, command):
            with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as process:
                for line in process.stdout:
                    print(line, end="", flush=True)
                    log.write(line)
                    log.flush()
                code = process.wait()
            if code:
                raise SystemExit(code)


def main():
    run_dir = Path("/output") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    run_dir.mkdir(parents=True)
    write_report(run_dir, "RUNNING")
    try:
        run_demo(run_dir)
    except (Exception, SystemExit) as error:
        write_report(run_dir, "FAILED", str(error))
        print("Demo failed. Read output/output.txt for details.", flush=True)
        raise
    else:
        write_report(run_dir, "COMPLETED")
        print("Report ready: output/output.txt (on your host)", flush=True)


if __name__ == "__main__":
    main()
