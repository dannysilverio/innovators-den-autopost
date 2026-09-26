"""Trend scout: decides IF and WHAT to post this run, then writes build/post.json.

Runs every 2 hours (8am to 9pm ET). Rules:
- Mon/Wed/Fri: a baseline post is guaranteed from 11am on (trending story if there is one, otherwise the category rotation).
- Any day: an extra post goes out when Claude confirms (via live web search) that a story in the Den's topics is trending hard.
- Caps: 2 posts max on Mon/Wed/Fri, 1 on other days, at least 3 hours apart, never the same story twice.
If nothing qualifies, it writes nothing and the workflow stops quietly.
"""
import json, os, re, sys, pathlib, datetime as dt, urllib.request, urllib.parse
from zoneinfo import ZoneInfo
import pick as P

ET = ZoneInfo("America/New_York")
TOPICS = ["Innovation", "Art", "Culture", "Music", "Business Growth", "Sports", "Dining", "Health",
          "Travel", "Astrology", "Law", "Finance", "Spotlight"]
TREND_MIN = int(os.environ.get("TREND_MIN_SCORE") or 8)      # 1-10, how hard a story must be trending for an extra post
BASELINE_DAYS = {0, 2, 4}                                     # Mon, Wed, Fri
BASELINE_HOUR = 11
MIN_GAP_H = 3
OUT = P.ROOT / "build"

def say(msg): print(msg, flush=True)

def real_posts():
    return [e for e in P.load(P.POSTED, []) if not e.get("dry_run") and any(r.get("ok") for r in e.get("results", {}).values())]

def decide_slot(now, posts):
    today = now.strftime("%Y-%m-%d")
    todays = [e for e in posts if e["date"] == today]
    is_base_day = now.weekday() in BASELINE_DAYS
    cap = 2 if is_base_day else 1
    baseline_due = is_base_day and now.hour >= BASELINE_HOUR and not todays
    if os.environ.get("FORCE") == "1":
        return "forced", True
    if len(todays) >= cap:
        return f"daily cap reached ({len(todays)}/{cap})", False
    last = max((dt.datetime.fromisoformat(e["posted_at"]) for e in posts if e.get("posted_at")), default=None)
    if last and (now - last).total_seconds() < MIN_GAP_H * 3600 and not baseline_due:
        return "last post was under 3 hours ago", False
    if not (8 <= now.hour <= 21):
        return "outside posting hours (8am to 9pm ET)", False
    return ("baseline due" if baseline_due else "open for a trending post"), True

def den_pool(used):
    """Fresh stories (36h) from the Den feed across all topics, titles only, for the trend check."""
    arts = P.get(f"{P.API}/articles?status=approved")
    now = dt.datetime.now(dt.timezone.utc)
    pool = []
    for a in arts:
        if a.get("status") != "approved" or a.get("isSponsored") or a["id"] in used or a.get("topic") not in TOPICS: continue
        try: age = (now - dt.datetime.fromisoformat(a["createdAt"].replace("Z", "+00:00"))).total_seconds() / 3600
        except Exception: continue
        title = P.clean(a["title"])
        if age > 36 or P.BLOCK.search(title + " " + P.clean(a.get("summary") or "")[:400]): continue
        pool.append({**a, "title": title, "age_h": round(age, 1)})
    pool.sort(key=lambda a: a["age_h"])
    return pool[:90]

TREND_PROMPT = """You are the trend desk for The Innovators Den, a media network for Black, Brown, Latino and underrepresented innovators. It ONLY covers these topics: {topics}.

Right now it is {now} (US Eastern). Use web search to find out what is genuinely trending in the last 24 hours within those topics: check Google Trends / trending searches, what many major outlets are covering at once, and what is spiking on social platforms. Then decide if any story is trending hard enough to post right now.

Candidate stories already in the Den news feed (id | topic | hours old | headline):
{pool}

Stories the Den already posted recently (never pick these or the same event again):
{recent}

Rules:
- The story MUST fit one of the Den's topics. Skip partisan politics, crime, deaths, disasters, gossip, and product sales or deals.
- Strongly prefer a candidate from the Den feed (return its id). Only if a clearly bigger trending story in the Den's topics is missing from the feed, return the URL of one solid, full news article about it (a major outlet, not a video or social post).
- "score" is how hard it is trending right now, 1 to 10. 8+ means widely covered by multiple major outlets in the last 24h and showing up in trending searches. Be strict: most hours nothing is an 8.
- Always return your best pick even if the score is low.

Return ONLY JSON:
{"story_id": "den id or null", "outside_url": "url or null", "topic": "one of the Den topics", "score": 1-10, "why": "one sentence on why it's trending", "evidence": ["2-4 urls showing it's trending"]}"""

