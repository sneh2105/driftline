"""Mechanical edit log. Appends one line per file edit to logs/edits.raw.log.
Independent of the model, so there is always a trail even if it forgets BUILD_LOG.md.
Never fails the tool call."""
import json, os, subprocess, sys, datetime
try:
    data = json.load(sys.stdin)
    path = (data.get("tool_input") or {}).get("file_path", "?")
    tool = data.get("tool_name", "?")
    try:
        br = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        br = "?"
    os.makedirs("logs", exist_ok=True)
    with open("logs/edits.raw.log", "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')}\t{br}\t{tool}\t{path}\n")
except Exception:
    pass
sys.exit(0)
