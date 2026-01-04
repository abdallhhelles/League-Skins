import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple

import requests

CHAMP_LIST_URL = "http://ddragon.leagueoflegends.com/cdn/15.10.1/data/en_US/champion.json"
BASE_CHAMP_URL = "http://ddragon.leagueoflegends.com/cdn/15.10.1/data/en_US/champion/"
BASE_SPLASH_URL = "https://ddragon.leagueoflegends.com/cdn/img/champion/splash/"


def ensure_base_folder(base_folder: str) -> None:
    if not os.path.exists(base_folder):
        os.makedirs(base_folder, exist_ok=True)


def download_skin(champ: str, skin_num: int, skin_name: str, champ_folder: str) -> Tuple[str, str]:
    splash_url = f"{BASE_SPLASH_URL}{champ}_{skin_num}.jpg"
    file_path = f"{champ_folder}/{champ}_{skin_num}.jpg"

    if os.path.exists(file_path):
        return file_path, "skipped"

    try:
        response = requests.get(splash_url)
        response.raise_for_status()
        with open(file_path, "wb") as f:
            f.write(response.content)
        return file_path, "saved"
    except Exception as exc:  # pragma: no cover - defensive
        return splash_url, f"failed: {exc}"


def fetch_champions() -> List[str]:
    response = requests.get(CHAMP_LIST_URL)
    response.raise_for_status()
    champion_data = response.json()
    return list(champion_data["data"].keys())


def fetch_champion_skins(champ: str) -> List[Dict]:
    champ_url = f"{BASE_CHAMP_URL}{champ}.json"
    res = requests.get(champ_url)
    res.raise_for_status()
    champ_info = res.json()
    return champ_info["data"][champ]["skins"]


def sync_splash_assets(base_folder: str = "static/splash_arts", verbose: bool = True) -> Dict:
    """
    Ensure splash art and metadata exist locally for every champion skin.
    Downloads only what is missing so it is safe to run on every startup.
    """

    ensure_base_folder(base_folder)
    champions = fetch_champions()
    summary = {"champions": len(champions), "downloaded": 0, "skipped": 0, "errors": []}

    for champ in champions:
        if verbose:
            print(f"Processing {champ}...", flush=True)

        skins = fetch_champion_skins(champ)
        champ_folder = f"{base_folder}/{champ}"
        ensure_base_folder(champ_folder)

        skin_info = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for skin in skins:
                skin_num = skin["num"]
                skin_name = skin["name"]
                skin_info.append({"num": skin_num, "name": skin_name})
                futures.append(executor.submit(download_skin, champ, skin_num, skin_name, champ_folder))

            for future in as_completed(futures):
                file_path, status = future.result()
                if status == "saved":
                    summary["downloaded"] += 1
                elif status == "skipped":
                    summary["skipped"] += 1
                else:
                    summary["errors"].append({"file": file_path, "status": status})
                if verbose:
                    print(f"  {status.capitalize()}: {file_path}")

        json_path = f"{champ_folder}/skin_names.json"
        with open(json_path, "w") as json_file:
            json.dump(skin_info, json_file, indent=4)

        if verbose:
            print(f"  Saved skin info JSON: {json_path}\n")

    return summary


if __name__ == "__main__":  # pragma: no cover - manual execution
    report = sync_splash_assets()
    print("\nSync complete:")
    print(json.dumps(report, indent=2))
