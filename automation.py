import asyncio
import csv
import os
import random
import subprocess
import tempfile
from datetime import date
from pathlib import Path

import edge_tts
import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)
WIDTH, HEIGHT = 1080, 1920


def load_products():
    with (ROOT / "products.csv").open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    eligible = [
        p for p in rows
        if p.get("active", "").strip().lower() == "true"
        and p.get("name", "").strip()
        and p.get("tracking_url", "").strip().startswith(("https://", "http://"))
        and p.get("image_url", "").strip().startswith(("https://", "http://"))
        and p.get("benefit", "").strip()
    ]
    if not eligible:
        raise RuntimeError(
            "No eligible products. Add a verified DCM tracking_url, public image_url, "
            "short accurate benefit, and set active=true in products.csv."
        )
    # Stable daily rotation; one product is selected per calendar day.
    index = date.today().toordinal() % len(eligible)
    return eligible[index]


def download_image(url, destination):
    response = requests.get(url, timeout=30, headers={"User-Agent": "TerrabloomSmartFinds/1.0"})
    response.raise_for_status()
    destination.write_bytes(response.content)
    with Image.open(destination) as img:
        img.verify()


def load_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def wrap_text(draw, text, font, max_width):
    words, lines, current = text.split(), [], ""
    for word in words:
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

    # Brand header
    draw.rounded_rectangle((55, 55, 1025, 230), radius=42, fill="#174c35")
    draw.text((95, 95), "TERRABLOOM", font=load_font(62, True), fill="white")
    draw.text((100, 170), "SMART FINDS", font=load_font(32, True), fill="#d8edc8")

    # Product image panel
    with Image.open(image_path).convert("RGB") as source:
        fitted = ImageOps.contain(source, (900, 930))
        panel = Image.new("RGB", (930, 960), "white")
        panel.paste(fitted, ((930 - fitted.width) // 2, (960 - fitted.height) // 2))
        canvas.paste(panel, (75, 285))

    title_font = load_font(54, True)
    y = 1290
    for line in wrap_text(draw, product["name"], title_font, 940)[:2]:
        draw.text((75, y), line, font=title_font, fill="#173d2c")
        y += 70

    benefit_font = load_font(37)
    y += 20
    for line in wrap_text(draw, product["benefit"], benefit_font, 920)[:3]:
        draw.text((80, y), line, font=benefit_font, fill="#34443a")
        y += 54

    draw.rounded_rectangle((75, 1650, 1005, 1780), radius=35, fill="#e2a83b")
    cta = "CHECK THE PRODUCT LINK"
    bbox = draw.textbbox((0, 0), cta, font=load_font(42, True))
    draw.text(((WIDTH - (bbox[2] - bbox[0])) / 2, 1690), cta,
              font=load_font(42, True), fill="#1e2d21")
    draw.text((80, 1830), "Affiliate recommendation • #Ad", font=load_font(27), fill="#45554a")
    canvas.save(poster_path, quality=94)


async def create_voiceover(product, audio_path):
    speech = (
        f"Looking for a practical find? Take a look at {product['name']}. "
        f"{product['benefit']}. Tap the product link in this post to check the details. "
        "This is an affiliate recommendation from Terrabloom Smart Finds."
    )
    communicate = edge_tts.Communicate(speech, voice="en-US-AriaNeural", rate="+0%")
    await communicate.save(str(audio_path))


def render_video(poster, audio, video):
    command = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(poster), "-i", str(audio),
        "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac",
        "-b:a", "128k", "-pix_fmt", "yuv420p", "-shortest",
        "-vf", "scale=1080:1920,format=yuv420p", "-r", "25",
        "-movflags", "+faststart", str(video)
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)


def publish_to_facebook(video, product):
    page_id = os.environ.get("FB_PAGE_ID", "").strip()
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "").strip()
    version = os.environ.get("FACEBOOK_GRAPH_VERSION", "").strip()
    if not all([page_id, token, version]):
        raise RuntimeError(
            "Missing GitHub secrets: FB_PAGE_ID, FB_PAGE_ACCESS_TOKEN, "
            "FACEBOOK_GRAPH_VERSION. No post was published."
        )

    caption = (
        f"{product['name']}\n\n{product['benefit']}\n\n"
        f"Check it here: {product['tracking_url']}\n\n"
        "Affiliate disclosure: I may earn a commission if you buy through this link. "
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
        raise RuntimeError(f"Facebook publishing failed ({response.status_code}): {response.text[:1200]}")
    result = response.json()
    print(f"Facebook video published. Video ID: {result.get('id', 'unknown')}")


def main():
    product = load_products()
    safe_name = "".join(c.lower() if c.isalnum() else "-" for c in product["name"]).strip("-")
    poster = OUTPUT / f"{safe_name}.jpg"
    audio = OUTPUT / f"{safe_name}.mp3"
    video = OUTPUT / f"{date.today().isoformat()}-{safe_name}.mp4"

    with tempfile.TemporaryDirectory() as temp:
        image_path = Path(temp) / "product-image"
        download_image(product["image_url"], image_path)
        make_poster(product, image_path, poster)
        asyncio.run(create_voiceover(product, audio))
        render_video(poster, audio, video)

    publish_to_facebook(video, product)


if __name__ == "__main__":
    main()
