import requests
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

CHAMP_LIST_URL = 'http://ddragon.leagueoflegends.com/cdn/15.10.1/data/en_US/champion.json'
BASE_CHAMP_URL = 'http://ddragon.leagueoflegends.com/cdn/15.10.1/data/en_US/champion/'
BASE_SPLASH_URL = 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/'

if not os.path.exists("static/splash_arts"):
    os.mkdir("static/splash_arts")

def download_skin(champ, skin_num, skin_name, champ_folder):
    splash_url = f"{BASE_SPLASH_URL}{champ}_{skin_num}.jpg"
    file_path = f"{champ_folder}/{champ}_{skin_num}.jpg"

    if os.path.exists(file_path):
        return (file_path, "skipped")

    try:
        img_data = requests.get(splash_url).content
        with open(file_path, 'wb') as f:
            f.write(img_data)
        return (file_path, "saved")
    except Exception as e:
        return (splash_url, f"failed: {e}")

response = requests.get(CHAMP_LIST_URL)
champion_data = response.json()
champions = list(champion_data['data'].keys())

for champ in champions:
    print(f"Processing {champ}...")
    champ_url = f"{BASE_CHAMP_URL}{champ}.json"
    res = requests.get(champ_url)
    champ_info = res.json()
    skins = champ_info['data'][champ]['skins']

    champ_folder = f"static/splash_arts/{champ}"
    if not os.path.exists(champ_folder):
        os.mkdir(champ_folder)

    skin_info = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for skin in skins:
            skin_num = skin['num']
            skin_name = skin['name']
            skin_info.append({"num": skin_num, "name": skin_name})
            futures.append(executor.submit(download_skin, champ, skin_num, skin_name, champ_folder))

        for future in as_completed(futures):
            file_path, status = future.result()
            print(f"  {status.capitalize()}: {file_path}")

    json_path = f"{champ_folder}/skin_names.json"
    with open(json_path, 'w') as json_file:
        json.dump(skin_info, json_file, indent=4)

    print(f"  Saved skin info JSON: {json_path}\n")
