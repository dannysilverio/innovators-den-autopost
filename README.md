# Innovators Den Autopost

Posts one branded carousel every **Mon / Wed / Fri at 11:00 AM ET** to Instagram, the Facebook Page and the LinkedIn company page. No approval step.

## How it works
1. **cron-job.org** calls the GitHub Actions workflow at 11:00 ET (same trigger setup as formerlyknownwrites).
2. `guard.py` checks whether a post already went out today and skips the run if so. The GitHub backup schedule at about 11:30 relies on this so it never double-posts.
3. `pick.py` pulls approved stories from Innovators Den News (`/api/articles?status=approved`). It rotates through the categories (Innovation comes up 4x per cycle) and skips categories with no fresh story (96h window). It filters out sales/deals, reviews, violence and partisan politics, and never repeats a story.
4. **Complete stories only.** A story is eligible only if the full article text is available (at least 1,200 characters). When the Den feed carries only a teaser, the full article is pulled from the publisher's page. Claude (Anthropic API) then tells the whole story in order: cover + 3 to 8 story slides + closing slide, up to Instagram's 10-slide limit. Every slide is a complete thought, with no cliffhangers or "..." endings. If a draft breaks the rules, it is sent back for one revision. If it still runs long, adjacent slides are merged, and nothing is ever dropped. Separate captions are written for IG, FB and LinkedIn: facts only, no em dashes, source credited.
   - If the AI copywriter is unavailable, the no-AI backup posts only a story short enough to show in full. If none qualifies, the slot is skipped rather than posting half a story.
5. `render.py` renders 1080x1350 slides in the Den brand (lightbulb-brain logo, black / #FFE600 / #FF4D7E).
6. Slides are committed to `public/<run>/` so Instagram and Facebook can fetch them. The repo must be **public**.
7. `publish.py` posts to each platform independently. A LinkedIn failure never blocks Instagram.
8. Results are logged to `posted.json`. The category rotation is saved in `state.json`.

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

Optional **Variables**: `PLATFORMS` (e.g. `instagram,facebook` until LinkedIn is approved), `ANTHROPIC_MODEL`, `IG_GRAPH_HOST` (`graph.facebook.com` if using a Facebook-login token instead of Instagram-login).

### 3. cron-job.org
- URL: `https://api.github.com/repos/dannysilverio/innovators-den-autopost/actions/workflows/post.yml/dispatches`
- Method: POST. Body: `{"ref":"main"}`
- Headers: `Authorization: Bearer <fine-grained PAT with Actions: read/write on this repo>`, `Accept: application/vnd.github+json`
- Schedule: Mon, Wed, Fri at 11:00, timezone America/New_York.

### 4. First test
Actions → *Innovators Den autopost* → Run workflow → `dry_run = 1`. Check the slides in `public/`, then run once with `dry_run = 0`.

## Token upkeep
- Instagram and Facebook long-lived user tokens expire after about 60 days. Page tokens made from a long-lived user token don't expire.
- LinkedIn access tokens last 60 days. Refresh them before then.
- If a platform fails, `posted.json` shows the exact error.
