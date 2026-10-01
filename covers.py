"""Cover (slide 1) designs. A different look each day of the week so the feed never feels repetitive.

Each function takes the post dict and returns a full HTML page (1080x1350).
Styles that need a photo fall back to "classic" when no licensed photo was found.
"""
import base64, html, pathlib, datetime as dt
from zoneinfo import ZoneInfo

HERE = pathlib.Path(__file__).parent
BULB = "data:image/png;base64," + base64.b64encode((HERE / "assets/logo_bulb.png").read_bytes()).decode()
ET = ZoneInfo("America/New_York")

# Monday=0 ... Sunday=6
STYLE_BY_DAY = {0: "breaking", 1: "newspaper", 2: "classic", 3: "tabloid", 4: "magazine", 5: "duotone", 6: "broadcast"}
NEEDS_PHOTO = {"breaking", "tabloid", "magazine", "duotone", "broadcast"}

TOPIC_COLORS = {
    "Innovation": "#FFE600", "Business Growth": "#3DDC97", "Finance": "#3DDC97", "Culture": "#FF4D7E",
    "Art": "#B388FF", "Music": "#FF8A3D", "Sports": "#4DA3FF", "Health": "#5CE1E6", "Dining": "#FFB74D",
    "Travel": "#80DEEA", "Law": "#CFD8DC", "Spotlight": "#FF4D7E", "Astrology": "#B388FF",
}

FONTS = ("@import url('https://fonts.googleapis.com/css2?family=Anton&family=Inter:wght@500;600;700;800;900"
         "&family=UnifrakturMaguntia&family=Playfair+Display:ital,wght@0,700;0,900;1,500"
         "&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&display=block');"
         "*{box-sizing:border-box;margin:0;padding:0}body{width:1080px;height:1350px;overflow:hidden}")


def esc(s): return html.escape(s or "", quote=False)
def plain(s): return esc((s or "").replace("*", ""))
def mark(s, tag="em"):
    out, on = [], False
    for part in esc(s or "").split("*"):
        out.append(f"<{tag}>{part}</{tag}>" if on else part); on = not on
    return "".join(out)
def fit(text, sizes):
    """sizes: list of (max_len, px). Returns the px for this headline length."""
    L = len((text or "").replace("*", ""))
    for mx, px in sizes:
        if L <= mx: return px
    return sizes[-1][1]
def doc(css, body): return f"<html><head><style>{FONTS}{css}</style></head><body>{body}</body></html>"


def pick_style(post, now=None):
    now = now or dt.datetime.now(ET)
    style = post.get("cover_style") or STYLE_BY_DAY[now.weekday()]
    if style in NEEDS_PHOTO and not photo_uri(post):
        style = "classic"
    return style


def photo_uri(post):
    ph = post.get("photo") or {}
    p = pathlib.Path(ph.get("path") or "")
    if ph.get("path") and p.exists():
        mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()
    return None


def ctx(post):
    now = dt.datetime.now(ET)
    ph = post.get("photo") or {}
    return dict(topic=post.get("topic", ""), color=TOPIC_COLORS.get(post.get("topic"), "#FFE600"),
                kicker=post.get("kicker", ""), hook=post.get("hook", ""), dek=post.get("dek", ""),
                src=post.get("source_name", ""), img=photo_uri(post), credit=ph.get("credit", ""),
                caption=ph.get("caption") or ph.get("subject", ""), focus=ph.get("focus", "50% 22%"),
                day=now.strftime("%a").upper(), date=f"{now.strftime('%A, %B')} {now.day}, {now.year}",
                short=f"{now.strftime('%b').upper()} {now.day}", yday=now.timetuple().tm_yday,
                lede=plain(post["slides"][0]["text"]) if post.get("slides") else "")


