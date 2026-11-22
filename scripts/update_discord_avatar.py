"""Sync the Discord profile picture into the profile README banner.

Fetches the current avatar through Lanyard, converts it to the monochrome
banner treatment, and regenerates assets/banner.svg from the template.

Run manually with:  python scripts/update_discord_avatar.py
"""

from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

import requests
from PIL import Image, ImageEnhance, ImageOps

USER_ID = "822397936980721674"
ROOT = Path(__file__).resolve().parents[1]
AVATAR_PATH = ROOT / "assets" / "avatar-mono.png"
TEMPLATE_PATH = ROOT / "assets" / "banner.template.svg"
BANNER_PATH = ROOT / "assets" / "banner.svg"
PLACEHOLDER = "{{AVATAR_BASE64}}"

HEADERS = {"User-Agent": "ps1coseado-profile-readme/1.0"}


def fetch_avatar_url() -> str:
    response = requests.get(
        f"https://api.lanyard.rest/v1/users/{USER_ID}",
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(f"Lanyard returned an error: {payload.get('error')}")

    user = payload["data"]["discord_user"]
    user_id = str(user["id"])
    avatar_hash = user.get("avatar")

    if avatar_hash:
        # Discord's PNG endpoint returns a still frame for animated avatars too.
        return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png?size=512"

    # Fallback for users with no custom avatar.
    index = (int(user_id) >> 22) % 6
    return f"https://cdn.discordapp.com/embed/avatars/{index}.png"


def make_monochrome_avatar(raw: bytes) -> bytes:
    image = Image.open(io.BytesIO(raw)).convert("RGB")

    width, height = image.size
    side = min(width, height)
    image = image.crop(
        ((width - side) // 2, (height - side) // 2, (width + side) // 2, (height + side) // 2)
    ).resize((344, 344), Image.LANCZOS)

    gray = ImageOps.grayscale(image)
    gray = ImageEnhance.Contrast(gray).enhance(1.12)
    gray = ImageEnhance.Brightness(gray).enhance(1.05)
    monochrome = ImageOps.colorize(gray, black=(4, 4, 5), white=(238, 238, 242))

    output = io.BytesIO()
    monochrome.save(output, format="PNG", optimize=True)
    return output.getvalue()


def main() -> int:
    try:
        avatar_url = fetch_avatar_url()
        response = requests.get(avatar_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - keep the scheduled job quiet on outages
        print(f"warning: could not fetch the Discord avatar: {exc}", file=sys.stderr)
        return 0

    new_avatar = make_monochrome_avatar(response.content)

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        raise RuntimeError(f"placeholder {PLACEHOLDER} missing from {TEMPLATE_PATH}")

    new_banner = template.replace(
        PLACEHOLDER,
        base64.b64encode(new_avatar).decode("ascii"),
    )

    old_avatar = AVATAR_PATH.read_bytes() if AVATAR_PATH.exists() else b""
    old_banner = BANNER_PATH.read_text(encoding="utf-8") if BANNER_PATH.exists() else ""

    if new_avatar == old_avatar and new_banner == old_banner:
        print("Discord avatar is unchanged.")
        return 0

    AVATAR_PATH.write_bytes(new_avatar)
    BANNER_PATH.write_text(new_banner, encoding="utf-8")
    print("Updated the Discord avatar and banner.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
