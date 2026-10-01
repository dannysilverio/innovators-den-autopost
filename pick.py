"""Pick today's story from Innovators Den News and write the carousel + captions.

Writes build/post.json. Rotates through categories using state.json.
Copy is written by Claude (ANTHROPIC_API_KEY). If that call fails, a safe
template fallback is used so the run never posts nothing.
"""
import json, os, re, html, sys, pathlib, datetime as dt, urllib.request, urllib.parse

API = os.environ.get("DEN_API", "https://innovators-den-news--danny449.replit.app/api")
APP_LINK = os.environ.get("DEN_APP_LINK", "https://innovators-den-news--danny449.replit.app/web/")
MODEL = os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-5"
ROOT = pathlib.Path(__file__).parent
STATE, POSTED = ROOT / "state.json", ROOT / "posted.json"

CATEGORIES = ["Innovation", "Business Growth", "Culture", "Music", "Innovation", "Finance", "Art",
              "Sports", "Innovation", "Health", "Spotlight", "Dining", "Innovation", "Travel", "Law", "Astrology"]
# Innovation appears 4x in the rotation: it's the core of the brand. Every category still gets its turn.

BLOCK = re.compile(r"(\b\d+% off\b|\$\d+ off|\bdeal(s)?\b|\bsale\b|coupon|promo code|best .* \(20\d\d\)|"
                   r"\bi tested\b|\breview:|\bgift guide\b|\bshooting\b|\bkilled\b|\bdead\b|\bmurder|\bsuicide|"
                   r"\brape\b|\babuse\b|\bobituar|\bdies\b|\bdied\b|trump|biden|harris|republican|democrat|gop\b|"
                   r"election|hegseth|maga)", re.I)
MAX_AGE_H = int(os.environ.get("MAX_AGE_H", "96"))
MIN_BODY = int(os.environ.get("MIN_BODY", "1200"))  # chars of real article text required
MAX_BODY_SLIDES = 8  # cover + 8 story slides + closing slide = 10, Instagram's carousel limit

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "den-autopost/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def clean(s):
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("—", ", ").replace("–", "-")
    return re.sub(r"\s+", " ", s).strip()

def load(p, default):
    try: return json.loads(p.read_text())
    except Exception: return default

def candidates(topic, used):
    arts = get(f"{API}/articles?status=approved&topic={urllib.parse.quote(topic)}")
    now = dt.datetime.now(dt.timezone.utc)
    out = []
    for a in arts:
        if a.get("status") != "approved" or a.get("isSponsored") or a["id"] in used: continue
        try: age = (now - dt.datetime.fromisoformat(a["createdAt"].replace("Z", "+00:00"))).total_seconds() / 3600
        except Exception: continue
        title, body = clean(a["title"]), clean(a.get("content") or a.get("summary"))
        if age > MAX_AGE_H or BLOCK.search(title + " " + body[:600]): continue
        # score: fresher + richer body + has a number (numbers make strong hooks)
        score = -age + min(len(body), 3000) / 300 + (4 if re.search(r"\$?\d", title) else 0) + (a.get("aiScore") or 0) / 20
        out.append((score, {**a, "title": title, "body": body}))
    ranked = [a for _, a in sorted(out, key=lambda x: -x[0])]
    # Only stories we can tell COMPLETELY: need the full article, not an RSS teaser.
    full = []
    for a in ranked[:12]:
        if len(a["body"]) < MIN_BODY:
            a["body"] = max(a["body"], full_text(a.get("sourceUrl")), key=len)
        if len(a["body"]) >= MIN_BODY and not a["body"].rstrip().endswith(("…", "...", "[…]")):
            a["body"] = a["body"][:12000]; full.append(a)
    return full

def full_text(url):
    """Fetch the full article from the publisher when the feed only carried a snippet."""
    if not url: return ""
    try:
        import trafilatura
        html_doc = trafilatura.fetch_url(url)
        return clean(trafilatura.extract(html_doc, include_comments=False, include_tables=False) or "") if html_doc else ""
    except Exception as e:
        print("full-text fetch failed", url, e); return ""

def pick():
    state, posted = load(STATE, {"idx": 0}), load(POSTED, [])
    used = {p["story_id"] for p in posted if not p.get("dry_run")}
    for step in range(len(CATEGORIES)):
        i = (state["idx"] + step) % len(CATEGORIES)
        topic = CATEGORIES[i]
        try: c = candidates(topic, used)
        except Exception as e: print("fetch failed", topic, e); c = []
        if c:
            state["idx"] = (i + 1) % len(CATEGORIES)
            return c, state
        print(f"no fresh story in {topic}, skipping")
    sys.exit("No eligible stories in any category")

