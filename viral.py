"""Per-platform discovery rules: one place that turns a Den post into the copy each platform ranks best.

Every platform indexes and distributes differently, so the same caption everywhere wastes reach.
enrich(post) fills post["platform_copy"] with ready-to-post copy for YouTube, Threads, TikTok, Rumble,
Instagram and LinkedIn. publish.py reads it, and the TikTok (Metricool) and Rumble (browser) uploads
use it too, since post.json is committed next to the slides in public/<run_id>/.

Research behind the rules (Nov 2026):
- YouTube: title read left to right, keyword in the first words; first lines of the description weigh most;
  first 3 hashtags show above the title, Shorts lean on hashtags; tags matter little except for
  misspellings/variants; more than 60 hashtags and YouTube ignores all of them.
- Instagram: caption keywords (first line) drive search; hard cap of 5 hashtags per post (Dec 2025);
  alt text is read for search and Google indexing; collaborators (max 3, public accounts) put the post
  on their profile and feed too.
- Threads: 500 characters, one topic tag per post (topic_tag, 1-50 chars, no "." or "&").
- LinkedIn: external links in the post body cut reach (and link-in-comment is now penalised too);
  dwell time, comments and saves are rewarded.
- TikTok: keyword in the first ~80 characters of the caption, 100-150 characters, 3-5 specific hashtags.
- Rumble: literal, searchable titles; rewrite metadata instead of copying YouTube's unchanged.
"""
import os, re

SITE = "https://theinnovatorsden.net"

# Instagram accounts invited as collaborators on every carousel and Reel (max 3 per post, public accounts only).
# Danny's personal page by default. IG_COLLABORATORS overrides it ("none" turns it off);
# a post's own "ig_collaborators" list (e.g. the brand or venue we covered) is added first.
# Every Den post invites the team as collaborators: Danny, Orlando (mr_a_plus) and Wally (W Studios).
# The API allows 3, so featured partners (a venue, a chef) get tagged on the first slide instead (see partners()).
DEFAULT_COLLABORATORS = ["formerlyknownashashtag", "mr_a_plus", "wstudiosnj"]

SUB_BRAND = {"Innovation": "Brain Trust", "Art": "Frame Room", "Culture": "The Stoop", "Music": "Tarima",
             "Business Growth": "The Margin", "Business": "The Margin", "Sports": "Walk-Off",
             "Food & Wine": "Brindis", "Food": "Brindis", "Dining": "Brindis", "Health": "Second Wind",
             "Travel": "Carry-On Culture", "Astrology": "Rising Sign", "Law": "Counsel Hour",
             "Finance": "Capital Cipher", "Spotlight": "The Debut"}

# Broad Threads communities per Den category (used when the copywriter did not pick one)
THREADS_TOPIC = {"Innovation": "Tech", "Art": "Art", "Culture": "Culture", "Music": "Music",
                 "Business Growth": "Entrepreneurship", "Business": "Entrepreneurship", "Sports": "Sports",
                 "Food & Wine": "Food", "Food": "Food", "Dining": "Food", "Health": "Health",
                 "Travel": "Travel", "Astrology": "Astrology", "Law": "Law", "Finance": "Personal Finance",
                 "Spotlight": "Creators"}

# YouTube category IDs (standard list): 10 Music, 17 Sports, 19 Travel & Events, 22 People & Blogs,
# 24 Entertainment, 26 Howto & Style, 27 Education, 28 Science & Technology
YT_CATEGORY = {"Innovation": "28", "Music": "10", "Sports": "17", "Food & Wine": "19", "Food": "19",
               "Dining": "19", "Travel": "19", "Health": "26", "Art": "24", "Culture": "24",
               "Spotlight": "24", "Astrology": "24", "Finance": "27", "Law": "27"}

TOPIC_TAGS = {"Innovation": ["#Tech", "#Innovation"], "Art": ["#Art", "#Artist"], "Culture": ["#Culture"],
              "Music": ["#Music", "#NewMusic"], "Business Growth": ["#Entrepreneur", "#SmallBusiness"],
              "Sports": ["#Sports"], "Food & Wine": ["#NYCFood", "#Foodie"], "Dining": ["#NYCFood", "#Foodie"],
              "Health": ["#Health", "#Wellness"], "Travel": ["#Travel"], "Astrology": ["#Astrology"],
              "Law": ["#Law"], "Finance": ["#Finance", "#MoneyTips"], "Spotlight": ["#Creators"]}

