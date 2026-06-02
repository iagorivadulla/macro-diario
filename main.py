import json
from pathlib import Path
from rss import read_feeds
from agents import (
    filter_agent,
    resume_agent,
    control_agent,
    script_agent_2,
    script_control_2,
    broadcaster_kokoro, image_agent_v8
)
from scraper import get_articles
from produccion import producir
import os
import warnings

warnings.filterwarnings("ignore")

SCRIPT_DICT_PATH = Path(__file__).parent / "script_dict.json"
OUTPUT_VIDEO     = Path(__file__).parent / "video" / "episode.mp4"
FFMPEG           = Path(__file__).parent / "ffmpeg.exe"
IMAGES_PATH = Path(__file__).parent / "assets" / "news_images"


def flow():
    # ------------------------------------------------------------------
    # 1. Get and filter the news
    # ------------------------------------------------------------------
    news     = read_feeds()
    selected = filter_agent(news)

    articles = get_articles(selected)

    # ------------------------------------------------------------------
    # 2. Resume and quality test
    # ------------------------------------------------------------------
    resumes          = resume_agent(articles)
    accepted, denied = control_agent(resumes)
    passed           = list(accepted)
    print(f"Accepted: {len(accepted)}")

    for d in denied:
        print(f"  [!] Rechazado: {d['title'][:30]}... | Motivo: {d.get('control_reason')}")

    retries = 0
    while denied and retries > 0:
        resumes          = resume_agent(denied)
        accepted, denied = control_agent(resumes)
        passed.extend(accepted)
        print(f"Accepted: {len(accepted)}")
        for d in denied:
            print(f"  [!] Rechazado: {d['title'][:30]}... | Motivo: {d.get('control_reason')}")
        retries -= 1

    print("All articles summarized!")

    # ------------------------------------------------------------------
    # 3. Build and revise the script
    # ------------------------------------------------------------------
    script_dict = script_agent_2(passed)
    script_dict = script_control_2(passed, script_dict)

    for section in script_dict['sections']:
        section['images_paths'] = []

    with open(SCRIPT_DICT_PATH, "w", encoding="utf-8") as f:
        json.dump(script_dict, f, ensure_ascii=False, indent=2, default=str)
    print(f"script_dict guardado en {SCRIPT_DICT_PATH}")

    # ------------------------------------------------------------------
    # 4. Search and download images
    # ------------------------------------------------------------------
    script_dict = image_agent_v8(script_dict)

    # ------------------------------------------------------------------
    # 5. Create the voice path and save duration in the script
    # ------------------------------------------------------------------
    broadcaster_kokoro(script_dict)

    # ------------------------------------------------------------------
    # 6. Saves the script
    # ------------------------------------------------------------------
    with open(SCRIPT_DICT_PATH, "w", encoding="utf-8") as f:
        # Convertimos Paths a strings para que json no se queje
        json.dump(script_dict, f, ensure_ascii=False, indent=2, default=str)
    print(f"script_dict guardado en {SCRIPT_DICT_PATH}")

    # ------------------------------------------------------------------
    # 7. Build the video
    # ------------------------------------------------------------------
    producir(
        script_dict=script_dict,
        output=OUTPUT_VIDEO,
        ffmpeg=FFMPEG,
    )

    # --------------------------------------------------------------
    # 8. Delete temporal images
    #---------------------------------------------------------------

    for i in os.listdir(IMAGES_PATH):
        path = os.path.join(IMAGES_PATH, i)
        os.unlink(path)


def flow_test():

    with open(SCRIPT_DICT_PATH, "r", encoding="utf-8") as f:
        script_dict = json.load(f)

    #script_dict = image_agent_v8(script_dict)
    broadcaster_kokoro(script_dict)

    with open(SCRIPT_DICT_PATH, "w", encoding="utf-8") as f:
        json.dump(script_dict, f, ensure_ascii=False, indent=2, default=str)

    producir(script_dict=script_dict, output=OUTPUT_VIDEO, ffmpeg=FFMPEG,)

def flow_test_video():
    with open(SCRIPT_DICT_PATH, "r", encoding="utf-8") as f:
        script_dict = json.load(f)

    producir(script_dict=script_dict, output=OUTPUT_VIDEO, ffmpeg=FFMPEG)

if __name__ == "__main__":
    flow()