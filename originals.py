"""Den originals watcher: every story published on theinnovatorsden.net gets its own carousel.

Each autopost run (every 2 hours, 9am to 9pm ET) asks the site for Den originals
(source "The Innovators Den"). Any live story from the last LOOKBACK_DAYS that has not had a
carousel yet is written up by Claude in the Den template and posted on that run, ahead of the
trend desk and the scheduled queue (one per run, so several new stories post 2 hours apart).

originals.json remembers which stories were handled, so nothing ever posts twice. Stories that
already had a hand-made carousel (same title in manual/queue, manual/done or posted.json) are
skipped and marked handled.
"""
import json, os, re, pathlib, datetime as dt, urllib.request, urllib.parse
from zoneinfo import ZoneInfo
import pick as P

ET = ZoneInfo("America/New_York")
SITE = os.environ.get("DEN_SITE", "https://theinnovatorsden.net").rstrip("/")
SEEN = P.ROOT / "originals.json"
LOOKBACK_DAYS = int(os.environ.get("ORIGINALS_LOOKBACK_DAYS") or 7)
SOURCE = "The Innovators Den"

SUB_BRAND = {"Innovation": "BRAIN TRUST", "Art": "FRAME ROOM", "Culture": "THE STOOP", "Music": "TARIMA",
             "Business Growth": "THE MARGIN", "Business": "THE MARGIN", "Sports": "WALK-OFF",
             "Food & Wine": "BRINDIS", "Food": "BRINDIS", "Dining": "BRINDIS", "Health": "SECOND WIND",
             "Travel": "CARRY-ON CULTURE", "Astrology": "RISING SIGN", "Law": "COUNSEL HOUR",
             "Finance": "CAPITAL CIPHER", "Spotlight": "THE DEBUT"}


def norm(t):
    return re.sub(r"[^a-z0-9]+", " ", P.clean(t).lower()).strip()


def load_seen():
    return P.load(SEEN, {"seen": {}})


def fetch():
    q = urllib.parse.urlencode({"sourceName": SOURCE, "status": "approved", "includeContent": "1", "limit": 60})
    return P.get(f"{SITE}/api/articles?{q}")


def already_made():
    """Titles that already have a carousel (queued, done or posted)."""
    titles = {norm(e.get("title", "")) for e in P.load(P.POSTED, []) if not e.get("dry_run")}
    for d in ("queue", "done"):
        for f in (P.ROOT / "manual" / d).glob("*.json"):
            try: titles.add(norm(json.loads(f.read_text()).get("title", "")))
            except Exception: pass
    return titles - {""}


def live_at(a):
    for k in ("publishAt", "createdAt"):
        if a.get(k):
            try: return dt.datetime.fromisoformat(a[k].replace("Z", "+00:00"))
            except Exception: pass
    return None


def next_original(say=print):
    """Oldest new, live Den original that still needs a carousel. Returns (story, seen_state)."""
    state = load_seen()
    seen = state.setdefault("seen", {})
    made = already_made()
    now = dt.datetime.now(dt.timezone.utc)
    todo = []
    for a in fetch():
        if a.get("sourceName") != SOURCE or a.get("status") not in (None, "approved") or a["id"] in seen:
            continue
        at = live_at(a)
        if not at or at > now or (now - at).days >= LOOKBACK_DAYS:
            continue
        if norm(a["title"]) in made:
            seen[a["id"]] = {"title": P.clean(a["title"]), "how": "already had a carousel",
                             "at": dt.datetime.now(ET).isoformat(timespec="minutes")}
            continue
        body = P.clean(a.get("content") or "")
        if len(body) < 600:
            say(f"original '{a['title']}' has no full text yet, will retry next run")
            continue
        todo.append((at, {**a, "title": P.clean(a["title"]), "body": body[:14000]}))
    todo.sort(key=lambda x: x[0])
    return (todo[0][1] if todo else None), state


