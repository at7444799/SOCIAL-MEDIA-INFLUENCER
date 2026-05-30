import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import requests


GRAPH_VERSION = os.getenv("GRAPH_VERSION", "v25.0")
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"

ROOT = Path(__file__).resolve().parent
PHOTOS_ROOT = ROOT / "media" / "photos"
DATA_DIR = ROOT / "data"
HISTORY_FILE = DATA_DIR / "posted_history.json"

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

CATEGORY_MAP = {
    "morning": PHOTOS_ROOT / "morning",
    "evening": PHOTOS_ROOT / "evening",
    "weekend": PHOTOS_ROOT / "weekend",
}


def log(message: str) -> None:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{now}] {message}", flush=True)


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing GitHub Secret / environment variable: {name}")
    return value


def optional_env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def load_history() -> Dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not HISTORY_FILE.exists():
        HISTORY_FILE.write_text(json.dumps({"posted": []}, indent=2), encoding="utf-8")
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"posted": []}


def save_history(history: Dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")


def detect_mode() -> str:
    """
    GitHub Actions uses UTC. This converts to India time and chooses the post type.
    Schedule plan:
    - Morning around 8:30 AM IST -> morning
    - Evening around 8:30 PM IST -> evening
    - Weekend around 11:00 AM IST on Sat/Sun -> weekend
    """
    ist = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    weekday = ist.weekday()  # Monday=0, Sunday=6
    hour = ist.hour

    if weekday in (5, 6) and 10 <= hour <= 12:
        return "weekend"
    if 4 <= hour < 13:
        return "morning"
    return "evening"


def get_all_images(category: str) -> List[Path]:
    folder = CATEGORY_MAP[category]
    if not folder.exists():
        raise RuntimeError(f"Missing category folder: {folder}")

    images = [
        p for p in folder.rglob("*")
        if p.is_file()
        and p.suffix.lower() in ALLOWED_IMAGE_EXTENSIONS
        and not p.name.startswith(".")
    ]
    return sorted(images)


def choose_two_images(category: str) -> List[Path]:
    images = get_all_images(category)
    if len(images) < 2:
        raise RuntimeError(
            f"Need at least 2 images in media/photos/{category}/ or its subfolders. "
            f"Found only {len(images)}."
        )
    return random.sample(images, 2)


def github_raw_url(file_path: Path) -> str:
    """
    Makes a public raw GitHub URL for the current commit.
    Your repository must be public for Meta/Instagram to fetch this URL.
    """
    repository = required_env("GITHUB_REPOSITORY")  # username/repo
    sha = optional_env("GITHUB_SHA", "main")
    relative = file_path.relative_to(ROOT).as_posix()

    # encode spaces and unsafe chars simply
    from urllib.parse import quote
    relative_encoded = "/".join(quote(part) for part in relative.split("/"))
    return f"https://raw.githubusercontent.com/{repository}/{sha}/{relative_encoded}"


def nvidia_caption(category: str, selected_images: List[Path]) -> str:
    api_key = optional_env("NVIDIA_API_KEY")
    model = optional_env("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")

    fallback = fallback_caption(category)

    if not api_key:
        log("NVIDIA_API_KEY not found. Using fallback caption.")
        return fallback

    image_names = ", ".join([p.stem.replace("_", " ") for p in selected_images])
    prompt = f"""
Create one viral caption for an Indian AI/lifestyle/fashion influencer post.

Post category: {category}
Image context from filenames: {image_names}

Rules:
- Hinglish + English mix
- Confident influencer tone
- Safe for Instagram and Facebook
- No adult explicit content
- No fake claims
- No mention of AI-generated
- Include 12 to 18 relevant hashtags
- Make the caption fresh, stylish, and short
- Return only the final caption text
"""

    try:
        response = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You write viral but safe social media captions."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.9,
                "max_tokens": 350,
            },
            timeout=60,
        )

        data = response.json()
        if response.status_code >= 400:
            log(f"NVIDIA API error status {response.status_code}: {data}")
            return fallback

        caption = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if not caption:
            return fallback
        return caption

    except Exception as exc:
        log(f"NVIDIA caption failed: {exc}")
        return fallback


