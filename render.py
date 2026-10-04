"""Innovators Den IG-native card renderer (1080x1350, 4:5 portrait).
Usage: python render.py post.json outdir
"""
import json, sys, html, pathlib, base64
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).parent
def b64(p): return "data:image/png;base64," + base64.b64encode((HERE / p).read_bytes()).decode()
BULB, FULL = b64("assets/logo_bulb.png"), b64("assets/logo_full.png")

TOPIC_COLORS = {
    "Innovation": "#FFE600", "Business Growth": "#3DDC97", "Finance": "#3DDC97", "Culture": "#FF4D7E",
    "Art": "#B388FF", "Music": "#FF8A3D", "Sports": "#4DA3FF", "Health": "#5CE1E6", "Dining": "#FFB74D",
    "Travel": "#80DEEA", "Law": "#CFD8DC", "Spotlight": "#FF4D7E", "Astrology": "#B388FF",
}
W, H = 1080, 1350

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600;800;900&family=Anton&display=block');
*{box-sizing:border-box;margin:0;padding:0}
body{width:1080px;height:1350px;background:#000;color:#fff;font-family:Inter,sans-serif;overflow:hidden}
.card{position:relative;width:100%;height:100%;padding:64px 72px 60px;display:flex;flex-direction:column;background:#000;overflow:hidden}
.glow{position:absolute;inset:0;background:radial-gradient(circle at 100% 0%,rgba(255,77,126,.28),transparent 45%),
 radial-gradient(circle at 0% 100%,rgba(255,230,0,.16),transparent 45%)}
.wm{position:absolute;right:-120px;bottom:-60px;width:620px;opacity:.10;transform:rotate(-8deg)}
.top{position:relative;display:flex;justify-content:space-between;align-items:center;z-index:2}
.brand{display:flex;align-items:center;gap:16px}
.brand img{height:96px}
.brand span{font-weight:900;font-size:28px;letter-spacing:.08em;line-height:1.05}
.chip{font-weight:900;font-size:24px;letter-spacing:.12em;text-transform:uppercase;padding:12px 22px;border-radius:999px;color:#000}
.body{position:relative;flex:1;display:flex;flex-direction:column;justify-content:center;z-index:2}
.kicker{display:inline-block;align-self:flex-start;font-weight:900;font-size:30px;letter-spacing:.14em;text-transform:uppercase;
 background:#FF4D7E;color:#000;padding:10px 18px;margin-bottom:34px}
h1{font-family:Anton,Impact,sans-serif;font-weight:400;line-height:1.14;text-transform:uppercase;letter-spacing:.005em}
h1 em{font-style:normal;color:#000;background:#FFE600;padding:6px 12px 2px;line-height:1;display:inline-block;margin:6px 0}
.big{font-family:Anton,sans-serif;font-size:190px;line-height:.8;color:transparent;-webkit-text-stroke:3px #FFE600;margin-bottom:26px}
.label{font-weight:900;font-size:34px;letter-spacing:.12em;text-transform:uppercase;color:#FF4D7E;margin-bottom:26px}
p.txt{font-weight:600;font-size:58px;line-height:1.22;letter-spacing:-.01em}
p.txt strong{color:#FFE600;font-weight:800}
.foot{position:relative;display:flex;justify-content:space-between;align-items:center;z-index:2;font-size:24px;color:#A0A0A0;font-weight:600}
.swipe{font-weight:900;color:#000;background:#FFE600;padding:16px 28px;border-radius:999px;font-size:26px;letter-spacing:.08em}
.dots{display:flex;gap:10px}.dots i{width:14px;height:14px;border-radius:50%;background:#444}.dots i.on{background:#FFE600;width:40px;border-radius:8px}
.cta{align-items:center;text-align:center}
.cta img{width:330px;margin-bottom:40px}
.cta h1{font-size:92px}
.cta p{font-weight:600;font-size:40px;line-height:1.3;color:#E5E5E5;margin-top:44px;max-width:880px}
.acts{display:flex;gap:18px;margin-top:44px}
.acts span{border:3px solid #FFE600;color:#FFE600;font-weight:900;font-size:26px;letter-spacing:.1em;padding:14px 26px;border-radius:999px}
.cta p.q{font-family:Anton,sans-serif;font-size:64px;line-height:1.12;color:#fff;margin-top:40px;text-transform:uppercase;font-weight:400}
.cmt{margin-top:28px;background:#FFE600;color:#000;font-weight:900;font-size:30px;letter-spacing:.1em;padding:16px 30px;border-radius:999px}
.fubu{font-family:Anton;color:#FF4D7E;font-size:40px;letter-spacing:.04em;margin-top:40px}
"""

def esc(s): return html.escape(s, quote=False)
def mark(s, tag):
    out, on = [], False
    for part in esc(s).split("*"):
        out.append(f"<{tag}>{part}</{tag}>" if on else part); on = not on
    return "".join(out)

def page(inner, wm=True):
    w = f"<img class='wm' src='{BULB}'>" if wm else ""
    return f"<html><head><style>{CSS}</style></head><body><div class='card'><div class='glow'></div>{w}{inner}</div></body></html>"

def top(topic):
    c = TOPIC_COLORS.get(topic, "#FFE600")
    return (f"<div class='top'><div class='brand'><img src='{BULB}'><span>THE INNOVATORS<br>DEN</span></div>"
            f"<div class='chip' style='background:{c}'>{esc(topic)}</div></div>")

def dots(i, n): return "<div class='dots'>" + "".join(f"<i class='{'on' if k == i else ''}'></i>" for k in range(1, n + 1)) + "</div>"

def tsize(t):
    L = len(t.replace("*", ""))
    return 62 if L <= 80 else 56 if L <= 110 else 50 if L <= 140 else 45 if L <= 175 else 40

def hsize(t):
    L = len(t.replace("*", ""))
    return 150 if L < 30 else 128 if L < 45 else 108 if L < 65 else 92 if L < 90 else 80

def carousel(post):
    t, src, n = post["topic"], post["source_name"], len(post["slides"]) + 2
    out = [top(t) + f"<div class='body'><div class='kicker'>{esc(post.get('kicker','Signal'))}</div>"
           f"<h1 style='font-size:{hsize(post['hook'])}px'>{mark(post['hook'],'em')}</h1></div>"
           f"<div class='foot'><span>via {esc(src)}</span><span class='swipe'>SWIPE &rarr;</span></div>"]
    for i, s in enumerate(post["slides"], start=2):
        out.append(top(t) + f"<div class='body'><div class='big'>{i-1:02d}</div><div class='label'>{esc(s['label'])}</div>"
                   f"<p class='txt' style='font-size:{tsize(s['text'])}px'>{mark(s['text'],'strong')}</p></div>"
                   f"<div class='foot'><span>via {esc(src)}</span>{dots(i,n)}</div>")
    out.append(f"<div class='body cta'><img src='{FULL}'><h1>{mark(post['cta_line'],'em')}</h1>"
               f"<p class='q'>{esc(post['question'])}</p><div class='cmt'>COMMENT YOUR ANSWER &darr;</div><div class='acts'><span>SEND TO A FRIEND</span><span>FOLLOW</span></div>"
               f"<div class='fubu'>FOR US. BY US.</div></div>"
               f"<div class='foot'><span>Full story: link in bio</span>{dots(n,n)}</div>")
    return out

def single(post):
    return (top(post["topic"]) + f"<div class='body'><div class='kicker'>{esc(post.get('kicker','Signal'))}</div>"
            f"<h1 style='font-size:{hsize(post['hook'])}px'>{mark(post['hook'],'em')}</h1>"
            f"<p style='font-weight:600;font-size:40px;line-height:1.3;color:#D8D8D8;margin-top:44px'>{mark(post['dek'],'strong')}</p></div>"
            f"<div class='foot'><span>via {esc(post['source_name'])}</span><span style='font-family:Anton;color:#FF4D7E;font-size:32px'>FOR US. BY US.</span></div>")


import covers

def render(post, outdir):
    out = pathlib.Path(outdir); out.mkdir(parents=True, exist_ok=True); files = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        def shot(inner, name, wm=True, full=False):
            pg = b.new_page(viewport={"width": W, "height": H})
            pg.set_content(inner if full else page(inner, wm), wait_until="networkidle"); pg.wait_for_timeout(400)
            f = out / name; pg.screenshot(path=str(f)); pg.close(); files.append(str(f))
        slides = carousel(post)
        style = covers.pick_style(post)
        print(f"cover style: {style}")
        for i, s in enumerate(slides, 1):
            if i == 1 and style != "classic":
                shot(covers.COVERS[style](post), "carousel_01.png", full=True); continue
            shot(s, f"carousel_{i:02d}.png", wm=(i != len(post["slides"]) + 2))
        shot(single(post), "single.png")
        b.close()
    return files

if __name__ == "__main__":
    for f in render(json.load(open(sys.argv[1])), sys.argv[2]): print(f)