# Text the copywriter fills in for every post (appended to the JSON schema in pick.py and originals.py)
SCHEMA = """ "seo_keyword": "the 2-5 word phrase a real person would type into YouTube, TikTok or Instagram search to find this exact story (a name, brand, place or the striking thing itself, e.g. 'risotto martini', 'Jay-Z top 21 rappers'). Plain words, no hashtag",
 "search_terms": ["5 to 8 short search phrases people use for this story: full names, brands, the place, the topic, plus any common misspelling of a name in it"],
 "hashtags": ["3 or 4 specific hashtags for this story WITHOUT #TheInnovatorsDen: one broad (e.g. #NYCFood) and the rest niche to the story (e.g. #RisottoMartini). No generic tags like #Viral or #FYP"],
 "yt_title": "YouTube Shorts title, max 60 characters. The seo_keyword (or its key words) in the first 3 words, then the hook. Literal enough to match a search, curious enough to tap. No hashtags, nothing the slides do not pay off",
 "caption_threads": "max 380 characters. Sounds like a person talking, not a press release: the hook, the one fact that makes it surprising, then the question. No hashtags, no links, no 'link in bio'",
 "threads_topic": "one Threads topic for the community most likely to care, 1-40 characters, letters, numbers and spaces only (e.g. 'Brooklyn Food', 'Black Founders', 'NBA', 'Hip Hop')",
 "caption_tiktok": "TikTok photo-post caption, 100 to 150 characters before hashtags: the seo_keyword inside the first 80 characters, one line of payoff, the question, then the same 3-4 hashtags plus #TheInnovatorsDen","""

RULES = """Discovery rules (every platform ranks on search words now, so write for search AND for the scroll):
- The seo_keyword must appear naturally in the first sentence of caption_instagram, caption_reel, caption_facebook, caption_tiktok and in yt_title. Instagram only shows the first ~125 characters before "more", so the keyword and the hook live there.
- Instagram allows 5 hashtags at most. caption_instagram and caption_reel end with the hashtags list plus #TheInnovatorsDen (and the sub-brand tag if asked), 5 total maximum.
- caption_linkedin must contain NO URLs (LinkedIn cuts reach on posts with links). Say "Full story on theinnovatorsden.net" only if a URL was asked for, written without https.
- Every caption ends with a question people can answer in a few words, because comments and replies are what every algorithm tests first."""


def _clean(s):
    return re.sub(r"\s+", " ", (s or "").replace("*", "")).strip()


ABBR = r"(?<!\bJan)(?<!\bFeb)(?<!\bMar)(?<!\bApr)(?<!\bAug)(?<!\bSep)(?<!\bSept)(?<!\bOct)(?<!\bNov)(?<!\bDec)" \
       r"(?<!\bNo)(?<!\bSt)(?<!\bMr)(?<!\bMs)(?<!\bDr)(?<!\bvs)(?<!\bInc)(?<!\bJr)(?<!\bU\.S)"


def _first_sentence(s):
    s = _clean(re.sub(r"#\w+", "", s or ""))
    m = re.match(r"(.+?" + ABBR + r"[.!?])(\s+(?=[A-Z\"'0-9])|$)", s)
    return (m.group(1) if m else s)[:220]


def _strip_tags(s):
    return re.sub(r"[ \t]*#\w+", "", s or "").strip()


def hashtags(post):
    """Story-specific hashtags (never #TheInnovatorsDen), from the copywriter or the Instagram caption."""
    tags = post.get("hashtags") or re.findall(r"#\w+", post.get("caption_instagram") or "")
    out = []
    for t in tags:
        t = "#" + re.sub(r"[^\w]", "", str(t).lstrip("#"))
        if len(t) > 2 and t.lower() not in ("#theinnovatorsden", "#shorts") and t.lower() not in [x.lower() for x in out]:
            out.append(t)
    brand = "#" + re.sub(r"[^A-Za-z]", "", SUB_BRAND.get(post.get("topic"), "")).lower()
    out.sort(key=lambda t: t.lower() == brand)
    if len(out) < 2:
        out += [t for t in TOPIC_TAGS.get(post.get("topic"), []) if t.lower() not in [x.lower() for x in out]]
    return out[:4]