PROMPT = """You write social posts for The Innovators Den, a media network and news app for Black, Brown, Latino and underrepresented innovators. Tagline: "For Us. By Us." Voice: direct, energetic, smart, community-first. Never corporate.

Turn this news story into an Instagram carousel (up to 10 slides total) plus captions. The carousel must tell the COMPLETE story: someone who only swipes the slides, never opening the article, should know everything important that happened. Return ONLY valid JSON matching this schema:
{
 "kicker": "2-3 word label for the cover, e.g. AI WATCH, MONEY MOVES, CULTURE CHECK",
 "hook": "cover headline, max 55 characters, wrap the single most striking word/number in *asterisks*",
 "dek": "one sentence, max 90 characters",
 "slides": [ {"label": "What happened", "text": "..."}, {"label": "...", "text": "..."}, "... as many as the story needs, 3 to 8 total ...", {"label": "Why it matters", "text": "..."} ],
 "cta_line": "punchy closing line, max 40 characters, one phrase in *asterisks*",
 "question": "a real question that invites comments, max 90 characters",
 "photo_subjects": ["exact English Wikipedia article title of the main person, group, company, team or place in the story, best first", "up to 2 more fallbacks, e.g. the company or city"],
 "photo_caption": "max 70 characters naming who or what would be pictured, using only facts from the article",
 "caption_instagram": "120-180 words. Hook first line, 3 short paragraphs, end with the question, then 'Full story: link in bio.' then 5-8 relevant hashtags incl #TheInnovatorsDen",
 "caption_facebook": "80-130 words, conversational, ends with the question. No hashtags except #TheInnovatorsDen",
 "caption_linkedin": "120-200 words, sharper professional angle for founders/operators, short paragraphs, end with the question, 3 hashtags max"
}
Slide rules (the cover and closing slide are added automatically, so "slides" holds 3 to 8 story slides):
- Use as many slides as the story needs to be complete, up to 8. A simple story may need 3 or 4. A detailed one should use 6 to 8. Never cut the story short to save slides.
- Walk through the story in logical order: what happened, who is involved, the key numbers and details, how it works or why it happened, reactions or context from the article, what happens next or current status. Finish with "Why it matters".
- Every slide is a complete thought. No cliffhangers, no "more on the next slide", no sentence split across slides, no "..." endings.
- Each slide "text" is 60 to 160 characters. Wrap 1-2 key phrases per slide in *asterisks*. Labels are 1-3 words.
- If the article leaves something unresolved (a vote pending, a result unknown), say so plainly on a slide rather than leaving it out.
Hard rules:
- Use ONLY facts in the article. Never invent numbers, quotes, names or outcomes. Credit the source by name ({source}) in every caption.
- Never use em dashes or en dashes anywhere. Use commas, periods or parentheses.
- No partisan political takes. No buzzwords (synergy, leverage, elevate, game-changer, revolutionize).
- "Why it matters" connects the story to underrepresented founders, creators, workers or communities in an honest, non-preachy way.

Category: {topic}
Source: {source}
Headline: {title}
Article:
{body}
"""

def post_anthropic(body, timeout=300):
    """Call the Anthropic API; on failure raise with the API's own error message so the log says exactly what's wrong."""
    import urllib.error
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key: raise RuntimeError("no ANTHROPIC_API_KEY")
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(), headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Anthropic API {e.code}: {e.read().decode()[:800]}")

def validate(c):
    probs = []
    sl = c.get("slides") or []
    sl = [x for x in sl if isinstance(x, dict) and x.get("text")]
    if not 3 <= len(sl) <= MAX_BODY_SLIDES: probs.append(f"slides must have 3 to {MAX_BODY_SLIDES} items, got {len(sl)}")
    long = [i + 1 for i, x in enumerate(sl) if len(x["text"].replace("*", "")) > 170]
    if long: probs.append(f"slides {long} are over 160 characters, tighten them without dropping facts")
    cut = [i + 1 for i, x in enumerate(sl) if x["text"].rstrip().endswith(("...", "…"))]
    if cut: probs.append(f"slides {cut} end with an ellipsis, finish the thought")
    c["slides"] = sl
    return probs

def fit(sl):
    """Last-resort: merge adjacent slides (never drop any) until it fits Instagram's 10-slide limit."""
    sl = list(sl)
    while len(sl) > MAX_BODY_SLIDES:
        i = min(range(len(sl) - 2), key=lambda k: len(sl[k]["text"]) + len(sl[k + 1]["text"]))  # keep "Why it matters" last
        sl[i:i + 2] = [{"label": sl[i]["label"], "text": sl[i]["text"].rstrip() + " " + sl[i + 1]["text"]}]
    return sl