PROMPT = """You make Instagram carousels for The Innovators Den, a NYC media network for Black, Brown, Latino and underrepresented innovators. Tagline: "For Us. By Us."

This is one of the Den's OWN original stories, written by its founder and published on theinnovatorsden.net, bylined "By The Innovators Den". Turn it into a carousel (up to 10 slides total) plus captions that make people stop, swipe to the end and tap the link in bio for the full story.

Voice: keep the story's own voice. It is the Den's writing, so carry over its wordplay, metaphors, double and triple meanings and its strongest lines (you may reuse its exact phrases). Confident, culture-forward, NYC energy, warm, never corporate. The carousel must still tell the story COMPLETELY: someone who only swipes should get the whole arc.

Return ONLY valid JSON matching this schema:
{
 "hook": "cover headline, max 55 characters, the single most striking word or number wrapped in *asterisks*. Stop the scroll in under 2 seconds with the story's sharpest tension, image or line. Never a generic label",
 "dek": "one sentence, max 90 characters",
 "slides": [ {"label": "1-3 words", "text": "..."}, "... 3 to 8 story slides in the story's own order, the last one lands the meaning ..." ],
 "cta_line": "punchy closing line, max 40 characters, one phrase in *asterisks*",
 "question": "max 90 characters. ONE low-effort question specific to this story, answerable in 1 to 5 words (this-or-that, rate it, your experience, fill in the blank). Never 'Thoughts?'",
 "first_comment": "the Den's own first comment, max 150 characters: one extra detail from the story or a follow-up question. Conversational, no hashtags, no links",
 "photo_subjects": ["exact English Wikipedia article title of the main place, person or thing, best first", "up to 2 fallbacks"],
 "photo_caption": "max 70 characters naming what the cover image shows, only facts from the story",
 "caption_instagram": "120-180 words. First sentence restates the hook and naturally includes the 2-3 words people would search for this story. 3 short paragraphs in the story's voice. End with the question, then one share prompt naming who should get it, then 'Full story: link in bio.' then 3-5 specific hashtags incl #TheInnovatorsDen and the sub-brand hashtag (#{brand_tag})",
 "caption_reel": "40-80 words: keyword-rich first sentence, the 2 strongest moments, the question, the share prompt, the same hashtags",
 "caption_facebook": "80-130 words, conversational, ends with the question, then 'Read the full story: {url}'. No hashtags except #TheInnovatorsDen",
 "caption_linkedin": "120-200 words, a sharper angle for founders, operators and creatives, short paragraphs, end with the question, then 'Full story: {url}', 3 hashtags max"
}
Slide rules (the cover and closing slide are added automatically):
- 3 to 8 story slides, as many as the story needs. Every slide is a complete thought: no cliffhangers, no sentence split across slides, no "..." endings.
- Each slide "text" is 60 to 160 characters. Wrap 1-2 key phrases per slide in *asterisks*.
Hard rules:
- Use ONLY facts, names, numbers and quotes that are in the story. Never invent anything.
- Never use em dashes or en dashes anywhere. Use commas, periods or parentheses.
- If the story touches faith, spiritual practice, family or anyone's private life, stay as respectful and discreet as the story itself is. Do not add detail it does not give.
- No partisan political takes. No buzzwords (synergy, leverage, elevate, game-changer, revolutionize).

Sub-brand: {brand} (topic: {topic})
Story URL: {url}
Headline: {title}
Dek: {summary}
Story:
{body}
"""


def write_copy(story):
    url = story.get("sourceUrl") or SITE
    brand = SUB_BRAND.get(story.get("topic"), "THE INNOVATORS DEN")
    tag = re.sub(r"[^A-Za-z]", "", brand.title())
    prompt = (PROMPT.replace("{brand_tag}", tag).replace("{brand}", brand).replace("{topic}", story.get("topic") or "")
              .replace("{url}", url).replace("{title}", story["title"]).replace("{summary}", P.clean(story.get("summary")))
              .replace("{body}", story["body"]))

    def ask(msgs):
        res = P.post_anthropic({"model": P.MODEL, "max_tokens": 16000, "messages": msgs})
        text = "".join(b.get("text", "") for b in res["content"] if b.get("type") == "text")
        return json.loads(text[text.find("{"): text.rfind("}") + 1])

    msgs = [{"role": "user", "content": prompt}]
    c = ask(msgs)
    probs = P.validate(c)
    if probs:
        print("revising copy:", probs)
        c2 = ask(msgs + [{"role": "assistant", "content": json.dumps(c)},
                         {"role": "user", "content": "Fix these problems and return the full corrected JSON only: " + "; ".join(probs)}])
        c = c2 if len(P.validate(c2)) < len(probs) else c
    c["slides"] = P.fit(c["slides"])
    c = P.scrub(c)
    for k in [k for k in c if k.startswith("caption_")]:
        c[k] = c[k].replace("*", "")
    c["kicker"] = brand
    return c


def story_photo(story, dest):
    """The story's own featured image from the site, used on the cover."""
    img = story.get("imageUrl")
    if not img: return None
    url = img if img.startswith("http") else SITE + "/" + img.lstrip("/")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "den-autopost/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        if len(data) < 5000: return None
        pathlib.Path(dest).write_bytes(data)
        return {"path": str(dest), "credit": "Image: The Innovators Den", "subject": story["title"]}
    except Exception as e:
        print("story image download failed:", e)
        return None


def build_post(story, out_dir, say=print):
    copy = write_copy(story)
    post = {**copy, "story_id": "den-original-" + story["id"], "topic": story.get("topic") or "Culture",
            "title": story["title"], "source_name": SOURCE, "source_url": story.get("sourceUrl") or SITE,
            "credit_line": "By The Innovators Den", "writer": "claude", "mode": "original", "trend": None}
    ph = story_photo(story, out_dir / "photo.jpg")
    if not ph:
        try:
            from photo import find_photo
            ph = find_photo(copy.get("photo_subjects") or [], out_dir / "photo.jpg")
        except Exception as e:
            say(f"photo lookup failed: {e}")
    if ph:
        ph["caption"] = copy.get("photo_caption") or ph["subject"]
        post["photo"] = ph
        say(f"cover photo: {ph['credit']}")
    return post


def mark(state, story, how):
    state.setdefault("seen", {})[story["id"]] = {"title": story["title"], "how": how,
                                                 "at": dt.datetime.now(ET).isoformat(timespec="minutes")}
    return state


if __name__ == "__main__":
    s, _ = next_original()
    print("next original:", s and s["title"])
