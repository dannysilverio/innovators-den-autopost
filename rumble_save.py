"""Save a rendered YouTube Short to the media branch as shorts/<run_id>.mp4 so the daily Rumble
browser upload can fetch it from raw.githubusercontent.com.

Rumble has no posting API, so nothing here posts to Rumble. The daily Rumble task reads posted.json,
public/<run_id>/post.json (platform_copy.rumble) and this file.

Usage: python rumble_save.py build/short.mp4 [run_id]   (run_id defaults to $RUN_ID)
Needs GH_TOKEN (contents: write). Skips when the file is missing or already saved.
"""
import base64, json, os, pathlib, sys, urllib.error, urllib.request

REPO = os.environ.get("GITHUB_REPOSITORY") or "dannysilverio/innovators-den-autopost"
BRANCH = "media"


def api(method, path, body=None):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/{path}",
        data=json.dumps(body).encode() if body else None, method=method,
        headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read() or b"{}")


def save(video, run_id):
    p = pathlib.Path(video)
    if not p.exists():
        print(f"rumble_save: no {video}, nothing to save")
        return
    path = f"contents/shorts/{run_id}.mp4"
    try:
        api("GET", f"{path}?ref={BRANCH}")
        print(f"rumble_save: shorts/{run_id}.mp4 already on {BRANCH}")
        return
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    for attempt in (1, 2):
        try:
            api("PUT", path, {"message": f"short {run_id}", "branch": BRANCH,
                              "content": base64.b64encode(p.read_bytes()).decode()})
            print(f"rumble_save: saved shorts/{run_id}.mp4 ({p.stat().st_size // 1024} KB) to {BRANCH}")
            return
        except urllib.error.HTTPError as e:
            print(f"rumble_save: attempt {attempt} failed: {e.code} {e.read()[:200]!r}")


if __name__ == "__main__":
    save(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else os.environ["RUN_ID"])
