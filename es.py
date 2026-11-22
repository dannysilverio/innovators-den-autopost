"""Spanish Instagram for The Innovators Den: every carousel, rewritten in Spanish, carousels only.

Dormant until IG_ES_USER_ID and IG_ES_ACCESS_TOKEN are set (same pattern as Threads and YouTube).

  python es.py build   translate + render this run's jobs into public/es/<run_id>/ and write build/es/jobs.json
  python es.py post    publish those jobs to the Spanish account and log them in es/log.json

Each run handles up to two jobs:
  live     the carousel the English account just posted on this run (build/post.json)
  catchup  the next past carousel from es/queue.json, oldest first, max ES_CATCHUP_PER_DAY a day (default 6)

What the Spanish account gets: the carousel only. No Reels, no Stories, no collaborator invites.
Every post tags the main account on the cover and mentions it in the caption (ES_MAIN_HANDLE).
Hand-built carousels (prerendered_dir) keep their original slides; only the caption is in Spanish.
Nothing here can block or change an English post: the workflow runs it last and ignores its failures.
"""
import json, os, re, sys, shutil, pathlib, time, datetime as dt
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).parent
QUEUE, LOG, SRC = ROOT / "es/queue.json", ROOT / "es/log.json", ROOT / "es/source"
PUB, BUILD = ROOT / "public/es", ROOT / "build/es"
ET = ZoneInfo("America/New_York")
REPO = os.environ.get("GITHUB_REPOSITORY", "dannysilverio/innovators-den-autopost")
RAW = f"https://raw.githubusercontent.com/{REPO}/main"
MAIN = (os.environ.get("ES_MAIN_HANDLE") or "theinnovatorsden").lstrip("@")
PER_DAY = int(os.environ.get("ES_CATCHUP_PER_DAY") or 6)
MAX_TRIES = 3
DRY = os.environ.get("DRY_RUN") == "1"

TOPIC_ES = {"Innovation": "Innovación", "Business Growth": "Negocios", "Business": "Negocios", "Finance": "Finanzas",
            "Culture": "Cultura", "Art": "Arte", "Music": "Música", "Sports": "Deportes", "Health": "Salud",
            "Dining": "Comida y Vino", "Food & Wine": "Comida y Vino", "Food": "Comida y Vino", "Travel": "Viajes",
            "Law": "Leyes", "Spotlight": "En Foco", "Astrology": "Astrología"}

# Fixed labels printed by render.py and covers.py (the story text itself comes translated in the post)
UI = [("SWIPE &rarr;", "DESLIZA &rarr;"), ("Swipe for the full story &rarr;", "Desliza para leer la historia &rarr;"),
      ("COMMENT YOUR ANSWER &darr;", "COMENTA TU RESPUESTA &darr;"), (">SEND TO A FRIEND<", ">ENVÍALO A UN AMIGO<"),
      (">FOLLOW<", ">SÍGUENOS<"), ("FOR US. BY US.", "POR Y PARA NOSOTROS."),
      ("For Us. By Us.", "Por y para nosotros."), ("Full story: link in bio", "Historia completa: enlace en la bio"),
      ("Continued inside", "Continúa adentro"), (">DEN NEWS<", ">DEN NOTICIAS<")]


def localize(doc):
    for a, b in UI:
        doc = doc.replace(a, b)
    return re.sub(r">([^<>]{3,12}) ISSUE<", r">EDICIÓN \1<", doc)  # magazine cover: "22 NOV ISSUE"


def say(m): print(f"es: {m}", flush=True)
def load(p, default): return json.loads(p.read_text()) if p.exists() else default
def now(): return dt.datetime.now(ET)


# ---------- translation ----------
PROMPT = """You are the Spanish-language editor of The Innovators Den, a New York media brand (Dominican-born, Bronx-raised founder).
Rewrite this Instagram carousel in Spanish for the Den's Spanish Instagram account.

Voice: natural, warm Latin American Spanish the way a bilingual New York editor writes it. Clear for readers in the
Dominican Republic, Puerto Rico, Mexico, Colombia and US Latinos alike. Rewrite, do not translate word for word: the
hook has to hit as hard in Spanish as it does in English. No stiff or textbook phrasing, no regional slang that only one
country understands.

Hard rules:
- Every fact, name, number, date, time, score, price and quote stays exactly as in the English. Add nothing, drop nothing.
- Names of people, brands, teams, shows, venues and Den sections (Brindis, Tarima, Walk-Off, The Stoop, Brain Trust,
  Frame Room, The Margin, Second Wind, Carry-On Culture, Rising Sign, Counsel Hour, Capital Cipher, The Debut) stay as is.
- Keep the *asterisks*: wrap the Spanish words that carry the same emphasis. Same number of slides, same order.
- Never use em dashes or en dashes. Use commas, periods or parentheses. Use opening marks (¿ ¡) correctly.
- Keep each text about the same length as the English (Spanish can run up to 15% longer, never more), so it fits the slide.
- "label" stays 1 to 3 words. "kicker": keep a Den section name as is; translate a generic one (BREAKING = ÚLTIMA HORA).
- caption: the Instagram caption in Spanish. Open with the words a Spanish speaker would type into search to find this
  story. Keep the paragraph breaks and the closing question or call to tag someone. No hashtags, no @mentions, no links,
  and leave out the "full story, link in bio" line (they are added afterwards).
- hashtags: 3 hashtags Spanish speakers actually search for this story (names, teams, the topic). No #TheInnovatorsDen.
- Return JSON only, with exactly these keys:
{"hook": "", "dek": "", "kicker": "", "slides": [{"label": "", "text": ""}], "cta_line": "", "question": "",
 "first_comment": "", "photo_caption": "", "caption": "", "hashtags": ["#", "#", "#"]}

English carousel:
"""