# ---------------------------------------------------------------- 1. BREAKING (Mon)
def breaking(post):
    c = ctx(post)
    css = """
.t{position:relative;width:1080px;height:1350px;background:#000;overflow:hidden}
.ph{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.shade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.55) 0%,rgba(0,0,0,0) 22%,rgba(0,0,0,0) 38%,rgba(0,0,0,.93) 72%),radial-gradient(circle at 100% 100%,rgba(255,77,126,.35),transparent 50%)}
.top{position:absolute;top:44px;left:56px;right:56px;display:flex;justify-content:space-between;align-items:center}
.brand{display:flex;align-items:center;gap:14px;color:#fff;font-family:Inter;font-weight:900;font-size:26px;letter-spacing:.08em;line-height:1.05}.brand img{height:86px}
.chip{font-family:Inter;font-weight:900;font-size:22px;letter-spacing:.14em;padding:10px 20px;border-radius:999px;text-transform:uppercase}
.box{position:absolute;left:56px;right:56px;bottom:136px}
.live{display:inline-flex;align-items:center;gap:10px;background:#FF4D7E;font-family:Inter;font-weight:900;font-size:26px;letter-spacing:.14em;padding:10px 18px;margin-bottom:22px;text-transform:uppercase}
.live:before{content:'';width:14px;height:14px;border-radius:50%;background:#000}
h1{font-family:Anton;font-weight:400;color:#fff;line-height:1.14;text-transform:uppercase}
h1 em{font-style:normal;color:#000;background:#FFE600;padding:0 12px;-webkit-box-decoration-break:clone;box-decoration-break:clone}
.dek{font-family:Inter;font-weight:600;color:#e5e5e5;font-size:34px;margin-top:22px;line-height:1.3}
.foot{position:absolute;left:56px;right:56px;bottom:44px;display:flex;justify-content:space-between;align-items:center;font-family:Inter;font-weight:600;color:#aaa;font-size:18px}
.sw{background:#FFE600;color:#000;padding:14px 26px;border-radius:999px;font-weight:900;font-size:22px;letter-spacing:.08em}"""
    fs = fit(c["hook"], [(28, 140), (42, 120), (56, 104), (99, 90)])
    return doc(css, f"""<div class='t'><img class='ph' src='{c['img']}' style='object-position:{c['focus']}'><div class='shade'></div>
<div class='top'><div class='brand'><img src='{BULB}'><span>THE INNOVATORS<br>DEN</span></div><div class='chip' style='background:{c['color']}'>{esc(c['topic'])}</div></div>
<div class='box'><div class='live'>{esc(c['kicker'])}</div><h1 style='font-size:{fs}px'>{mark(c['hook'])}</h1><div class='dek'>{plain(c['dek'])}</div></div>
<div class='foot'><span>{esc(c['credit'])} &middot; via {esc(c['src'])}</span><span class='sw'>SWIPE &rarr;</span></div></div>""")


