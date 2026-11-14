# Terrabloom Smart Finds — Daily Facebook Affiliate Video

This starter workflow builds one English product-promo video per day from your product catalogue, generates an English voiceover, and publishes it to your Facebook Page.

## What it does
1. Selects one active product from `products.csv` (daily rotation).
2. Downloads its product image.
3. Creates a vertical 1080×1920 promotional video with on-screen text.
4. Generates English voiceover using Edge TTS.
5. Publishes the MP4 and affiliate disclosure/caption to your Facebook Page.
6. Runs daily through GitHub Actions (default: 09:00 UTC / 2:00 PM Pakistan time).

**Important:** This first free starter uses automated product-card video (product image + motion/video encoding + voiceover), not cinematic AI text-to-video. It does not use Muse AI.

## 1. Add your products
Edit `products.csv`. Each product must have:
- `name`
- `tracking_url` — your actual DCM affiliate tracking link (do not put a normal product URL here unless it is your approved tracking URL)
- `image_url` — a publicly accessible image URL you are allowed to use
- `benefit` — one short, accurate benefit
- `active` — `true` or `false`

Only products with a real tracking URL and image URL are eligible. The starter catalogue contains the compost product URL as a placeholder; replace it with your DCM tracking link before enabling publishing.

## 2. Add GitHub Actions secrets
In GitHub: **Settings → Secrets and variables → Actions → New repository secret**.

Required secrets:
- `FB_PAGE_ID` — your Facebook Page ID
- `FB_PAGE_ACCESS_TOKEN` — a valid Page access token with permission to publish Page videos
- `FACEBOOK_GRAPH_VERSION` — supported Graph API version, e.g. the version enabled for your Meta app

Never paste access tokens into source files or commit them to this repository.

## 3. Enable the workflow
Go to **Actions** and enable GitHub Actions for this repository. The workflow runs daily at 09:00 UTC (14:00 Pakistan time). You can also run it manually with **Run workflow**.

## 4. Test safely first
Before relying on daily publishing:
- Add at least one verified DCM tracking link and image.
- Add the three GitHub secrets.
- Run the workflow manually.
- Confirm the video, caption, affiliate disclosure, and link on your Facebook Page.

The workflow will fail rather than publish if required secrets or valid product fields are missing.

## Notes
- Facebook/Meta may require app review, Page permissions, and a valid token. Tokens expire or can be revoked; renew them when publishing fails.
- Affiliate disclosure is included in every caption: **#Ad #Affiliate**.
- Verify product claims, image rights, tracking links, and Meta's current policies before enabling unattended publishing.
- This repository does not yet connect to Metricool. Metricool can remain your monitoring/analytics dashboard.