def cap_hashtags(text, limit=5):
    """Instagram rejects or ignores more than 5 hashtags: keep the first `limit`, always keeping #TheInnovatorsDen."""
    if not text:
        return text
    found = re.findall(r"#\w+", text)
    if len(found) <= limit:
        return text
    keep = [t for t in found if t.lower() == "#theinnovatorsden"][:1]
    for t in found:
        if len(keep) >= limit: break
        if t not in keep: keep.append(t)
    drop = set(found) - set(keep)
    for t in drop:
        text = re.sub(rf"[ \t]*{re.escape(t)}\b", "", text)
    return re.sub(r"[ \t]+\n", "\n", text).rstrip()


def keyword(post):
    k = _clean(post.get("seo_keyword"))
    if k:
        return k
    t = re.sub(r"[:|].*$", "", _clean(post.get("title") or post.get("hook") or ""))
    return " ".join(t.split()[:6])


def _yt_title(post):
    t = _clean(post.get("yt_title"))
    if not t:  # older posts: the story title carries the names people search; the hook is the fallback
        title, hook = _clean(post.get("title")), _clean(post.get("hook"))
        t = title if title and len(title) <= 70 else (hook or title)
    t = re.sub(r"[<>#]", "", t).strip()
    return t if len(t) <= 70 else t[:70].rsplit(" ", 1)[0].rstrip(",:;")


