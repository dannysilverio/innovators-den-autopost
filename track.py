"""Performance tracker: once a day, snapshot Instagram account + per-post insights into metrics.json.

Uses the free Instagram API with the same IG_ACCESS_TOKEN used for posting.
Post insights need the instagram_business_manage_insights permission on that token;
if it is missing, the error is recorded in metrics.json (so the weekly review can flag it) and posting is unaffected.
"""
import json, os, pathlib, datetime as dt, urllib.request, urllib.parse, urllib.error
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).parent
METRICS, POSTED = ROOT / "metrics.json", ROOT / "posted.json"
HOST = os.environ.get("IG_GRAPH_HOST") or "graph.instagram.com"
BASE = f"https://{HOST}/{os.environ.get('IG_API_VERSION', 'v21.0')}"
TOK, UID = os.environ.get("IG_ACCESS_TOKEN", ""), os.environ.get("IG_USER_ID", "")


def get(path, **params):
    params["access_token"] = TOK
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode()[:300]}


def media_insights(mid, is_reel):
    metrics = "views,reach,likes,comments,saved,shares,total_interactions"
    if is_reel:
        metrics += ",ig_reels_avg_watch_time"
    d = get(f"{mid}/insights", metric=metrics)
    if "error" in d:  # retry with the core set in case one metric is unsupported for this media type
        d = get(f"{mid}/insights", metric="reach,likes,comments,saved,shares")
    if "error" in d:
        return {"error": d["error"]}
    return {m["name"]: (m.get("values") or [{}])[0].get("value", m.get("total_value", {}).get("value")) for m in d.get("data", [])}


def main():
    if not TOK or not UID:
        print("track: no Instagram credentials, skipping"); return
    today = dt.datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    data = json.loads(METRICS.read_text()) if METRICS.exists() else {"daily": [], "posts": {}}
    if data["daily"] and data["daily"][-1]["date"] == today and os.environ.get("FORCE_TRACK") != "1":
        print("track: already ran today"); return

    acct = get(UID, fields="username,followers_count,follows_count,media_count")
    snap = {"date": today, "followers": acct.get("followers_count"), "media": acct.get("media_count")}
    if "error" in acct:
        snap["error"] = acct["error"]

    posted = json.loads(POSTED.read_text()) if POSTED.exists() else []
    cutoff = (dt.date.today() - dt.timedelta(days=30)).isoformat()
    errors = 0
    for e in posted:
        if e.get("dry_run") or e.get("date", "") < cutoff:
            continue
        for kind in ("instagram", "instagram_reel"):
            r = (e.get("results") or {}).get(kind) or {}
            if not r.get("ok") or not r.get("id"):
                continue
            ins = media_insights(r["id"], kind == "instagram_reel")
            if "error" in ins:
                errors += 1
                snap.setdefault("insights_error", ins["error"])
                continue
            data["posts"][r["id"]] = {"date": e["date"], "kind": kind, "topic": e.get("topic"), "title": e.get("title"),
                                      "mode": e.get("mode"), "updated": today, **ins}
    data["daily"].append(snap)
    data["daily"] = data["daily"][-400:]
    METRICS.write_text(json.dumps(data, indent=1))
    print(f"track: followers={snap.get('followers')} posts tracked={len(data['posts'])} errors={errors}")


if __name__ == "__main__":
    main()
