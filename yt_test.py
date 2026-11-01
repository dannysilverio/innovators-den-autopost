"""One-off YouTube Shorts test: render the newest Den carousel as a Short and upload it. Touches no other platform.

Picks the newest run in public/ (or RUN_ID if set), builds build/short.mp4 with reel.py, uploads via publish.youtube.
New API projects upload as private until Google's audit approves them, so this never goes public by surprise.
"""
import json, os, pathlib, shutil, subprocess, sys

import publish as P

ROOT = pathlib.Path(__file__).parent
runs = sorted(p for p in (ROOT / "public").iterdir() if p.is_dir() and (p / "post.json").exists())
run = ROOT / "public" / os.environ["RUN_ID"] if os.environ.get("RUN_ID") else runs[-1]
build = ROOT / "build"
shutil.rmtree(build, ignore_errors=True)
(build / "slides").mkdir(parents=True)
for f in sorted(run.glob("carousel_*.png")):
    shutil.copy(f, build / "slides" / f.name)
shutil.copy(run / "post.json", build / "post.json")
subprocess.run([sys.executable, "reel.py", "build/slides", "build/short.mp4"], check=True, cwd=ROOT,
               env={**os.environ, "FORCE_REEL": "1"})
post = json.loads((build / "post.json").read_text())
print(f"youtube test: {post['title'][:80]} ({run.name})")
print(json.dumps(P.youtube(post, str(build / "short.mp4"))))
