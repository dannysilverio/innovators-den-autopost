"""Exit code 0 + prints 'skip=true' to GITHUB_OUTPUT if a real post already went out today (ET)."""
import json, os, pathlib, datetime as dt
from zoneinfo import ZoneInfo
today = dt.datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
p = pathlib.Path(__file__).parent / "posted.json"
log = json.loads(p.read_text()) if p.exists() else []
done = any(e["date"] == today and not e.get("dry_run") and any(r.get("ok") for r in e["results"].values()) for e in log)
skip = done and os.environ.get("FORCE") != "1"
print(f"today={today} already_posted={done} skip={skip}")
with open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a") as f: f.write(f"skip={'true' if skip else 'false'}\n")
