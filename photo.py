"""Find a free-to-use photo of the story's main subject on Wikimedia Commons.

Only Commons images (imagerepository == "shared") with a Creative Commons or public-domain
license are used, and the credit line is returned so it can be printed on the slide.
Wikipedia's own "fair use" images (logos, album covers, posters) are skipped on purpose.
"""
import json, re, time, html, pathlib, urllib.request, urllib.parse

UA = "InnovatorsDenBot/1.0 (https://github.com/dannysilverio/innovators-den-autopost)"
API = "https://en.wikipedia.org/w/api.php"
OK_LICENSE = re.compile(r"^(CC0|CC BY|CC-BY|Public domain|PD)", re.I)


def _get(params, tries=3):
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read())
        except Exception:
            time.sleep(2 + 3 * i)
    return {}


def _lead_image(subject):
    """Lead image file name of the Wikipedia article that best matches `subject`."""
    d = _get({"action": "query", "titles": subject, "redirects": 1, "prop": "pageimages", "piprop": "name"})
    for p in d.get("query", {}).get("pages", {}).values():
        if p.get("pageimage"):
            return p["pageimage"]
    d = _get({"action": "query", "generator": "search", "gsrsearch": subject, "gsrlimit": 1,
              "prop": "pageimages", "piprop": "name"})
    for p in d.get("query", {}).get("pages", {}).values():
        if p.get("pageimage"):
            return p["pageimage"]
    return None


def _clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def find_photo(subjects, dest):
    """Try each subject in order; download the first properly licensed photo to `dest`.
    Returns {"path", "credit", "subject"} or None."""
    for subject in [s for s in subjects or [] if s][:3]:
        name = _lead_image(subject)
        if not name or name.lower().endswith((".svg", ".gif")):
            continue
        d = _get({"action": "query", "titles": "File:" + name, "prop": "imageinfo",
                  "iiprop": "extmetadata|url", "iiurlwidth": 1200,
                  "iiextmetadatafilter": "Artist|LicenseShortName"})
        page = next(iter(d.get("query", {}).get("pages", {}).values()), {})
        if page.get("imagerepository") != "shared":  # local enwiki file = usually non-free fair use
            continue
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        lic = _clean(meta.get("LicenseShortName", {}).get("value"))
        if not OK_LICENSE.match(lic):
            continue
        artist = _clean(meta.get("Artist", {}).get("value"))[:60] or "Unknown"
        url = info.get("thumburl") or info.get("url")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                pathlib.Path(dest).write_bytes(r.read())
        except Exception:
            continue
        credit = f"Photo: {artist} / {lic} via Wikimedia Commons"
        return {"path": str(dest), "credit": credit, "subject": subject}
    return None


if __name__ == "__main__":
    import sys
    print(find_photo(sys.argv[1:], "photo_test.jpg"))