# ---------------------------------------------------------------- 2. NEWSPAPER (Tue)
def newspaper(post):
    c = ctx(post)
    css = """
.np{position:relative;width:100%;height:100%;padding:44px 56px 40px;color:#141414;display:flex;flex-direction:column;
 background:#F3EDE0;background-image:radial-gradient(rgba(0,0,0,.035) 1px,transparent 1.2px),radial-gradient(circle at 20% 10%,rgba(160,120,60,.10),transparent 55%),radial-gradient(circle at 90% 95%,rgba(120,90,40,.12),transparent 50%);background-size:5px 5px,100% 100%,100% 100%}
.meta{display:flex;justify-content:space-between;align-items:center;font-family:Inter;font-weight:800;font-size:17px;letter-spacing:.14em;text-transform:uppercase;border-top:3px solid #141414;border-bottom:1px solid #141414;padding:9px 2px}
.mast{display:flex;align-items:center;justify-content:center;gap:20px;padding:14px 0 8px}.mast img{height:80px}
.mast h2{font-family:'UnifrakturMaguntia',serif;font-weight:400;font-size:98px;line-height:1;white-space:nowrap}
.rule{border-top:3px solid #141414;border-bottom:1px solid #141414;height:7px;margin-bottom:14px}
.sec{display:flex;align-items:center;gap:14px;margin-bottom:12px}
.chip{font-family:Inter;font-weight:900;font-size:21px;letter-spacing:.16em;text-transform:uppercase;padding:7px 16px;background:#141414;color:#F3EDE0}
.kick{font-family:Inter;font-weight:900;font-size:21px;letter-spacing:.16em;text-transform:uppercase;padding:7px 4px}
.via{margin-left:auto;font-family:'Playfair Display';font-style:italic;font-size:24px}
h1{font-family:'Playfair Display',serif;font-weight:900;line-height:1.02;letter-spacing:-.01em;margin-bottom:14px}
.photo{position:relative;flex:1;min-height:0;overflow:hidden;border:2px solid #141414}
.photo img{width:100%;height:100%;object-fit:cover;filter:grayscale(1) contrast(1.18) sepia(.18)}
.photo:after{content:'';position:absolute;inset:0;background-image:radial-gradient(rgba(0,0,0,.22) .9px,transparent 1.3px);background-size:4px 4px;mix-blend-mode:multiply}
.cap{display:flex;justify-content:space-between;gap:20px;font-family:'Libre Baskerville';font-style:italic;font-size:17px;padding:8px 2px 12px;border-bottom:1px solid #141414}
.cr{font-style:normal;font-family:Inter;font-weight:700;font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:#555;white-space:nowrap;align-self:center}
.cols{display:grid;grid-template-columns:1.2fr 1fr;gap:26px;padding-top:14px;font-family:'Libre Baskerville';font-size:21px;line-height:1.45}
.dek{font-family:'Playfair Display';font-style:italic;font-weight:500;font-size:27px;line-height:1.25;border-right:1px solid #141414;padding-right:24px}
.cols p:first-letter{font-family:'Playfair Display';font-weight:900;float:left;font-size:66px;line-height:.9;padding:4px 8px 0 0}
.foot{display:flex;justify-content:space-between;align-items:center;margin-top:16px;font-family:Inter;font-weight:800;font-size:17px;letter-spacing:.1em;text-transform:uppercase}
.sw{background:#FFE600;color:#141414;padding:12px 22px;border:2px solid #141414;font-weight:900;font-size:19px}
.nophoto h1{margin:40px 0 30px}.nophoto .cols{flex:1;font-size:26px}.nophoto .dek{font-size:36px}"""
    has = bool(c["img"])
    fs = fit(c["hook"], [(30, 104), (42, 92), (56, 80), (99, 70)]) if has else fit(c["hook"], [(30, 140), (56, 118), (99, 100)])
    photo = (f"<div class='photo'><img src='{c['img']}' style='object-position:{c['focus']}'></div>"
             f"<div class='cap'><span>{esc(c['caption'])}</span><span class='cr'>{esc(c['credit'])}</span></div>") if has else ""
    return doc(css, f"""<div class='np{'' if has else ' nophoto'}'>
<div class='meta'><span>Vol. I &middot; No. {c['yday']}</span><span>{c['date']}</span><span>For Us. By Us.</span></div>
<div class='mast'><img src='{BULB}'><h2>The Innovators Den</h2></div><div class='rule'></div>
<div class='sec'><span class='chip'>{esc(c['topic'])}</span><span class='kick'>{esc(c['kicker'])}</span><span class='via'>via {esc(c['src'])}</span></div>
<h1 style='font-size:{fs}px'>{plain(c['hook'])}</h1>{photo}
<div class='cols'><div class='dek'>{plain(c['dek'])}</div><p>{c['lede']}</p></div>
<div class='foot'><span>Continued inside</span><span class='sw'>Swipe for the full story &rarr;</span></div></div>""")