def llm(story):
    c = _llm(story)
    probs = validate(c)
    if probs:
        print("revising copy:", probs)
        c2 = _llm(story, feedback=probs, previous=c)
        c = c2 if len(validate(c2)) < len(probs) else c
    c["slides"] = fit(c["slides"])
    return c

def _llm(story, feedback=None, previous=None):
    msgs = [{"role": "user", "content": PROMPT.replace("{topic}", story["topic"]).replace("{source}", story["sourceName"])
              .replace("{title}", story["title"]).replace("{body}", story["body"])}]
    if feedback:
        msgs += [{"role": "assistant", "content": json.dumps(previous)},
                 {"role": "user", "content": "Fix these problems and return the full corrected JSON only: " + "; ".join(feedback)}]
    res = post_anthropic({"model": MODEL, "max_tokens": 16000, "messages": msgs})
    # Newer models may return thinking blocks first; use only the text blocks.
    text = "".join(b.get("text", "") for b in res["content"] if b.get("type") == "text")
    return json.loads(text[text.find("{"): text.rfind("}") + 1])

def fallback(story):
    """No-AI backup: tells the story in order using the article's own sentences, up to 8 slides."""
    body = re.sub(r"^By [A-Z][\w.'-]+( [A-Z][\w.'-]+){0,3}\s+", "", story["body"])
    sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+(?=[A-Z\"'“])", body) if len(x.strip()) > 30]
    slides, cur = [], ""
    for x in sents:
        if len(x) > 165: return None  # can't show this sentence whole, so this story isn't a fallback candidate
        if cur and len(cur) + 1 + len(x) > 160:
            slides.append(cur); cur = x
        else:
            cur = (cur + " " + x).strip()
        if len(slides) == MAX_BODY_SLIDES: return None  # story too long to show completely without AI
    if cur: slides.append(cur)
    if len(slides) > MAX_BODY_SLIDES or len(slides) < 2: return None
    labels = ["What happened", "The details", "Key facts", "Context", "Go deeper", "Also", "The latest", "What's next"]
    t = story["title"]
    hook = t if len(t) <= 90 else t[:87].rsplit(" ", 1)[0] + "..."
    first = slides[0] if slides else t
    cap = f"{t}\n\n{first}\n\nWhat's your take? Drop it below.\n\nVia {story['sourceName']}."
    return {"kicker": "Den Signal", "hook": hook, "dek": first[:90],
            "slides": [{"label": labels[i], "text": x} for i, x in enumerate(slides)],
            "cta_line": "Stay *in the know*", "question": "What's your take? Drop it below.",
            "caption_instagram": cap + "\nFull story: link in bio.\n\n#TheInnovatorsDen #ForUsByUs",
            "caption_facebook": cap + "\n\n#TheInnovatorsDen", "caption_linkedin": cap + "\n\n#TheInnovatorsDen"}

def scrub(o):
    if isinstance(o, str): return o.replace("—", ", ").replace("–", "-").replace(" ,", ",")
    if isinstance(o, list): return [scrub(x) for x in o]
    if isinstance(o, dict): return {k: scrub(v) for k, v in o.items()}
    return o

def main():
    stories, state = pick()
    story = stories[0]
    try:
        copy, writer = llm(story), "claude"
    except Exception as e:
        print("LLM failed, trying no-AI fallback:", e)
        copy = None
        for cand in stories:  # only post a story the fallback can show in full
            copy = fallback(cand)
            if copy: story, writer = cand, "fallback"; break
        if not copy:
            sys.exit("AI copywriter unavailable and no story short enough to show completely. Skipping this slot.")
    copy = scrub(copy)
    for k in [k for k in copy if k.startswith('caption_')]:
        copy[k] = copy[k].replace('*', '')  # asterisks only mean 'highlight' on slides; social captions show them literally
    post = {**copy, "story_id": story["id"], "topic": story["topic"], "title": story["title"],
            "source_name": story["sourceName"], "source_url": story.get("sourceUrl"), "writer": writer}
    src = f"\n\nSource: {story['sourceName']} {story.get('sourceUrl') or ''}".rstrip()
    post["caption_facebook"] += src
    post["caption_linkedin"] += src
    out = ROOT / "build"; out.mkdir(exist_ok=True)
    (out / "post.json").write_text(json.dumps(post, indent=1))
    (out / "state.next.json").write_text(json.dumps(state))
    print(f"Picked [{story['topic']}] {story['title']} ({writer})")

if __name__ == "__main__":
    main()
