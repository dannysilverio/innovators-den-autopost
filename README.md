# Innovators Den Autopost

Posts one branded carousel every **Mon / Wed / Fri at 11:00 AM ET** to Instagram, the Facebook Page and the LinkedIn company page. No approval step.

## How it works
Every 2 hours (9am to 9pm ET), cron-job.org wakes the GitHub workflow and Claude runs the trend desk:

1. **Should we post?** (`scout.py`)
   - **Mon/Wed/Fri:** one post is guaranteed from 11am on.
   - **Any day:** an extra post goes out when a story is trending hard. Max 2 posts on Mon/Wed/Fri and 1 on other days, at least 3 hours apart, only between 8am and 9pm ET.
2. **What's trending?** Claude gets the Den feed's fresh stories (last 36h, all 13 topics) and uses **live web search** (trending searches plus what major outlets are covering at once) to score how hard each is trending, from 1 to 10.
   - Only stories inside the Den's topics count. Politics, crime, deaths, gossip and product sales are excluded.
   - An extra post needs a score of **8+** (set the `TREND_MIN_SCORE` variable to change it).
   - On a baseline slot, the top trending story is used if it scores 5+. Otherwise the category rotation picks one.
   - If a bigger in-topic story is missing from the Den feed, Claude can pull it straight from a major outlet.
3. **Complete stories only.** The full article text is required. Claude tells the whole story, in order, on up to 10 slides (cover, 3 to 8 story slides, closing). Every slide is a complete thought. Separate captions go to IG, FB and LinkedIn: facts only, no em dashes, source credited. If the writer fails, nothing posts.
4. `render.py` builds the 1080x1350 slides in the Den brand. The cover changes by day: Mon breaking, Tue newspaper, Wed classic, Thu tabloid, Fri magazine, Sat duotone, Sun broadcast (`covers.py`). `photo.py` finds a free-licensed Wikimedia Commons photo of the story's subject and prints the credit on the cover; with no usable photo, the classic or text newspaper cover is used. They're committed to `public/<run>/` (the repo must be **public** so Instagram and Facebook can load them).
5. `publish.py` posts to each platform independently and logs everything to `posted.json` (time, mode `trending`/`baseline`, and results or errors).

## One-time setup

### 1. GitHub
- Create a **public** repo `innovators-den-autopost` under `dannysilverio` and upload these files.
- Settings → Actions → General → Workflow permissions → **Read and write**.

### 2. Secrets (Settings → Secrets and variables → Actions → Secrets)
| Secret | Where it comes from |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |
| `IG_USER_ID` | Den Instagram professional account ID |
| `IG_ACCESS_TOKEN` | Long-lived IG token with `instagram_business_content_publish` (same Meta app flow as formerlyknownwrites) |
| `FB_PAGE_ID` | Den Facebook Page ID |
| `FB_PAGE_TOKEN` | Long-lived **Page** access token with `pages_manage_posts`, `pages_read_engagement` |
| `LI_ORG_ID` | Numeric ID in the company page admin URL (linkedin.com/company/**12345678**/admin) |
| `LI_ACCESS_TOKEN` | LinkedIn app token with `w_organization_social` (needs Community Management API approval) |

Optional **Variables**: `TREND_MIN_SCORE` (default 8), `PLATFORMS` (e.g. `instagram,facebook` until LinkedIn is approved), `ANTHROPIC_MODEL`, `IG_GRAPH_HOST` (`graph.facebook.com` if using a Facebook-login token instead of Instagram-login).

### 3. cron-job.org
- URL: `https://api.github.com/repos/dannysilverio/innovators-den-autopost/actions/workflows/post.yml/dispatches`
- Method: POST. Body: `{"ref":"main"}`
- Headers: `Authorization: Bearer <fine-grained PAT with Actions: read/write on this repo>`, `Accept: application/vnd.github+json`
- Schedule: **every day, every 2 hours from 9:00 to 21:00** (9am, 11am, 1pm, 3pm, 5pm, 7pm, 9pm), timezone America/New_York.

### 4. First test
Actions → *Innovators Den autopost* → Run workflow → `dry_run = 1`, `force = 1`. Check the slides in `public/`, then run once with `dry_run = 0`.

## Token upkeep
- Instagram and Facebook long-lived user tokens expire after about 60 days. Page tokens made from a long-lived user token don't expire.
- LinkedIn access tokens last 60 days. Refresh them before then.
- If a platform fails, `posted.json` shows the exact error.
