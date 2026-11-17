#!/usr/bin/env python3

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path

import requests

# ============================================================================
# CONFIG
# ============================================================================

API_BASE = "https://api.pictoaccess.fr"
EXPORT_ENDPOINT = f"{API_BASE}/cards/accessibility_export"

MAX_IMAGE_WORKERS = 8
PAGE_DELAY = 0.2
REQUEST_TIMEOUT = 60

# ============================================================================
# HELPERS
# ============================================================================


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def save_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


def build_photo_url(url: str):

    if not url:
        return None

    if url.startswith("https://"):
        return url

    if url.startswith("//"):
        return f"https:{url}"

    if url.startswith("/"):
        return API_BASE + url

    return url


def download_image(session, url, output_file):

    try:

        if output_file.exists():
            return True

        response = session.get(
            url,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code != 200:
            print(
                f"[IMAGE] Failed ({response.status_code}) {url}"
            )
            return False

        with open(output_file, "wb") as f:
            f.write(response.content)

        return True

    except Exception as e:
        print(
            f"[IMAGE] Error downloading {url}: {e}"
        )
        return False


# ============================================================================
# EXPORT
# ============================================================================


def run_export(api_token, output_folder):

    output_folder = Path(output_folder)

    places_dir = output_folder / "places"
    images_dir = output_folder / "images"
    logs_dir = output_folder / "logs"

    ensure_dir(output_folder)
    ensure_dir(places_dir)
    ensure_dir(images_dir)
    ensure_dir(logs_dir)

    print(f"\nOutput folder:")
    print(output_folder.resolve())
    print()

    api_session = requests.Session()

    api_session.headers.update({
        "Accept": "application/vnd.picto-developer-v2+json",
        "X-Auth-Token": api_token
    })

    image_session = requests.Session()

    stats = {
        "pages": 0,
        "places": 0,
        "images": 0
    }

    seen_cursors = set()
    image_futures = []

    executor = ThreadPoolExecutor(
        max_workers=MAX_IMAGE_WORKERS
    )

    cursor = None

    try:

        while True:

            params = {}

            if cursor:
                params["cursor"] = cursor

            print(
                f"Fetching page {stats['pages'] + 1}"
            )

            response = api_session.get(
                EXPORT_ENDPOINT,
                params=params,
                timeout=REQUEST_TIMEOUT
            )

            response.raise_for_status()

            payload = response.json()

            places = payload.get("data", [])

            stats["pages"] += 1

            print(
                f"  received {len(places)} places"
            )

            for place in places:

                uuid = place.get("uuid")

                if not uuid:
                    continue

                # ----------------------------------------------------------
                # Save JSON immediately
                # ----------------------------------------------------------

                place_file = places_dir / f"{uuid}.json"

                save_json(
                    place_file,
                    place
                )

                stats["places"] += 1

                # ----------------------------------------------------------
                # Queue image downloads
                # ----------------------------------------------------------

                photos = place.get("photos", [])

                if not photos:
                    continue

                place_img_dir = images_dir / uuid
                ensure_dir(place_img_dir)

                for index, photo in enumerate(photos):

                    photo_url = build_photo_url(
                        photo.get("url")
                    )

                    if not photo_url:
                        continue

                    extension = (
                        Path(photo_url)
                        .suffix
                        .split("?")[0]
                    )

                    if not extension:
                        extension = ".jpg"

                    image_file = (
                        place_img_dir /
                        f"{index + 1}{extension}"
                    )

                    image_futures.append(
                        executor.submit(
                            download_image,
                            image_session,
                            photo_url,
                            image_file
                        )
                    )

            print(
                f"  total places saved: {stats['places']}"
            )

            save_json(
                logs_dir / "progress.json",
                stats
            )

            pagination = payload.get(
                "pagination",
                {}
            )

            if not pagination.get(
                "has_next_page",
                False
            ):
                print("\nEnd of export reached.")
                break

            next_cursor = pagination.get(
                "next_cursor"
            )

            if not next_cursor:
                print(
                    "\nWARNING: no next_cursor found"
                )
                break

            if next_cursor in seen_cursors:

                print(
                    "\nWARNING: pagination loop detected"
                )
                break

            seen_cursors.add(next_cursor)

            cursor = next_cursor

            time.sleep(PAGE_DELAY)

        # ------------------------------------------------------------------
        # Wait for all image downloads
        # ------------------------------------------------------------------

        print()
        print(
            f"Waiting for {len(image_futures)} queued image downloads..."
        )

        done, _ = wait(image_futures)

        stats["images"] = sum(
            1
            for future in done
            if future.result()
        )

    finally:

        executor.shutdown(wait=True)

    save_json(
        logs_dir / "progress.json",
        stats
    )

    save_json(
        output_folder / "summary.json",
        stats
    )

    print()
    print("=" * 60)
    print("EXPORT COMPLETE")
    print("=" * 60)
    print(f"Pages  : {stats['pages']}")
    print(f"Places : {stats['places']}")
    print(f"Images : {stats['images']}")
    print("=" * 60)


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--token",
        required=True,
        help="PictoAccess API token"
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output directory"
    )

    args = parser.parse_args()

    run_export(
        args.token,
        args.output
    )