# ---------------------------------------------------------------- 3. TABLOID (Thu)
def tabloid(post):
    c = ctx(post)
    css = """
.t{position:relative;width:1080px;height:1350px;background:#000;overflow:hidden}
.ph{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.mast{position:absolute;top:0;left:0;right:0;background:#E3001B;display:flex;align-items:center;gap:18px;padding:18px 40px;z-index:2}
.mast img{height:70px}.mast b{font-family:Anton;font-weight:400;font-size:80px;color:#fff;line-height:1}
.mast i{margin-left:auto;font-family:Inter;font-style:normal;font-weight:900;color:#FFE600;font-size:20px;letter-spacing:.14em;text-align:right;line-height:1.3}
.shade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,0) 42%,rgba(0,0,0,.88) 80%)}
.box{position:absolute;left:40px;right:40px;bottom:112px}
.tag{display:inline-block;background:#FFE600;font-family:Inter;font-weight:900;font-size:26px;letter-spacing:.14em;padding:8px 16px;margin-bottom:16px;text-transform:uppercase}
h1{font-family:Anton;color:#fff;line-height:.94;text-transform:uppercase;-webkit-text-stroke:3px #000;text-shadow:6px 6px 0 #000}
h1 em{font-style:normal;color:#FFE600}
.foot{position:absolute;left:40px;right:40px;bottom:36px;display:flex;justify-content:space-between;align-items:center;font-family:Inter;font-weight:700;color:#ddd;font-size:18px}
.sw{background:#fff;color:#000;padding:12px 22px;font-weight:900;font-size:20px}"""
    fs = fit(c["hook"], [(24, 160), (36, 138), (50, 118), (99, 100)])
    return doc(css, f"""<div class='t'><img class='ph' src='{c['img']}' style='object-position:{c['focus']}'><div class='shade'></div>
<div class='mast'><img src='{BULB}'><b>THE INNOVATORS DEN</b><i>{c['day']} {c['short']}<br>FOR US. BY US.</i></div>
<div class='box'><div class='tag'>{esc(c['topic'])} &middot; {esc(c['kicker'])}</div><h1 style='font-size:{fs}px'>{mark(c['hook'])}</h1></div>
<div class='foot'><span>{esc(c['credit'])} &middot; via {esc(c['src'])}</span><span class='sw'>SWIPE &rarr;</span></div></div>""")


# ---------------------------------------------------------------- 4. MAGAZINE (Fri)
def magazine(post):
    c = ctx(post)
    css = """
.t{position:relative;width:1080px;height:1350px;background:#0d0d0d;overflow:hidden}
.ph{position:absolute;left:0;right:0;top:250px;bottom:0;width:100%;height:1100px;object-fit:cover}
.shade{position:absolute;left:0;right:0;top:250px;bottom:0;background:linear-gradient(180deg,rgba(13,13,13,1) 0%,rgba(13,13,13,0) 14%,rgba(0,0,0,0) 45%,rgba(0,0,0,.92) 88%)}
.mast{position:absolute;top:22px;left:0;right:0;text-align:center;font-family:Anton;color:#fff;font-size:200px;line-height:1;letter-spacing:.04em}
.sub{position:absolute;top:218px;left:0;right:0;display:flex;justify-content:center;gap:26px;font-family:Inter;font-weight:900;color:#fff;font-size:20px;letter-spacing:.3em;z-index:2}
.sub b{color:#FFE600}
.box{position:absolute;left:52px;right:52px;bottom:118px}
.box .k{display:inline-block;font-family:Inter;font-weight:900;font-size:20px;letter-spacing:.16em;padding:6px 12px;color:#000;text-transform:uppercase;margin-bottom:16px}
.box p{font-family:Inter;font-weight:600;color:#e8e8e8;font-size:30px;line-height:1.3;margin-top:18px}
h1{font-family:'Playfair Display';font-weight:900;color:#fff;line-height:1.02;text-shadow:0 4px 24px rgba(0,0,0,.5)}
h1 em{font-style:italic;color:#FFE600}
.foot{position:absolute;left:52px;right:52px;bottom:40px;display:flex;justify-content:space-between;align-items:center;font-family:Inter;font-weight:700;color:#ccc;font-size:17px}
.bar{display:flex;gap:18px;align-items:center}.bar img{height:54px}
.sw{border:3px solid #FFE600;color:#FFE600;padding:10px 22px;border-radius:999px;font-weight:900;font-size:20px;letter-spacing:.1em}"""
    fs = fit(c["hook"], [(28, 104), (42, 90), (56, 80), (99, 70)])
    return doc(css, f"""<div class='t'><img class='ph' src='{c['img']}' style='object-position:{c['focus']}'><div class='shade'></div>
<div class='mast'>THE DEN</div><div class='sub'><span>THE INNOVATORS DEN</span><b>&bull;</b><span>{c['short']} ISSUE</span></div>
<div class='box'><span class='k' style='background:{c['color']}'>{esc(c['topic'])}</span><h1 style='font-size:{fs}px'>{mark(c['hook'])}</h1><p>{plain(c['dek'])}</p></div>
<div class='foot'><div class='bar'><img src='{BULB}'><span>{esc(c['credit'])}<br>via {esc(c['src'])}</span></div><span class='sw'>SWIPE &rarr;</span></div></div>""")