def _yt_tags(post):
    seen, out, size = set(), [], 0
    brand = SUB_BRAND.get(post.get("topic"), "")
    from_tags = [re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", h.lstrip("#")) for h in hashtags(post)]
    for t in [_clean(post.get("seo_keyword")), *(post.get("search_terms") or []), _clean(post.get("title"))[:60], *from_tags,
              "The Innovators Den", brand, post.get("topic") or ""]:
        t = re.sub(r"[<>,#\"]", "", _clean(t))
        if not t or t.lower() in seen: continue
        cost = len(t) + (2 if " " in t else 0) + 1
        if size + cost > 450: break
        seen.add(t.lower()); out.append(t); size += cost
    return out[:15]


def _yt_description(post, tags):
    body = _strip_tags(post.get("caption_facebook") or post.get("caption_instagram"))
    body = body.replace("link in bio", "link below").replace("Full story: link below.", "").strip()
    lead = _first_sentence(post.get("caption_reel") or post.get("caption_instagram") or body)
    if lead and body.startswith(lead[:40]):
        lead = ""
    url = post.get("story_url") or (post.get("source_url") if post.get("mode") == "original" else None) or SITE
    brand = SUB_BRAND.get(post.get("topic"))
    parts = [lead, body]
    if url not in body:
        parts.append(f"Full story: {url}")
    parts.append("The Innovators Den covers culture, food, music, business and the people building what's next. "
                 + (f"{brand} is our {post.get('topic')} series. " if brand else "") + "Subscribe for more.")
    parts.append(" ".join([*tags[:3], "#Shorts", "#TheInnovatorsDen"]))
    return re.sub(r"[<>]", "", "\n\n".join(p for p in parts if p))[:4900]


def _threads(post):
    s = _clean(post.get("caption_threads")) if post.get("caption_threads") else _strip_tags(
        post.get("caption_facebook") or post.get("caption_instagram"))
    s = s.replace("link in bio", "link in profile").strip()
    if len(s) > 480:
        cut = s[:480]
        for sep in ("\n\n", ". ", "? ", "! "):
            i = cut.rfind(sep)
            if i > 240:
                cut = cut[: i + (1 if sep != "\n\n" else 0)]; break
        s = cut.rstrip()
    topic = re.sub(r"[^A-Za-z0-9 ]", "", post.get("threads_topic") or THREADS_TOPIC.get(post.get("topic"), "")).strip()[:50]
    return {"text": s, "topic": topic or "The Innovators Den"}


def _tiktok(post, tags):
    if post.get("caption_tiktok"):
        c = post["caption_tiktok"]
        if "#theinnovatorsden" not in c.lower(): c += " #TheInnovatorsDen"
        return cap_hashtags(c, 5)
    lead = _first_sentence(post.get("caption_reel") or post.get("caption_instagram") or post.get("title"))
    q = _clean(post.get("question"))
    return " ".join(x for x in [lead, q] if x) + "\n\n" + " ".join([*tags[:4], "#TheInnovatorsDen"])


def linkedin_text(post):
    s = post.get("caption_linkedin") or ""
    if os.environ.get("LI_LINKS") == "1":
        return s
    s = re.sub(r"(Full story|Read the full story|Read more)\s*:\s*https?://\S+", r"\1 on theinnovatorsden.net", s)
    s = re.sub(r"\s*https?://\S+", "", s)
    return re.sub(r"[ \t]+\n", "\n", s).strip()


def collaborators(post):
    # A post can name its exact 3 collaborators (e.g. the venue plus two of the team) instead of the default team.
    exact = [str(u).lstrip("@").strip() for u in (post.get("ig_collaborators_exact") or []) if str(u).strip()]
    if exact:
        return exact[:3]
    env = os.environ.get("IG_COLLABORATORS")
    base = [] if (env or "").strip().lower() == "none" else (
        [x for x in re.split(r"[,\s]+", env) if x] if env else DEFAULT_COLLABORATORS)
    out = []
    for u in [*base, *(post.get("ig_collaborators") or [])]:  # the team first, always
        u = str(u).lstrip("@").strip()
        if u and len(u) <= 30 and u.lower() not in [x.lower() for x in out]:
            out.append(u)
    return out[:3]


def partners(post):
    """Featured accounts (post ig_collaborators) that don't fit in the 3 collaborator slots: tag them instead."""
    taken = [x.lower() for x in collaborators(post)]
    out = []
    for u in post.get("ig_collaborators") or []:
        u = str(u).lstrip("@").strip()
        if u and u.lower() not in taken and u.lower() not in [x.lower() for x in out]:
            out.append(u)
    return out[:20]


def alt_texts(post, n):
    """Alt text per carousel image (Instagram reads it for search and Google indexing; max 1,000 chars)."""
    slides = [s for s in (post.get("slides") or []) if isinstance(s, dict) and s.get("text")]
    head = _clean(post.get('hook') or post.get('title')).rstrip(".!? ")
    cover = _clean(f"The Innovators Den: {head}. {post.get('dek') or ''}")
    out = []
    for i in range(n):
        if i == 0:
            out.append(cover)
        elif 1 <= i <= len(slides) and i < n - 1:
            s = slides[i - 1]
            out.append(_clean(f"{s.get('label', '')}: {s['text']}"))
        else:
            out.append(_clean(f"{post.get('title')}. {post.get('question') or ''}"))
    return [a[:1000] for a in out]


def enrich(post):
    """Adds post['platform_copy'] and enforces hard platform limits. Safe to call more than once."""
    tags = hashtags(post)
    for k in ("caption_instagram", "caption_reel"):
        if post.get(k):
            post[k] = cap_hashtags(post[k], 5)
    post["platform_copy"] = {
        "seo_keyword": keyword(post),
        "youtube": {"title": _yt_title(post), "description": _yt_description(post, tags), "tags": _yt_tags(post),
                    "category_id": YT_CATEGORY.get(post.get("topic"), "22")},
        "threads": _threads(post),
        "tiktok": {"caption": _tiktok(post, tags)},
        "rumble": {"title": _yt_title(post), "description": _yt_description(post, tags).replace(" #Shorts", ""),
                   "tags": ", ".join(_yt_tags(post)), "category_hint": post.get("topic") or ""},
        "linkedin": {"text": linkedin_text(post)},
        "instagram": {"collaborators": collaborators(post)},
    }
    return post


def copy_for(post, platform):
    return (post.get("platform_copy") or enrich(dict(post))["platform_copy"])[platform]
