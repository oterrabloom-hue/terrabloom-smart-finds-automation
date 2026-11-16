import asyncio
import base64
import csv
import json
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import edge_tts
import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)
WIDTH, HEIGHT = 1080, 1920
PK_TZ = ZoneInfo("Asia/Karachi")
API = "https://api.github.com"


def today_pk():
    return datetime.now(PK_TZ).date()


def load_products():
    with (ROOT / "products.csv").open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    eligible = []
    for p in rows:
        if p.get("active", "").strip().lower() != "true":
            continue
        required = ["name", "tracking_url", "image_url", "benefit"]
        if any(not p.get(k, "").strip() for k in required):
            continue
        if not p["tracking_url"].startswith("https://") or not p["image_url"].startswith("https://"):
            continue
        eligible.append(p)
    if not eligible:
        raise RuntimeError("No active products with HTTPS DCM tracking_url, public image_url and accurate benefit. Update products.csv first.")
    day = today_pk()
    return eligible[day.toordinal() % len(eligible)]


def github_request(method, url, token, **kwargs):
    response = requests.request(
        method, url, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }, timeout=30, **kwargs
    )
    if response.status_code not in (200, 201, 204):
        raise RuntimeError(f"GitHub state operation failed ({response.status_code}): {response.text[:500]}")
    return response


def get_state(repo, token):
    url = f"{API}/repos/{repo}/contents/state/published.json"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}, params={"ref": "main"}, timeout=30)
    if r.status_code == 404:
        return {"posts": {}}, None
    if not r.ok:
        raise RuntimeError(f"Cannot read publish history ({r.status_code}): {r.text[:500]}")
    item = r.json()
    content = base64.b64decode(item["content"]).decode("utf-8")
    return json.loads(content), item["sha"]


def save_state(repo, token, state, sha):
    url = f"{API}/repos/{repo}/contents/state/published.json"
    encoded = base64.b64encode((json.dumps(state, indent=2, ensure_ascii=False) + "\n").encode()).decode()
    body = {"message": "Record successful Facebook publication", "content": encoded, "branch": "main"}
    if sha:
        body["sha"] = sha
    github_request("PUT", url, token, json=body)


def load_font(size, bold=False):
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(path, size) if Path(path).exists() else ImageFont.load_default()


def wrap_text(draw, text, font, max_width):
    lines, current = [], ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if draw.textbbox((0, 0), trial, font=font)[2] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def make_poster(product, image_path, poster_path):
    canvas = Image.new("RGB", (WIDTH, HEIGHT), "#f4f1e8")
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((55, 55, 1025, 230), radius=42, fill="#174c35")
    draw.text((95, 95), "TERRABLOOM", font=load_font(62, True), fill="white")
    draw.text((100, 170), "SMART FINDS", font=load_font(32, True), fill="#d8edc8")
    with Image.open(image_path).convert("RGB") as source:
        fitted = ImageOps.contain(source, (900, 900))
        panel = Image.new("RGB", (930, 930), "white")
        panel.paste(fitted, ((930 - fitted.width) // 2, (930 - fitted.height) // 2))
        canvas.paste(panel, (75, 275))
    y = 1245
    title_font = load_font(54, True)
    for line in wrap_text(draw, product["name"], title_font, 940)[:2]:
        draw.text((75, y), line, font=title_font, fill="#173d2c")
        y += 68
    y += 15
    for line in wrap_text(draw, product["benefit"], load_font(35), 920)[:3]:
        draw.text((80, y), line, font=load_font(35), fill="#34443a")
        y += 50
    draw.rounded_rectangle((75, 1645, 1005, 1775), radius=35, fill="#e2a83b")
    cta, font = "CHECK PRODUCT DETAILS", load_font(42, True)
    bbox = draw.textbbox((0, 0), cta, font=font)
    draw.text(((WIDTH - bbox[2] + bbox[0]) / 2, 1688), cta, font=font, fill="#1e2d21")
    draw.text((80, 1830), "Affiliate recommendation • #Ad", font=load_font(27), fill="#45554a")
    canvas.save(poster_path, quality=94)


def make_script(product):
    return (
        f"Need a smarter find? Take a look at {product['name']}. "
        f"{product['benefit']}. Check the product details through the link in this post. "
        "This is an affiliate recommendation from Terrabloom Smart Finds."
    )


async def create_voiceover(script, audio_path):
    await edge_tts.Communicate(script, voice="en-US-AriaNeural", rate="+2%").save(str(audio_path))


def probe_duration(audio):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(audio)],
        check=True, capture_output=True, text=True
    )
    return max(float(result.stdout.strip()), 1.0)