# ---------------------------------------------------------------- 5. DUOTONE SPLIT (Sat)
def duotone(post):
    c = ctx(post)
    css = """
.t{position:relative;width:1080px;height:1350px;background:#FFE600;overflow:hidden;display:flex;flex-direction:column}
.pic{position:relative;height:720px;overflow:hidden;background:#FF4D7E}
.pic img{width:100%;height:100%;object-fit:cover;filter:grayscale(1) contrast(1.25) brightness(1.05);mix-blend-mode:multiply}
.pic:after{content:'';position:absolute;inset:0;background:linear-gradient(180deg,rgba(20,0,40,.25),rgba(20,0,40,0) 30%)}
.top{position:absolute;top:36px;left:48px;right:48px;display:flex;justify-content:space-between;align-items:center;z-index:2}
.brand{display:flex;align-items:center;gap:12px;color:#fff;font-family:Inter;font-weight:900;font-size:24px;letter-spacing:.08em;line-height:1.05}.brand img{height:78px}
.date{font-family:Inter;font-weight:900;color:#fff;font-size:20px;letter-spacing:.18em}
.num{position:absolute;right:40px;bottom:-60px;font-family:Anton;font-size:300px;color:#FFE600;line-height:1;z-index:2;-webkit-text-stroke:4px #000}
.low{flex:1;padding:44px 48px 40px;display:flex;flex-direction:column;color:#000}
.k{font-family:Inter;font-weight:900;font-size:24px;letter-spacing:.18em;text-transform:uppercase;border-bottom:4px solid #000;padding-bottom:10px;margin-bottom:22px;display:flex;justify-content:space-between}
h1{font-family:Anton;font-weight:400;line-height:1.16;text-transform:uppercase}
h1 em{font-style:normal;background:#000;color:#FFE600;padding:0 12px;-webkit-box-decoration-break:clone;box-decoration-break:clone}
.foot{margin-top:auto;display:flex;justify-content:space-between;align-items:center;font-family:Inter;font-weight:700;font-size:17px;color:#333}
.sw{background:#000;color:#FFE600;padding:14px 24px;font-weight:900;font-size:20px;letter-spacing:.1em}"""
    fs = fit(c["hook"], [(28, 150), (42, 128), (56, 110), (99, 92)])
    return doc(css, f"""<div class='t'><div class='pic'><img src='{c['img']}' style='object-position:{c['focus']}'>
<div class='top'><div class='brand'><img src='{BULB}'><span>THE INNOVATORS<br>DEN</span></div><span class='date'>{c['day']} &middot; {c['short']}</span></div></div>
<div class='low'><div class='k'><span>{esc(c['topic'])} / {esc(c['kicker'])}</span><span>via {esc(c['src'])}</span></div>
<h1 style='font-size:{fs}px'>{mark(c['hook'])}</h1>
<div class='foot'><span>{esc(c['credit'])}</span><span class='sw'>SWIPE &rarr;</span></div></div></div>""")


