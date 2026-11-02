"""Instagram Story frames (1080x1920) for every post: the cover and the Den's-take slide, each framed in the
Den look with a call to action. The Graph API can't add link stickers, so the frames say "link in bio".

A post can bring its own frames: "ig_stories": ["story_01.png", ...] files inside its "prerendered_dir".
Writes outdir/story_01.png, story_02.png next to the carousel slides.
Usage: python stories.py post.json slides_dir
"""
import base64, html, json, pathlib, shutil, sys

HERE = pathlib.Path(__file__).parent
W, H = 1080, 1920

CSS = """@import url('https://fonts.googleapis.com/css2?family=Inter:wght@600;800;900&family=Anton&display=block');
*{box-sizing:border-box;margin:0;padding:0}
body{width:1080px;height:1920px;background:#000;color:#fff;font-family:Inter,sans-serif;overflow:hidden}
.s{position:relative;width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:0 60px 40px}
.glow{position:absolute;inset:0;background:radial-gradient(circle at 100% 0%,rgba(255,77,126,.32),transparent 45%),radial-gradient(circle at 0% 100%,rgba(255,230,0,.2),transparent 45%)}
.tag{position:relative;font-weight:900;font-size:34px;letter-spacing:.16em;text-transform:uppercase;background:#FFE600;color:#000;padding:14px 28px;border-radius:999px;margin-bottom:44px;max-width:900px;text-align:center}
.card{position:relative;width:880px;height:1100px;border-radius:28px;overflow:hidden;box-shadow:0 30px 80px rgba(0,0,0,.6),0 0 0 4px #FFE600}
.card img{width:100%;height:100%;display:block}
.cta{position:relative;margin-top:56px;text-align:center;max-width:940px}
.cta h2{font-family:Anton,sans-serif;font-weight:400;font-size:84px;line-height:1.05;text-transform:uppercase}
.cta h2 em{font-style:normal;color:#000;background:#FFE600;padding:0 14px}
.cta p{font-weight:800;font-size:30px;line-height:1.3;letter-spacing:.06em;text-transform:uppercase;color:#FF4D7E;margin-top:22px}
"""


def esc(s): return html.escape(s or "", quote=False)
def mark(s):
    out, on = [], False
    for part in esc(s).split("*"):
        out.append(f"<em>{part}</em>" if on else part); on = not on
    return "".join(out)
def uri(p): return "data:image/png;base64," + base64.b64encode(pathlib.Path(p).read_bytes()).decode()


def frame(slide, tag, line, sub):
    return (f"<html><head><style>{CSS}</style></head><body><div class='s'><div class='glow'></div>"
            f"<div class='tag'>{esc(tag)}</div><div class='card'><img src='{uri(slide)}'></div>"
            f"<div class='cta'><h2>{mark(line)}</h2><p>{esc(sub)}</p></div></div></body></html>")


def plan(post, slides):
    """Cover + the last story slide (usually The Den's take), with the post's question on frame 2."""
    frames = [(slides[0], "New on the Den", "Full story. *Link in bio.*", "theinnovatorsden.net")]
    if len(slides) >= 3:
        label = ((post.get("slides") or [{}])[-1].get("label") or "The Den's take")
        q = (post.get("question") or "Tell us what you think.").replace("*", "")
        frames.append((slides[-2], label, "Agree? *Tell us on the post.*", q[:90]))
    return frames


def make(post, outdir):
    out = pathlib.Path(outdir)
    for old in out.glob("story_*.png"): old.unlink()
    own = post.get("ig_stories") if post.get("prerendered_dir") else None
    if own:  # hand-made frames shipped with the post
        files = []
        for i, name in enumerate(own, 1):
            src = HERE / post["prerendered_dir"] / name
            if src.exists():
                dst = out / f"story_{i:02d}.png"; shutil.copy(src, dst); files.append(str(dst))
        if files: return files
    slides = sorted(out.glob("carousel_*.png"))
    if not slides: return []
    from playwright.sync_api import sync_playwright
    files = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for i, (sl, tag, line, sub) in enumerate(plan(post, slides), 1):
            pg = b.new_page(viewport={"width": W, "height": H})
            pg.set_content(frame(sl, tag, line, sub), wait_until="networkidle"); pg.wait_for_timeout(400)
            f = out / f"story_{i:02d}.png"; pg.screenshot(path=str(f)); pg.close(); files.append(str(f))
        b.close()
    return files


if __name__ == "__main__":
    for f in make(json.load(open(sys.argv[1])), sys.argv[2]): print(f)
