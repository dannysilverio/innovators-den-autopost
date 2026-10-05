"""Publish build/post.json + rendered slides to Instagram, Facebook Page and LinkedIn company page.

Each platform runs independently: one failing never blocks the others.
Images must already be public at IMAGE_BASE_URL/<run_id>/carousel_XX.png
(the workflow commits them to public/ first and uses raw.githubusercontent URLs).
Set DRY_RUN=1 to print what would be posted without calling any API.
"""
import json, os, re, sys, time, pathlib, datetime as dt, urllib.request, urllib.parse, urllib.error
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).parent
POSTED = ROOT / "posted.json"
DRY = os.environ.get("DRY_RUN") == "1"
ENABLED = set((os.environ.get("PLATFORMS") or "instagram,facebook,linkedin").split(","))

def http(method, url, data=None, headers=None, raw=None):
    h = dict(headers or {})
    body = raw
    if data is not None and raw is None:
        if h.get("Content-Type") == "application/json":
            body = json.dumps(data).encode()
        else:
            body = urllib.parse.urlencode(data).encode(); h.setdefault("Content-Type", "application/x-www-form-urlencoded")
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            txt = r.read().decode() or "{}"
            return json.loads(txt) if txt.strip().startswith(("{", "[")) else {"_raw": txt}, dict(r.headers)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {url.split('?')[0]} -> {e.code}: {e.read().decode()[:500]}")

def _warm(url, wait=90):
    """Make sure a just-committed image is actually live on the CDN before asking Instagram to fetch it."""
    end = time.time() + wait
    while time.time() < end:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=20) as r:
                r.read()
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(5)
    return False

# ---------- Instagram (Graph API content publishing) ----------
def instagram(post, urls):
    host = os.environ.get("IG_GRAPH_HOST") or "graph.instagram.com"
    ver, uid, tok = os.environ.get("IG_API_VERSION", "v21.0"), os.environ["IG_USER_ID"], os.environ["IG_ACCESS_TOKEN"]
    base = f"https://{host}/{ver}"
    kids = []
    for u in urls:
        _warm(u)
        for attempt in range(4):  # Instagram sometimes times out fetching freshly committed images; wait and retry
            try:
                r, _ = http("POST", f"{base}/{uid}/media", {"image_url": u, "is_carousel_item": "true", "access_token": tok})
                break
            except RuntimeError as e:
                if attempt == 3 or not re.search(r"Timeout|2207003|is_transient\":true|download", str(e)):
                    raise
                print(f"instagram: media fetch timed out, retry {attempt + 1} in {20 * (attempt + 1)}s")
                time.sleep(20 * (attempt + 1))
        kids.append(r["id"])
    r, _ = http("POST", f"{base}/{uid}/media", {"media_type": "CAROUSEL", "children": ",".join(kids),
                                                "caption": post["caption_instagram"], "access_token": tok})
    cid = r["id"]
    for _ in range(30):
        s, _ = http("GET", f"{base}/{cid}?fields=status_code&access_token={tok}")
        if s.get("status_code") == "FINISHED": break
        if s.get("status_code") == "ERROR": raise RuntimeError(f"IG container error {s}")
        time.sleep(5)
    r, _ = http("POST", f"{base}/{uid}/media_publish", {"creation_id": cid, "access_token": tok})
    return {"id": r["id"]}

# ---------- Instagram Reel (video version of the same story, for discovery) ----------
def _reel_container(base, uid, tok, post, cover_url, video_url=None):
    data = {"media_type": "REELS", "cover_url": cover_url, "share_to_feed": "true", "access_token": tok,
            "caption": post.get("caption_reel") or post["caption_instagram"]}
    if os.environ.get("REEL_TRIAL") == "1":  # trial reel: shown to non-followers first (needs 1,000+ followers)
        data["trial_params"] = json.dumps({"graduation_strategy": "SS_PERFORMANCE"})
    if video_url:
        data["video_url"] = video_url
    else:
        data["upload_type"] = "resumable"
    r, _ = http("POST", f"{base}/{uid}/media", data)
    return r["id"]


def _wait(base, cid, tok):
    for _ in range(60):  # videos take longer to process than images
        s, _ = http("GET", f"{base}/{cid}?fields=status_code,status&access_token={tok}")
        if s.get("status_code") == "FINISHED": return True
        if s.get("status_code") == "ERROR": return False
        time.sleep(10)
    return False


