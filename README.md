# Terrabloom Smart Finds — Performance-focused Facebook affiliate automation

This workflow creates one English vertical product video per day and publishes it to your connected Facebook Page after you configure the required secrets and add verified products.

## Improvements in this version
- US-evening-oriented publishing schedule: 00:30 UTC (05:30 Pakistan time). This is a starting test window, not a guaranteed best time; adjust using Page Insights.
- English voiceover plus burned-in phrase subtitles.
- Subtle zoom motion, product benefit, brand treatment and clear CTA.
- Daily product rotation from the active catalogue.
- HTTPS validation for product and image links.
- Duplicate protection: successful posts are recorded in `state/published.json`, so rerunning the workflow on the same Pakistan calendar date skips a second post.
- Affiliate disclosure in both video and caption.

## Add products
Edit `products.csv`. Required columns:
- `name`: accurate product name.
- `tracking_url`: your real DCM affiliate tracking link (not a plain shop URL).
- `image_url`: public HTTPS product image URL you have permission to use.
- `benefit`: short, factual benefit; avoid unverified claims.
- `active`: `true` only after all fields are checked.

The seven DCM tracking URLs you supplied are now entered exactly in the catalogue. All seven remain inactive until each row has an exact public HTTPS product image, current listing availability and a verified DCM redirect; no campaign will publish with a missing image or unverified destination.

## Required GitHub secrets
Go to **Settings → Secrets and variables → Actions** and add:
- `FB_PAGE_ID`
- `FB_PAGE_ACCESS_TOKEN` — a valid Page token with the required video-publishing permission.
- `FACEBOOK_GRAPH_VERSION` — a currently supported version enabled for your Meta app.

Never commit tokens to files or send them in chat. The workflow uses GitHub's built-in token to save successful post IDs to the repository.

## Enable and test
1. Add verified product rows and set only approved rows to active=true.
2. Add the three Facebook secrets.
3. Ensure GitHub Actions is enabled.
4. Run **Actions → Daily Terrabloom Affiliate Video → Run workflow** once.
5. Check the Page post on mobile and desktop: video, subtitles, caption, affiliate disclosure and tracking URL.
6. Compare 7-day results in Meta Business Suite: reach, 3-second views, average watch time, link clicks and purchases/conversions if your affiliate dashboard reports them.

## Performance rules
- Start with one post per day and compare the US-evening slot against other slots using at least 7 days of results.
- Keep products active only when the link works and product claims/images are accurate.
- Prioritize click-through rate and confirmed affiliate conversions over raw views.
- Pause products that receive impressions but no meaningful clicks after a fair test; rotate in better-converting products.
- Do not assume US reach or sales are guaranteed. Audience delivery depends on content quality, engagement, Page history and platform distribution.

## Limits
This is an automated product-card video (designed poster + subtle zoom + voiceover + subtitles), not cinematic generative text-to-video and not Muse AI. It does not yet fetch Meta Insights or DCM conversion data automatically. Pinterest is not integrated into this GitHub workflow, and Metricool scheduling requires a separately connected publishing integration. Seven Pinterest copy and 2:3 creative briefs are saved in `pinterest-campaign-drafts.md`. Use Meta Business Suite and your DCM dashboard for performance data until those integrations are configured.
