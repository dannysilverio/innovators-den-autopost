"""Turn the rendered carousel slides into a 9:16 Reel (1080x1920 MP4).

Each slide sits centered over a blurred, zoomed copy of itself. Timing follows reading speed
(cover is short so the hook lands inside the first 2 seconds), with quick crossfades between slides.
Usage: python reel.py build/slides build/reel.mp4
"""
import glob, json, pathlib, subprocess, sys, tempfile
from PIL import Image, ImageFilter, ImageEnhance

FPS, FADE = 30, 0.35


def durations(slides_dir, n):
    """Seconds per slide: cover 2.2s, story slides by text length, closing 3s."""
    post = {}
    p = pathlib.Path(slides_dir).parent / "post.json"
    if p.exists():
        post = json.loads(p.read_text())
    body = [len(s.get("text", "").replace("*", "")) for s in post.get("slides", [])]
    out = []
    for i in range(n):
        if i == 0:
            out.append(2.2)
        elif i == n - 1:
            out.append(3.0)
        else:
            L = body[i - 1] if i - 1 < len(body) else 120
            out.append(max(3.0, min(5.5, L / 30)))  # ~30 characters per second of screen time
    return out


def build(slides_dir, out):
    import os
    post_file = pathlib.Path(slides_dir).parent / "post.json"
    score = (json.loads(post_file.read_text()).get("trend") or {}).get("score", 0) if post_file.exists() else 0
    need = int(os.environ.get("REEL_MIN_SCORE") or 10)
    if (score or 0) < need and os.environ.get("FORCE_REEL") != "1":
        print(f"reel: skipped (trend score {score} is below {need}; Reels are reserved for the most viral stories)")
        return
    files = sorted(glob.glob(f"{slides_dir}/carousel_*.png"))
    if not files:
        sys.exit("no slides to turn into a reel")
    durs = durations(slides_dir, len(files))
    tmp = pathlib.Path(tempfile.mkdtemp())
    frames = []
    for i, f in enumerate(files):  # compose each 9:16 frame once (blurred backdrop + slide) instead of per video frame
        fg = Image.open(f).convert("RGB").resize((1080, 1350))
        bg = fg.resize((1536, 1920)).crop((228, 0, 1308, 1920)).filter(ImageFilter.GaussianBlur(40))
        bg = ImageEnhance.Brightness(bg).enhance(0.75)
        bg.paste(fg, (0, (1920 - 1350) // 2 - 40))
        p = tmp / f"frame_{i:02d}.png"; bg.save(p); frames.append(str(p))
    files = frames
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for f, d in zip(files, durs):
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{d + FADE:.2f}", "-i", f]
    parts = []
    for i, d in enumerate(durs):
        parts.append(f"[{i}:v]fps={FPS},format=yuv420p,setsar=1[v{i}]")
    chain, last, t = [], "v0", 0.0
    for i in range(1, len(durs)):
        t += durs[i - 1]
        chain.append(f"[{last}][v{i}]xfade=transition=fade:duration={FADE}:offset={t:.2f}[x{i}]")
        last = f"x{i}"
    graph = ";".join(parts + chain)
    total = sum(durs) + FADE
    cmd += ["-f", "lavfi", "-t", f"{total:.2f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-filter_complex", graph, "-map", f"[{last}]", "-map", f"{len(files)}:a",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", "-r", str(FPS), out]
    subprocess.run(cmd, check=True)
    print(f"reel: {out} ({total:.1f}s, {len(files)} slides)")


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
