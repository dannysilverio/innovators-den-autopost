"""Render a 1000x1500 Pinterest pin for a Den story.

Usage: python pin.py <story_url> <out.jpg> [--title "Pin headline"] [--label "NYC FOOD AND DRINK"]

Pulls the story's square photo (/api/assets/crops/<slug>-1x1.jpg, falling back to -og.jpg)
and headline from theinnovatorsden.net, then renders: photo on top, Den bulb logo, a pink
desk label, the headline in Anton with a neon yellow bar, and a "read the full story" footer.
Brand colors only: black, neon yellow #FFE600, hot pink #FF4D7E.
"""
import argparse, base64, html, json, pathlib, re, sys, urllib.request

HERE = pathlib.Path(__file__).parent
SITE = "https://theinnovatorsden.net"
UA = {"User-Agent": "Mozilla/5.0 (den-pin)"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read()


def story(url):
    page = get(url).decode("utf-8", "replace")
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    m = re.search(r'"headline":"((?:[^"\\]|\\.)*)"', page)
    title = json.loads('"' + m.group(1) + '"') if m else slug.replace("-", " ").title()
    t = re.search(r'"topic":"((?:[^"\\]|\\.)*)"', page)
    topic = json.loads('"' + t.group(1) + '"') if t else ""
    photo = None
    for crop in ("1x1", "og"):
        try:
            photo = get(f"{SITE}/api/assets/crops/{slug}-{crop}.jpg")
            if photo[:2] == b"\xff\xd8":
                break
            photo = None
        except Exception:
            photo = None
    if not photo:
        og = re.search(r'og:image" content="([^"]+)"', page)
        if og:
            photo = get(og.group(1))
    if not photo:
        sys.exit(f"no photo found for {url}")
    return {"slug": slug, "title": title, "topic": topic, "photo": photo}


def hsize(t):
    n = len(t)
    return 96 if n <= 34 else 84 if n <= 48 else 72 if n <= 64 else 62 if n <= 82 else 54


def build_html(title, label, photo):
    bulb = base64.b64encode((HERE / "assets/logo_bulb.png").read_bytes()).decode()
    img = base64.b64encode(photo).decode()
    return f"""<!doctype html><html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@600;800;900&family=Anton&display=block');
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:1000px;height:1500px;background:#000;color:#fff;font-family:Inter,sans-serif;overflow:hidden;position:relative}}
.ph{{position:absolute;top:0;left:0;width:1000px;height:960px;background:url(data:image/jpeg;base64,{img}) center/cover}}
.fade{{position:absolute;top:640px;left:0;width:1000px;height:330px;background:linear-gradient(to bottom,rgba(0,0,0,0),#000)}}
.logo{{position:absolute;top:40px;left:40px;width:96px;height:96px;border-radius:50%;background:#000 url(data:image/png;base64,{bulb}) center/70% no-repeat}}
.txt{{position:absolute;left:60px;right:60px;top:880px;bottom:150px;display:flex;flex-direction:column;justify-content:center}}
.label{{align-self:flex-start;background:#FF4D7E;color:#000;font-weight:900;font-size:26px;letter-spacing:.12em;text-transform:uppercase;padding:12px 22px;border-radius:999px;margin-bottom:30px}}
h1{{font-family:Anton,Impact,sans-serif;font-weight:400;text-transform:uppercase;line-height:1.28;color:#000}}
h1 span{{background:#FFE600;padding:2px 14px 0;-webkit-box-decoration-break:clone;box-decoration-break:clone}}
.foot{{position:absolute;left:60px;right:60px;bottom:56px;display:flex;justify-content:space-between;align-items:center}}
.foot b{{font-weight:900;font-size:28px;letter-spacing:.06em;color:#FFE600}}
.foot i{{font-style:normal;font-family:Anton;font-size:30px;color:#FF4D7E;letter-spacing:.04em}}
</style></head><body>
<div class="ph"></div><div class="fade"></div><div class="logo"></div>
<div class="txt"><div class="label">{html.escape(label)}</div>
<h1 style="font-size:{hsize(title)}px"><span>{html.escape(title)}</span></h1></div>
<div class="foot"><b>READ IT AT THEINNOVATORSDEN.NET</b><i>THE INNOVATORS DEN</i></div>
</body></html>"""


def render(url, out, title=None, label=None, photo_url=None):
    s = story(url)
    if photo_url:  # a Den-owned image when the story has no crop (e.g. its own YouTube thumbnail)
        s["photo"] = get(photo_url)
    title = title or s["title"]
    label = label or s["topic"] or "The Innovators Den"
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1000, "height": 1500})
        pg.set_content(build_html(title, label, s["photo"]), wait_until="networkidle")
        pg.wait_for_timeout(600)
        pg.screenshot(path=str(out), type="jpeg", quality=90, full_page=False)
        b.close()
    return {"slug": s["slug"], "title": title, "topic": s["topic"], "out": str(out)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("url"); ap.add_argument("out")
    ap.add_argument("--title"); ap.add_argument("--label"); ap.add_argument("--photo")
    a = ap.parse_args()
    print(json.dumps(render(a.url, a.out, a.title, a.label, a.photo)))