def fallback_caption(category: str) -> str:
    presets = {
        "morning": [
            "New day, new glow ✨ Starting soft but moving strong. #MorningVibes #InfluencerLife #DelhiBlogger #LifestyleCreator #FashionReels #DailyGlow #GoodMorning #InstaDaily #CreatorMode #StyleInspo #PositiveVibes #DesiInfluencer",
            "Woke up with calm energy and main character mood ☀️ #MorningMood #SoftLife #LifestyleInfluencer #FashionDaily #GlowUp #CreatorLife #IndianInfluencer #InstaVibes #DailyPost #NewDayNewEnergy #StyleDiaries #ReelsIndia",
        ],
        "evening": [
            "Night plans, city lights, and a little extra confidence ✨ #NightLife #EveningVibes #ClubLook #FashionInfluencer #LifestyleCreator #DelhiNights #InstaStyle #ViralReels #CreatorMode #StyleInspo #WeekendMood #DesiGirlVibes",
            "Evening glow hits different when the vibe is right 🌙 #EveningMood #NightOut #InfluencerStyle #LifestyleBlogger #FashionVibes #InstaDaily #DelhiBlogger #PartyLook #ReelsIndia #TrendingNow #StyleDiaries #CreatorLife",
        ],
        "weekend": [
            "Weekend escape mode: ON ✈️✨ #WeekendVibes #TravelDiaries #TripMood #LifestyleInfluencer #TravelReels #FashionTravel #InstaTravel #CreatorLife #Wanderlust #DesiInfluencer #ReelsIndia #VacationMood",
            "Some weekends are for memories, not schedules 🌍✨ #WeekendTravel #TravelMood #LifestyleCreator #InfluencerLife #TripDiaries #FashionInspo #InstaVibes #ReelsIndia #TravelStyle #CreatorMode #ExploreMore #ViralPost",
        ],
    }
    return random.choice(presets.get(category, presets["morning"]))


def graph_post(endpoint: str, payload: Dict, timeout: int = 120) -> Dict:
    url = f"{GRAPH_BASE}/{endpoint.lstrip('/')}"
    response = requests.post(url, data=payload, timeout=timeout)
    try:
        data = response.json()
    except Exception:
        data = {"raw_response": response.text}

    if response.status_code >= 400 or "error" in data:
        raise RuntimeError(f"Meta API error at {endpoint}: {data}")

    return data


def graph_get(endpoint: str, params: Dict, timeout: int = 60) -> Dict:
    url = f"{GRAPH_BASE}/{endpoint.lstrip('/')}"
    response = requests.get(url, params=params, timeout=timeout)
    try:
        data = response.json()
    except Exception:
        data = {"raw_response": response.text}

    if response.status_code >= 400 or "error" in data:
        raise RuntimeError(f"Meta API GET error at {endpoint}: {data}")

    return data


def publish_instagram_carousel(ig_user_id: str, token: str, image_urls: List[str], caption: str) -> str:
    """
    Creates 2 carousel item containers, creates carousel parent, publishes it.
    """
    log("Creating Instagram carousel item containers...")
    children = []

    for url in image_urls:
        child = graph_post(
            f"{ig_user_id}/media",
            {
                "image_url": url,
                "is_carousel_item": "true",
                "access_token": token,
            },
        )
        creation_id = child.get("id")
        if not creation_id:
            raise RuntimeError(f"No Instagram child creation id returned: {child}")
        children.append(creation_id)

    log("Creating Instagram carousel parent container...")
    parent = graph_post(
        f"{ig_user_id}/media",
        {
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "caption": caption,
            "access_token": token,
        },
    )
    parent_id = parent.get("id")
    if not parent_id:
        raise RuntimeError(f"No Instagram parent creation id returned: {parent}")

    # Give Meta a few seconds to process the carousel container
    time.sleep(10)

    log("Publishing Instagram carousel...")
    published = graph_post(
        f"{ig_user_id}/media_publish",
        {
            "creation_id": parent_id,
            "access_token": token,
        },
    )

    media_id = published.get("id")
    if not media_id:
        raise RuntimeError(f"No Instagram media id returned: {published}")

    log(f"Instagram published media id: {media_id}")
    return media_id