def timestamp(seconds):
    ms = int(seconds * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def make_subtitles(script, duration, path):
    phrases = [p.strip() for p in script.replace("? ", "?|").replace(". ", ".|").split("|") if p.strip()]
    segment = duration / max(len(phrases), 1)
    entries = []
    for i, phrase in enumerate(phrases):
        start, end = i * segment, min((i + 1) * segment, duration)
        entries.append(f"{i+1}\n{timestamp(start)} --> {timestamp(end)}\n{phrase}\n")
    path.write_text("\n".join(entries), encoding="utf-8")


def render_video(poster, audio, subtitles, video):
    sub_path = str(subtitles.resolve()).replace("\\", "\\\\").replace(":", "\\:")
    vf = f"scale=1200:2134,zoompan=z='min(zoom+0.00035,1.08)':d=1:s=1080x1920:fps=25,subtitles='{sub_path}':force_style='FontName=DejaVu Sans,FontSize=18,Outline=2,Shadow=1,Alignment=2,MarginV=180'"
    command = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(poster), "-i", str(audio),
        "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "128k", "-pix_fmt", "yuv420p", "-shortest",
        "-r", "25", "-movflags", "+faststart", str(video)
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)


def publish_to_facebook(video, product):
    page_id = os.environ.get("FB_PAGE_ID", "").strip()
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "").strip()
    version = os.environ.get("FACEBOOK_GRAPH_VERSION", "").strip()
    if not all([page_id, token, version]):
        raise RuntimeError("Missing FB_PAGE_ID, FB_PAGE_ACCESS_TOKEN or FACEBOOK_GRAPH_VERSION GitHub secret.")
    # Validate token type and target Page before uploading a large video.
    identity = requests.get(
        f"https://graph.facebook.com/{version}/me",
        params={"fields": "id,name", "access_token": token},
        timeout=30,
    )
    if not identity.ok:
        try:
            error = identity.json().get("error", {})
            detail = f"Meta token check failed ({identity.status_code}, code {error.get('code', 'unknown')}): {error.get('message', 'Unknown Meta API error')}"
        except ValueError:
            detail = f"Meta token check failed ({identity.status_code}); response was not valid JSON."
        raise RuntimeError(detail)
    identity_data = identity.json()
    if str(identity_data.get("id", "")) != page_id:
        raise RuntimeError(
            "FB_PAGE_ACCESS_TOKEN is not a Page Access Token for the configured FB_PAGE_ID. "
            "No video was uploaded. The token identity did not match the selected Page."
        )
    print(f"Meta Page token preflight passed for configured Page ID {page_id}.")
    caption = (
        f"{product['name']}\n\n{product['benefit']}\n\n"
        f"See product details: {product['tracking_url']}\n\n"
        "Affiliate disclosure: I may earn a commission if you purchase through this link. "
        "#Ad #Affiliate #TerrabloomSmartFinds"
    )
    endpoint = f"https://graph.facebook.com/{version}/{page_id}/videos"
    with video.open("rb") as media:
        response = requests.post(
            endpoint,
            data={"access_token": token, "description": caption, "title": product["name"]},
            files={"source": (video.name, media, "video/mp4")},
            timeout=600,
        )
    if not response.ok:
        raise RuntimeError(f"Facebook publishing failed ({response.status_code}): {response.text[:1000]}")
    try:
        result = response.json()
    except ValueError:
        raise RuntimeError(
            f"Facebook returned HTTP {response.status_code} but the response was not valid JSON. "
            f"Response: {response.text[:1000]}"
        )
    video_id = result.get("id") or result.get("video_id")
    if not video_id:
        # Do not mark a post as published unless Facebook returns a verifiable video ID.
        safe_result = {k: v for k, v in result.items() if k not in ("access_token", "token")}
        raise RuntimeError(
            "Facebook returned HTTP success but no video ID; publication is unverified. "
            f"Response: {json.dumps(safe_result, ensure_ascii=False)[:1000]}"
        )
    return str(video_id)


def main():
    product = load_products()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    gh_token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not repo or not gh_token:
        raise RuntimeError("GITHUB_REPOSITORY and GITHUB_TOKEN are required for duplicate-post protection.")
    day_key = today_pk().isoformat()
    state, state_sha = get_state(repo, gh_token)
    if day_key in state.get("posts", {}):
        print(f"A post is already recorded for Pakistan date {day_key}; skipping to prevent duplicate publishing.")
        return

    slug = "".join(c.lower() if c.isalnum() else "-" for c in product["name"]).strip("-")
    poster, audio = OUTPUT / f"{slug}.jpg", OUTPUT / f"{slug}.mp3"
    subtitles, video = OUTPUT / f"{slug}.srt", OUTPUT / f"{day_key}-{slug}.mp4"
    with tempfile.TemporaryDirectory() as temp:
        image_path = Path(temp) / "product-image"
        image_response = requests.get(product["image_url"], timeout=30, headers={"User-Agent": "TerrabloomSmartFinds/1.0"})
        image_response.raise_for_status()
        image_path.write_bytes(image_response.content)
        with Image.open(image_path) as im:
            im.verify()
        make_poster(product, image_path, poster)
        script = make_script(product)
        asyncio.run(create_voiceover(script, audio))
        duration = probe_duration(audio)
        make_subtitles(script, duration, subtitles)
        render_video(poster, audio, subtitles, video)
        video_id = publish_to_facebook(video, product)

    state.setdefault("posts", {})[day_key] = {
        "product": product["name"],
        "facebook_video_id": video_id,
        "published_at_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    save_state(repo, gh_token, state, state_sha)
    print(f"Published {product['name']} successfully. Facebook video ID: {video_id}")


if __name__ == "__main__":
    main()