def _ask(payload, feedback=None, previous=None):
    import pick as P
    msgs = [{"role": "user", "content": PROMPT + json.dumps(payload, ensure_ascii=False, indent=1)}]
    if feedback:
        msgs += [{"role": "assistant", "content": json.dumps(previous, ensure_ascii=False)},
                 {"role": "user", "content": "Fix these problems and return the full corrected JSON only: " + "; ".join(feedback)}]
    res = P.post_anthropic({"model": os.environ.get("ES_MODEL") or P.MODEL, "max_tokens": 16000, "messages": msgs})
    text = "".join(b.get("text", "") for b in res["content"] if b.get("type") == "text")
    return json.loads(text[text.find("{"): text.rfind("}") + 1])


def _problems(src, out):
    bad = []
    n = len(src.get("slides") or [])
    if len(out.get("slides") or []) != n:
        bad.append(f"slides must have exactly {n} items")
    for k in ("hook", "caption", "question"):
        if src.get("caption_instagram" if k == "caption" else k) and not str(out.get(k) or "").strip():
            bad.append(f"{k} is empty")
    if re.search(r"[—–]", json.dumps(out, ensure_ascii=False)):
        bad.append("remove every em dash and en dash")
    if len((out.get("hook") or "").replace("*", "")) > max(60, len((src.get("hook") or "").replace("*", "")) * 1.3):
        bad.append("hook is too long for the cover, tighten it")
    for i, (a, b) in enumerate(zip(src.get("slides") or [], out.get("slides") or []), 1):
        if len(b.get("text") or "") > max(140, len(a.get("text") or "") * 1.3):
            bad.append(f"slide {i} text is too long, tighten it")
    return bad


def _scrub(o):
    if isinstance(o, str): return re.sub(r"\s*[—–]\s*", ", ", o)
    if isinstance(o, list): return [_scrub(x) for x in o]
    if isinstance(o, dict): return {k: _scrub(v) for k, v in o.items()}
    return o


def translate(src):
    payload = {k: src.get(k) for k in ("topic", "title", "hook", "dek", "kicker", "slides", "cta_line", "question",
                                       "first_comment", "photo_caption")}
    payload["caption"] = src.get("caption_instagram") or src.get("caption_facebook") or ""
    out = _ask(payload)
    bad = _problems(src, out)
    if bad:
        say("fixing: " + "; ".join(bad))
        out = _ask(payload, bad, out)
        if len(out.get("slides") or []) != len(src.get("slides") or []):
            raise RuntimeError("translator returned the wrong number of slides twice")
    return _scrub(out)


def caption(tr, src):
    tags, seen = [], set()
    import viral as V
    brand = "#" + re.sub(r"[^A-Za-z]", "", V.SUB_BRAND.get(src.get("topic"), ""))  # the Den section, e.g. #WalkOff
    for t in [*(tr.get("hashtags") or []), "#TheInnovatorsDen", brand]:
        t = "#" + re.sub(r"[^\w]", "", str(t).lstrip("#"))
        if len(t) > 2 and t.lower() not in seen and len(tags) < 5:   # Instagram's cap is 5
            seen.add(t.lower()); tags.append(t)
    body = re.sub(r"[ \t]*#\w+", "", tr.get("caption") or "").strip()
    tail = f"\n\nHistoria completa: enlace en la bio.\nEdición en inglés: @{MAIN}\n" + " ".join(tags)
    return body[: 2150 - len(tail)].rstrip() + tail