# ---------------------------------------------------------------- 6. BROADCAST / TV lower-third (Sun)
def broadcast(post):
    c = ctx(post)
    css = """
.t{position:relative;width:1080px;height:1350px;background:#000;overflow:hidden}
.ph{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.shade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.2),rgba(0,0,0,0) 30%,rgba(0,0,0,0) 50%,rgba(0,0,0,.75) 100%)}
.bug{position:absolute;top:40px;right:44px;display:flex;align-items:center;gap:10px;background:rgba(0,0,0,.55);padding:10px 16px;border-radius:10px;color:#fff;font-family:Inter;font-weight:900;font-size:20px;letter-spacing:.08em}
.bug img{height:48px}
.livebox{position:absolute;top:44px;left:44px;display:flex;gap:0;font-family:Inter;font-weight:900;font-size:22px;letter-spacing:.14em}
.livebox span{padding:10px 16px}.livebox .l{background:#E3001B;color:#fff}.livebox .d{background:#fff;color:#000}
.lt{position:absolute;left:0;right:0;bottom:170px}
.lt .tab{display:inline-block;margin-left:44px;padding:10px 20px;font-family:Inter;font-weight:900;font-size:24px;letter-spacing:.14em;color:#000;text-transform:uppercase}
.lt .main{background:#fff;padding:22px 44px;border-left:18px solid #FF4D7E}
.lt h1{font-family:Anton;font-weight:400;color:#000;line-height:1.05;text-transform:uppercase}
.lt h1 em{font-style:normal;color:#FF4D7E}
.lt .sub{background:#111;color:#fff;font-family:Inter;font-weight:700;font-size:28px;padding:14px 44px}
.ticker{position:absolute;left:0;right:0;bottom:96px;background:#FFE600;display:flex;align-items:center;font-family:Inter;font-weight:900;font-size:22px;white-space:nowrap;overflow:hidden}
.ticker b{background:#000;color:#FFE600;padding:14px 18px;letter-spacing:.12em}.ticker span{padding:0 20px}
.foot{position:absolute;left:44px;right:44px;bottom:30px;display:flex;justify-content:space-between;align-items:center;font-family:Inter;font-weight:700;color:#ccc;font-size:17px}
.sw{background:#fff;color:#000;padding:12px 22px;font-weight:900;font-size:20px;letter-spacing:.08em}"""
    fs = fit(c["hook"], [(28, 96), (42, 82), (56, 70), (99, 60)])
    return doc(css, f"""<div class='t'><img class='ph' src='{c['img']}' style='object-position:{c['focus']}'><div class='shade'></div>
<div class='livebox'><span class='l'>DEN NEWS</span><span class='d'>{c['day']} {c['short']}</span></div>
<div class='bug'><img src='{BULB}'><span>TID</span></div>
<div class='lt'><div class='tab' style='background:{c['color']}'>{esc(c['topic'])}</div>
<div class='main'><h1 style='font-size:{fs}px'>{mark(c['hook'])}</h1></div><div class='sub'>{plain(c['dek'])}</div></div>
<div class='ticker'><b>THE INNOVATORS DEN</b><span>{esc(c['kicker'])} &bull; via {esc(c['src'])} &bull; For Us. By Us.</span></div>
<div class='foot'><span>{esc(c['credit'])}</span><span class='sw'>SWIPE &rarr;</span></div></div>""")


COVERS = {"breaking": breaking, "newspaper": newspaper, "tabloid": tabloid,
          "magazine": magazine, "duotone": duotone, "broadcast": broadcast}
