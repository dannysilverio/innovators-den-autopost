"""Backfill: post Den carousels that reached Instagram but missed Facebook (and Threads) so every page matches.

Reads backfill/queue.json (oldest first). Each run posts ONE item to every platform it is still missing on,
capped at BACKFILL_PER_DAY items a day (default 5). Results go to backfill/log.json so nothing posts twice.
Images load from the commit that first published them, so slides the 10-day cleanup removed still work.
A platform is only tried when its secrets exist. Set DRY_RUN=1 to print without posting.
"""
import json, os, pathlib, datetime as dt
from zoneinfo import ZoneInfo

import publish as P

ROOT = pathlib.Path(__file__).parent
QUEUE = ROOT / "backfill/queue.json"
LOG = ROOT / "backfill/log.json"
REPO = os.environ.get("GITHUB_REPOSITORY", "dannysilverio/innovators-den-autopost")
PER_DAY = int(os.environ.get("BACKFILL_PER_DAY") or 5)
ET = ZoneInfo("America/New_York")


def live_platforms():
    out = []
    if os.environ.get("FB_PAGE_ID") and os.environ.get("FB_PAGE_TOKEN"):
        out.append(("facebook", P.facebook))
    if P.enabled("threads"):
        out.append(("threads", P.threads))
    return out


def main():
    items = json.loads(QUEUE.read_text())["items"]
    log = json.loads(LOG.read_text()) if LOG.exists() else {}
    plats = live_platforms()
    if not plats:
        print("backfill: no platform secrets set, nothing to do"); return
    today = dt.datetime.now(ET).strftime("%Y-%m-%d")
    done_today = sum(1 for e in log.values() if any(
        isinstance(v, dict) and v.get("ok") and v.get("at", "").startswith(today) for v in e.values()))
    if done_today >= PER_DAY:
        print(f"backfill: daily cap reached ({done_today}/{PER_DAY})"); return
    for it in items:
        entry = log.get(it["run_id"], {})
        missing = [(n, fn) for n, fn in plats if not (entry.get(n) or {}).get("ok")]
        if not missing:
            continue
        urls = [f"https://raw.githubusercontent.com/{REPO}/{it['commit']}/public/{it['run_id']}/{s}" for s in it["slides"]]
        post = {"title": it["title"], "topic": it.get("topic"), "caption_facebook": it["caption_facebook"],
                "caption_threads": it.get("caption_threads"), "caption_instagram": it["caption_facebook"]}
        print(f"backfill: {it['title'][:70]} -> {', '.join(n for n, _ in missing)}")
        now = dt.datetime.now(ET).isoformat(timespec="minutes")
        for name, fn in missing:
            if P.DRY:
                print(f"[dry] {name} ({len(urls)} slides)"); continue
            try:
                entry[name] = {"ok": True, "at": now, **fn(post, urls)}
                print(f"  {name}: posted {entry[name]['id']}")
            except Exception as e:
                entry[name] = {"ok": False, "at": now, "error": str(e)[:400]}
                print(f"  {name}: FAILED {str(e)[:200]}")
        if not P.DRY:
            log[it["run_id"]] = entry
            LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False))
        return  # one item per run
    print("backfill: all caught up")


if __name__ == "__main__":
    main()
