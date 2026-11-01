"""Publish build/post.json + rendered slides to Instagram, Facebook Page, LinkedIn company page,
Threads and YouTube Shorts.

Each platform runs independently: one failing never blocks the others.
Threads and YouTube switch on by themselves once their secrets exist (no PLATFORMS change needed).
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
AUTO = {"threads": ("THREADS_USER_ID", "THREADS_ACCESS_TOKEN"),
        "youtube": ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")}


def enabled(name):
    """PLATFORMS still governs IG/FB/LinkedIn; Threads and YouTube turn on when their secrets are set."""
    if name in AUTO:
        return all(os.environ.get(k) for k in AUTO[name])
    return name in ENABLED

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

# ---------- Threads (carousel, same images) ----------
TH_BASE = "https://graph.threads.net/v1.0"


def threads_text(post, limit=500):
    """Threads allows 500 characters and one topic tag. Trim on a paragraph/sentence boundary."""
    s = post.get("caption_threads") or post.get("caption_facebook") or post["caption_instagram"]
    s = re.sub(r"\s*#\w+", "", s).replace("link in bio", "link in profile").strip()
    tag = " #TheInnovatorsDen"
    room = limit - len(tag)
    if len(s) > room:
        cut = s[:room]
        for sep in ("\n\n", ". ", "? ", "! "):
            i = cut.rfind(sep)
            if i > room * 0.5:
                cut = cut[: i + (1 if sep != "\n\n" else 0)]
                break
        s = cut.rstrip()
    return s + tag


_th_checked = False


def _threads_refresh(tok):
    """Long-lived Threads tokens last 60 days; refreshing extends them. Runs once per process, never blocks."""
    global _th_checked
    if _th_checked:
        return
    _th_checked = True
    try:
        r, _ = http("GET", f"https://graph.threads.net/refresh_access_token?grant_type=th_refresh_token&access_token={tok}")
        if r.get("access_token") and r["access_token"] != tok:
            print("threads: WARNING Meta issued a new token string; update the THREADS_ACCESS_TOKEN secret")
    except Exception as e:
        print(f"threads: token refresh skipped ({str(e)[:120]})")


def threads(post, urls):
    uid, tok = os.environ["THREADS_USER_ID"], os.environ["THREADS_ACCESS_TOKEN"]
    _threads_refresh(tok)
    kids = []
    for u in urls[:20]:
        r, _ = http("POST", f"{TH_BASE}/{uid}/threads",
                    {"media_type": "IMAGE", "image_url": u, "is_carousel_item": "true", "access_token": tok})
        kids.append(r["id"])
    # Each slide must finish processing before the carousel can use it, or Threads answers
    # "Invalid Carousel Children ... invalid, nonexistent, or expired" (error_subcode 4279004).
    for kid in kids:
        for _ in range(36):  # up to ~3 minutes per slide; usually a few seconds
            s, _ = http("GET", f"{TH_BASE}/{kid}?fields=status,error_message&access_token={tok}")
            if s.get("status") == "FINISHED": break
            if s.get("status") in ("ERROR", "EXPIRED"): raise RuntimeError(f"Threads slide {kid} {s}")
            time.sleep(5)
        else:
            raise RuntimeError(f"Threads slide {kid} still not ready after 3 minutes")
    r, _ = http("POST", f"{TH_BASE}/{uid}/threads", {"media_type": "CAROUSEL", "children": ",".join(kids),
                                                     "text": threads_text(post), "access_token": tok})
    cid = r["id"]
    for _ in range(24):  # Meta recommends ~30s before publishing; poll until ready
        time.sleep(5)
        s, _ = http("GET", f"{TH_BASE}/{cid}?fields=status,error_message&access_token={tok}")
        if s.get("status") == "FINISHED": break
        if s.get("status") in ("ERROR", "EXPIRED"): raise RuntimeError(f"Threads container {s}")
    r, _ = http("POST", f"{TH_BASE}/{uid}/threads_publish", {"creation_id": cid, "access_token": tok})
    return {"id": r["id"]}


# ---------- YouTube Shorts (vertical slideshow of the carousel) ----------
def youtube(post, video_file):
    f = pathlib.Path(video_file)
    if not f.exists():
        raise RuntimeError("no build/short.mp4 (slideshow render failed)")
    t, _ = http("POST", "https://oauth2.googleapis.com/token", {
        "client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"})
    auth = {"Authorization": f"Bearer {t['access_token']}"}
    title = re.sub(r"[<>]", "", post.get("hook") or post["title"]).strip()
    title = (title[:88].rsplit(" ", 1)[0] if len(title) > 88 else title) + " #Shorts"
    desc = re.sub(r"[<>]", "", post.get("caption_facebook") or post["caption_instagram"])
    meta = {"snippet": {"title": title, "description": f"{desc}\n\n#Shorts #TheInnovatorsDen"[:4900],
                        "tags": ["The Innovators Den", "For Us By Us", str(post.get("topic") or "")][:3],
                        "categoryId": "22"},
            "status": {"privacyStatus": os.environ.get("YT_PRIVACY", "public"), "selfDeclaredMadeForKids": False}}
    _, hdr = http("POST", "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                  meta, {**auth, "Content-Type": "application/json", "X-Upload-Content-Type": "video/mp4",
                         "X-Upload-Content-Length": str(f.stat().st_size)})
    loc = hdr.get("Location") or hdr.get("location")
    r, _ = http("PUT", loc, raw=f.read_bytes(), headers={**auth, "Content-Type": "video/mp4"})
    return {"id": r.get("id"), "privacy": (r.get("status") or {}).get("privacyStatus")}


def main():
    post = json.loads((ROOT / "build/post.json").read_text())
    run_id, base = os.environ.get("RUN_ID", "local"), os.environ.get("IMAGE_BASE_URL", "")
    files = sorted(str(p) for p in (ROOT / "build/slides").glob("carousel_*.png"))
    urls = [f"{base.rstrip('/')}/{run_id}/{pathlib.Path(f).name}" for f in files]
    results = {}
    reel_file = ROOT / "build/reel.mp4"
    reel_url = f"{base.rstrip('/')}/{run_id}/reel.mp4"
    jobs = [("instagram", instagram, urls), ("facebook", facebook, urls), ("linkedin", linkedin, files),
            ("threads", threads, urls), ("youtube", youtube, str(ROOT / "build/short.mp4"))]
    if reel_file.exists() and os.environ.get("REELS", "1") != "0" and urls:
        jobs.insert(1, ("instagram_reel", lambda p, u: instagram_reel(p, u, urls[0]), reel_url))
    for name, fn, arg in jobs:
        if not enabled(name.split("_")[0]): continue
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