def spanish_post(src):
    """The English post dict -> the Spanish post dict render.py and publish.instagram understand."""
    tr = translate(src)
    post = {k: v for k, v in src.items() if k not in ("platform_copy", "ig_collaborators_exact", "ig_delete", "only",
                                                       "caption_reel", "video_file", "ig_stories")}
    for k in ("hook", "dek", "kicker", "cta_line", "question", "first_comment"):
        if tr.get(k): post[k] = tr[k]
    if src.get("slides"): post["slides"] = tr["slides"]
    post["lang"] = "es"
    post["topic_label"] = TOPIC_ES.get(src.get("topic"), src.get("topic"))
    credit = src.get("credit_line") or ""
    post["credit_line"] = ("Por " + credit[3:]) if credit.lower().startswith("by ") else (credit or f"vía {src.get('source_name', '')}")
    post["caption_instagram"] = caption(tr, src)
    post["hashtags"] = re.findall(r"#\w+", post["caption_instagram"])
    # Tag the main account on the cover, plus any featured venue or brand the English post named
    extra = [str(u).lstrip("@").strip() for u in [*(src.get("ig_collaborators") or []), *(src.get("ig_collaborators_exact") or [])]]
    team = {"formerlyknownashashtag", "mr_a_plus", "wstudiosnj", MAIN.lower()}
    people = [MAIN] + [u for u in dict.fromkeys(extra) if u and u.lower() not in team][:9]
    post["ig_user_tags"] = {"0": [{"username": u, "x": round((i + 1) / (len(people) + 1), 2), "y": 0.86} for i, u in enumerate(people)]}
    post["ig_collaborators"] = []
    if tr.get("photo_caption") and isinstance(post.get("photo"), dict):
        post["photo"] = {**post["photo"], "caption": tr["photo_caption"]}
    return post


# ---------- cover photo for catch-ups (the original photo file is gone, so find it again) ----------
_stories = None
def refetch_photo(src, post, work):
    ph = src.get("photo")
    if not isinstance(ph, dict): return
    if ph.get("path") and pathlib.Path(ph["path"]).exists(): return
    new = None
    try:
        if str(src.get("story_id", "")).startswith("den-original-"):
            import originals as O
            global _stories
            if _stories is None: _stories = O.fetch()
            st = next((a for a in _stories if "den-original-" + str(a.get("id")) == src["story_id"]), None)
            if st: new = O.story_photo(st, work / "photo.jpg")
        if not new and src.get("photo_subjects"):
            from photo import find_photo
            new = find_photo(src["photo_subjects"], work / "photo.jpg")
    except Exception as e:
        say(f"cover photo lookup failed: {e}")
    if new:
        post["photo"] = {**new, "caption": post.get("photo", {}).get("caption") or new.get("subject"),
                         **({"focus": ph["focus"]} if ph.get("focus") else {})}
    else:
        post.pop("photo", None)  # covers.py falls back to the classic text cover


# ---------- build ----------
def _done(log):
    ok = {k for k, v in log.items() if v.get("ok")}
    return ok, {v.get("story_id") for k, v in log.items() if v.get("ok") and v.get("story_id")}


def _make(kind, run_id, src):
    out = PUB / run_id
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True)
    post = spanish_post(src)
    pre = src.get("prerendered_dir")
    if pre:  # hand-built slides: reuse the originals, Spanish caption only
        files = sorted(p.name for p in (ROOT / pre).glob("carousel_*.png"))
        if not files: raise RuntimeError(f"no slides left in {pre}")
        urls = [f"{RAW}/{pre}/{f}" for f in files]
    else:
        import render
        work = BUILD / run_id; work.mkdir(parents=True, exist_ok=True)
        refetch_photo(src, post, work)
        render.render(post, work)
        files = sorted(p.name for p in work.glob("carousel_*.png"))
        for f in files: shutil.copy(work / f, out / f)
        urls = [f"{RAW}/public/es/{run_id}/{f}" for f in files]
    urls = urls[:20]  # Instagram carousel limit
    (out / "post.json").write_text(json.dumps(post, indent=1, ensure_ascii=False))
    say(f"{kind} built: {post['hook'].replace('*', '')[:70]} ({len(urls)} slides{', original art' if pre else ''})")
    return {"kind": kind, "run_id": run_id, "story_id": src.get("story_id"), "title": src.get("title"), "urls": urls}