def publish_facebook_multi_photo(page_id: str, token: str, image_urls: List[str], caption: str) -> str:
    """
    Uploads photos unpublished, then attaches them to one Page feed post.
    """
    log("Uploading Facebook unpublished photos...")
    media_ids = []

    for url in image_urls:
        result = graph_post(
            f"{page_id}/photos",
            {
                "url": url,
                "published": "false",
                "access_token": token,
            },
        )
        photo_id = result.get("id")
        if not photo_id:
            raise RuntimeError(f"No Facebook photo id returned: {result}")
        media_ids.append(photo_id)

    payload = {
        "message": caption,
        "access_token": token,
    }

    for index, media_id in enumerate(media_ids):
        payload[f"attached_media[{index}]"] = json.dumps({"media_fbid": media_id})

    log("Publishing Facebook Page multi-photo post...")
    result = graph_post(f"{page_id}/feed", payload)
    post_id = result.get("id")
    if not post_id:
        raise RuntimeError(f"No Facebook post id returned: {result}")

    log(f"Facebook published post id: {post_id}")
    return post_id


def delete_used_images(images: List[Path]) -> None:
    for image in images:
        try:
            image.unlink()
            log(f"Deleted used image: {image.relative_to(ROOT)}")
        except FileNotFoundError:
            pass


def update_history(category: str, images: List[Path], instagram_id: str, facebook_id: str, caption: str) -> None:
    history = load_history()
    posted = history.setdefault("posted", [])
    now = datetime.utcnow().isoformat() + "Z"

    for image in images:
        posted.append(
            {
                "time": now,
                "category": category,
                "image": image.relative_to(ROOT).as_posix(),
                "instagram_id": instagram_id,
                "facebook_id": facebook_id,
            }
        )

    history["last_caption"] = caption
    save_history(history)


def run(category: str) -> None:
    if category == "auto":
        category = detect_mode()

    if category not in CATEGORY_MAP:
        raise RuntimeError(f"Invalid category/mode: {category}. Use morning, evening, weekend, or auto.")

    log(f"Selected mode/category: {category}")

    token = required_env("FB_PAGE_ACCESS_TOKEN")
    page_id = required_env("FB_PAGE_ID")
    ig_user_id = required_env("IG_USER_ID")

    images = choose_two_images(category)
    log("Selected images:")
    for img in images:
        log(f" - {img.relative_to(ROOT)}")

    image_urls = [github_raw_url(img) for img in images]
    log("Public image URLs:")
    for url in image_urls:
        log(f" - {url}")

    caption = nvidia_caption(category, images)
    log("Generated caption:")
    log(caption)

    instagram_id = publish_instagram_carousel(ig_user_id, token, image_urls, caption)
    facebook_id = publish_facebook_multi_photo(page_id, token, image_urls, caption)

    delete_used_images(images)
    update_history(category, images, instagram_id, facebook_id, caption)

    log("Done. Images were posted and deleted locally. GitHub workflow will commit deletions.")


def main():
    parser = argparse.ArgumentParser(description="AI influencer auto-posting bot")
    parser.add_argument(
        "--mode",
        default=os.getenv("POST_MODE", "auto"),
        choices=["auto", "morning", "evening", "weekend"],
        help="Which category to post from.",
    )
    args = parser.parse_args()

    try:
        run(args.mode)
    except Exception as exc:
        log(f"BOT FAILED: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