def trend_check(pool, recent):
    lines = "\n".join(f"{a['id']} | {a['topic']} | {a['age_h']}h | {a['title']}" for a in pool) or "(none)"
    prompt = (TREND_PROMPT.replace("{topics}", ", ".join(TOPICS)).replace("{pool}", lines)
              .replace("{recent}", "\n".join(f"- {t}" for t in recent) or "(none)")
              .replace("{now}", dt.datetime.now(ET).strftime("%A %b %d %Y, %I:%M %p")))
    res = P.post_anthropic({"model": P.MODEL, "max_tokens": 16000,
                            "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}],
                            "messages": [{"role": "user", "content": prompt}]})
    text = "".join(b.get("text", "") for b in res["content"] if b.get("type") == "text")
    return json.loads(text[text.rfind("{\"story_id\""):text.rfind("}") + 1] if "{\"story_id\"" in text else text[text.find("{"):text.rfind("}") + 1])

def outside_story(url, topic):
    import trafilatura
    doc = trafilatura.fetch_url(url)
    if not doc: return None
    meta = trafilatura.extract_metadata(doc)
    body = P.clean(trafilatura.extract(doc) or "")
    title = P.clean(getattr(meta, "title", "") or "")
    site = getattr(meta, "sitename", None) or urllib.parse.urlparse(url).netloc.replace("www.", "")
    if len(body) < P.MIN_BODY or not title or P.BLOCK.search(title + " " + body[:600]): return None
    return {"id": "ext:" + url, "title": title, "body": body[:12000], "topic": topic,
            "sourceName": site, "sourceUrl": url}

def den_story(a):
    body = P.clean(a.get("content") or a.get("summary"))
    if len(body) < P.MIN_BODY: body = max(body, P.full_text(a.get("sourceUrl")), key=len)
    if len(body) < P.MIN_BODY or body.rstrip().endswith(("…", "...")): return None
    return {**a, "body": body[:12000]}

def main():
    OUT.mkdir(exist_ok=True)
    now = dt.datetime.now(ET)
    posts = real_posts()
    reason, go = decide_slot(now, posts)
    baseline_due = reason in ("baseline due", "forced")
    if os.environ.get("BASELINE_ONLY") == "1" and not baseline_due:
        go, reason = False, "backup run only fills a missed Mon/Wed/Fri baseline"
    say(f"{now:%a %H:%M} ET: {reason}")
    if not go: return

    used = {e["story_id"] for e in P.load(P.POSTED, []) if not e.get("dry_run")}
    recent = [e["title"] for e in posts[-20:]]
    story, trend, mode = None, None, None

    try:
        pool = den_pool(used)
        trend = trend_check(pool, recent)
        say(f"trend check: score {trend.get('score')} | {trend.get('why')}")
        if trend.get("score", 0) >= (TREND_MIN if not baseline_due else 5):
            if trend.get("story_id"):
                a = next((x for x in pool if x["id"] == trend["story_id"]), None)
                story = den_story(a) if a else None
            elif trend.get("outside_url") and trend.get("topic") in TOPICS:
                story = outside_story(trend["outside_url"], trend["topic"])
            if story: mode = "trending"
            else: say("trending pick had no full article text available")
    except Exception as e:
        say(f"trend check failed: {e}")

    state = P.load(P.STATE, {"idx": 0})
    if not story and baseline_due:
        stories, state = P.pick()
        story, mode = stories[0], "baseline"
    if not story:
        say("nothing trending hard enough, no post this run"); return

    try:
        copy, writer = P.llm(story), "claude"
    except Exception as e:
        sys.exit(f"Copywriter failed ({e}). Not posting an incomplete story.")
    copy = P.scrub(copy)
    post = {**copy, "story_id": story["id"], "topic": story["topic"], "title": story["title"],
            "source_name": story["sourceName"], "source_url": story.get("sourceUrl"), "writer": writer,
            "mode": mode, "trend": trend}
    src = f"\n\nSource: {story['sourceName']} {story.get('sourceUrl') or ''}".rstrip()
    post["caption_facebook"] += src
    post["caption_linkedin"] += src
    (OUT / "post.json").write_text(json.dumps(post, indent=1))
    (OUT / "state.next.json").write_text(json.dumps(state))
    say(f"POSTING ({mode}) [{story['topic']}] {story['title']}")

if __name__ == "__main__":
    main()