def build():
    log = load(LOG, {})
    ok_runs, ok_stories = _done(log)
    BUILD.mkdir(parents=True, exist_ok=True); PUB.mkdir(parents=True, exist_ok=True)
    for d in PUB.iterdir():  # slides from earlier runs are already on Instagram
        if d.is_dir(): shutil.rmtree(d)
    jobs, picked = [], set()

    def attempt(kind, run_id, src):
        try:
            jobs.append(_make(kind, run_id, src)); picked.add(src.get("story_id"))
        except Exception as e:
            say(f"{kind} {run_id} build FAILED: {e}")
            ent = log.get(run_id, {})
            log[run_id] = {**ent, "ok": False, "kind": kind, "story_id": src.get("story_id"), "title": src.get("title"),
                           "tries": ent.get("tries", 0) + 1, "at": now().isoformat(timespec="minutes"), "error": f"build: {str(e)[:300]}"}

    # 1) the carousel the English account posted on this run
    live, run_id = ROOT / "build/post.json", os.environ.get("RUN_ID")
    if live.exists() and run_id and not DRY:
        src = json.loads(live.read_text())
        only = set(src.get("only") or [])
        if only and "instagram" not in only:
            say("live post did not go to Instagram, skipping")
        elif src.get("story_id") in ok_stories:
            say("this story is already on the Spanish account (a re-post), skipping")
        else:
            (SRC / f"{run_id}.json").write_text(json.dumps(src, indent=1, ensure_ascii=False))  # kept so a failed post can retry as a catch-up
            attempt("live", run_id, src)

    # 2) one past carousel, oldest first
    today = now().strftime("%Y-%m-%d")
    done_today = sum(1 for v in log.values() if v.get("ok") and v.get("kind") == "catchup" and str(v.get("at", "")).startswith(today))
    if PER_DAY > 0 and done_today < PER_DAY and 8 <= now().hour < 22:
        items = load(QUEUE, {"items": []})["items"]
        # a live post that failed earlier joins the line too
        known = {i["run_id"] for i in items}
        items += [{"run_id": k, "story_id": v.get("story_id")} for k, v in log.items() if not v.get("ok") and k not in known]
        for it in items:
            rid = it["run_id"]
            if it.get("skip") or rid in ok_runs or it.get("story_id") in (ok_stories | picked): continue
            if log.get(rid, {}).get("tries", 0) >= MAX_TRIES: continue
            if any(j["run_id"] == rid for j in jobs) or not (SRC / f"{rid}.json").exists(): continue
            attempt("catchup", rid, json.loads((SRC / f"{rid}.json").read_text()))
            break
        else:
            say("catch-up: all caught up")
    else:
        say(f"catch-up: resting ({done_today}/{PER_DAY} today)")
    (BUILD / "jobs.json").write_text(json.dumps(jobs, indent=1, ensure_ascii=False))
    LOG.parent.mkdir(exist_ok=True); LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False))
    say(f"{len(jobs)} job(s) ready")


# ---------- post ----------
def post_all():
    import publish as P
    jobs = load(BUILD / "jobs.json", [])
    if not jobs: say("nothing to post"); return
    log = load(LOG, {})
    # publish.instagram reads its account from the environment: point it at the Spanish account for this process only
    os.environ["IG_USER_ID"], os.environ["IG_ACCESS_TOKEN"] = os.environ["IG_ES_USER_ID"], os.environ["IG_ES_ACCESS_TOKEN"]
    if os.environ.get("IG_ES_GRAPH_HOST"): os.environ["IG_GRAPH_HOST"] = os.environ["IG_ES_GRAPH_HOST"]
    os.environ["IG_COLLABORATORS"] = os.environ.get("IG_ES_COLLABORATORS") or "none"
    for n, job in enumerate(jobs):
        rid = job["run_id"]
        post = json.loads((PUB / rid / "post.json").read_text())
        ent = log.get(rid, {})
        base = {"kind": job["kind"], "story_id": job.get("story_id"), "title": job.get("title"),
                "at": now().isoformat(timespec="minutes"), "tries": ent.get("tries", 0) + 1}
        if DRY:
            say(f"[dry] {job['kind']} {rid}: {len(job['urls'])} slides\n{post['caption_instagram']}"); continue
        if n: time.sleep(60)
        try:
            r = P.instagram(post, job["urls"])
            log[rid] = {**base, "ok": True, "id": r["id"]}
            say(f"{job['kind']} posted {r['id']}: {str(job.get('title'))[:60]}")
            if post.get("first_comment"):
                try:
                    host = os.environ.get("IG_GRAPH_HOST") or "graph.instagram.com"
                    P.http("POST", f"https://{host}/{os.environ.get('IG_API_VERSION', 'v21.0')}/{r['id']}/comments",
                           {"message": post["first_comment"], "access_token": os.environ["IG_ACCESS_TOKEN"]})
                except Exception as ce:
                    say(f"first comment skipped: {str(ce)[:150]}")
        except Exception as e:
            log[rid] = {**base, "ok": False, "error": str(e)[:500]}
            say(f"{job['kind']} {rid} FAILED: {e}")
        LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    if not (os.environ.get("IG_ES_USER_ID") and os.environ.get("IG_ES_ACCESS_TOKEN")) and not DRY:
        say("not set up yet (IG_ES_USER_ID / IG_ES_ACCESS_TOKEN missing)"); sys.exit(0)
    {"build": build, "post": post_all}[sys.argv[1] if len(sys.argv) > 1 else "build"]()