def instagram_reel(post, video_url, cover_url):
    host = os.environ.get("IG_GRAPH_HOST") or "graph.instagram.com"
    ver, uid, tok = os.environ.get("IG_API_VERSION", "v21.0"), os.environ["IG_USER_ID"], os.environ["IG_ACCESS_TOKEN"]
    base = f"https://{host}/{ver}"
    cid = _reel_container(base, uid, tok, post, cover_url, video_url)
    if not _wait(base, cid, tok):
        # fallback: upload the file bytes directly instead of having Instagram fetch the URL
        cid = _reel_container(base, uid, tok, post, cover_url)
        f = ROOT / "build/reel.mp4"
        http("POST", f"https://rupload.facebook.com/ig-api-upload/{ver}/{cid}", raw=f.read_bytes(),
             headers={"Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(f.stat().st_size)})
        if not _wait(base, cid, tok):
            raise RuntimeError("IG reel processing failed (URL and direct upload)")
    r, _ = http("POST", f"{base}/{uid}/media_publish", {"creation_id": cid, "access_token": tok})
    return {"id": r["id"]}

# ---------- Facebook Page (multi-photo post) ----------
def facebook(post, urls):
    ver, pid, tok = os.environ.get("FB_API_VERSION", "v21.0"), os.environ["FB_PAGE_ID"], os.environ["FB_PAGE_TOKEN"]
    base = f"https://graph.facebook.com/{ver}"
    ids = []
    for u in urls:
        r, _ = http("POST", f"{base}/{pid}/photos", {"url": u, "published": "false", "access_token": tok})
        ids.append(r["id"])
    data = {"message": post["caption_facebook"], "access_token": tok}
    for i, x in enumerate(ids): data[f"attached_media[{i}]"] = json.dumps({"media_fbid": x})
    r, _ = http("POST", f"{base}/{pid}/feed", data)
    return {"id": r["id"]}

# ---------- LinkedIn company page (multi-image post) ----------
RESERVED = re.compile(r"([\\|{}@\[\]()<>*_~#])")
def li_text(s):
    tags = {}
    def keep(m):
        k = f"\x00{len(tags)}\x00"; tags[k] = "{hashtag|\\#|" + m.group(1) + "}"; return k
    s = re.sub(r"#(\w+)", keep, s)
    s = RESERVED.sub(r"\\\1", s)
    for k, v in tags.items(): s = s.replace(k, v)
    return s

def linkedin(post, files):
    tok, org = os.environ["LI_ACCESS_TOKEN"], os.environ["LI_ORG_ID"]
    owner = f"urn:li:organization:{org}"
    H = {"Authorization": f"Bearer {tok}", "LinkedIn-Version": os.environ.get("LI_API_VERSION", "202509"),
         "X-Restli-Protocol-Version": "2.0.0", "Content-Type": "application/json"}
    imgs = []
    for f in files:
        r, _ = http("POST", "https://api.linkedin.com/rest/images?action=initializeUpload",
                    {"initializeUploadRequest": {"owner": owner}}, H)
        v = r["value"]
        http("PUT", v["uploadUrl"], raw=pathlib.Path(f).read_bytes(),
             headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/octet-stream"})
        imgs.append({"id": v["image"], "altText": post["title"][:120]})
    body = {"author": owner, "commentary": li_text(post["caption_linkedin"]), "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
            "content": {"multiImage": {"images": imgs}}, "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False}
    _, hdr = http("POST", "https://api.linkedin.com/rest/posts", body, H)
    return {"id": hdr.get("x-restli-id") or hdr.get("X-RestLi-Id")}

def main():
    post = json.loads((ROOT / "build/post.json").read_text())
    run_id, base = os.environ.get("RUN_ID", "local"), os.environ.get("IMAGE_BASE_URL", "")
    files = sorted(str(p) for p in (ROOT / "build/slides").glob("carousel_*.png"))
    urls = [f"{base.rstrip('/')}/{run_id}/{pathlib.Path(f).name}" for f in files]
    results = {}
    reel_file = ROOT / "build/reel.mp4"
    reel_url = f"{base.rstrip('/')}/{run_id}/reel.mp4"
    jobs = [("instagram", instagram, urls), ("facebook", facebook, urls), ("linkedin", linkedin, files)]
    if reel_file.exists() and os.environ.get("REELS", "1") != "0" and urls:
        jobs.insert(1, ("instagram_reel", lambda p, u: instagram_reel(p, u, urls[0]), reel_url))
    for name, fn, arg in jobs:
        if name.split("_")[0] not in ENABLED: continue
        if DRY:
            results[name] = {"dry_run": True}; print(f"[dry] {name}"); continue
        try:
            results[name] = {"ok": True, **fn(post, arg)}; print(f"{name}: posted {results[name]}")
            if name == "instagram" and post.get("first_comment"):
                try:  # needs the instagram_business_manage_comments permission; never blocks the post
                    host = os.environ.get("IG_GRAPH_HOST") or "graph.instagram.com"
                    c, _ = http("POST", f"https://{host}/{os.environ.get('IG_API_VERSION', 'v21.0')}/{results[name]['id']}/comments",
                                {"message": post["first_comment"], "access_token": os.environ["IG_ACCESS_TOKEN"]})
                    results["instagram_comment"] = {"ok": True, "id": c.get("id")}
                except Exception as ce:
                    results["instagram_comment"] = {"ok": False, "error": str(ce)[:300]}
        except Exception as e:
            results[name] = {"ok": False, "error": str(e)[:600]}; print(f"{name}: FAILED {e}")
    log = json.loads(POSTED.read_text()) if POSTED.exists() else []
    now = dt.datetime.now(ZoneInfo("America/New_York"))
    log.append({"date": now.strftime("%Y-%m-%d"), "posted_at": now.isoformat(timespec="minutes"), "mode": post.get("mode"),
                "run_id": run_id, "story_id": post["story_id"], "topic": post["topic"], "title": post["title"],
                "source": post["source_name"], "writer": post.get("writer"), "dry_run": DRY, "results": results})
    POSTED.write_text(json.dumps(log, indent=1))
    if not DRY and results and not any(r.get("ok") for r in results.values()):
        sys.exit("All platforms failed")

if __name__ == "__main__":
    main()
