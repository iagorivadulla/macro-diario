import json
from pathlib import Path
from src.rss import read_feeds
from src.agents import (
    filter_agent,
    resume_agent,
    control_agent,
    script_agent_2,
    script_control_3,
    broadcaster_kokoro, image_agent_v9, image_agent_v8
)
from src.scraper import get_articles
from src.produccion import producir
from src.produccion_shorts import produce_shorts
import warnings

warnings.filterwarnings("ignore")

SCRIPT_DICT_PATH = Path(__file__).parent / "script_dict.json"
OUTPUT_VIDEO     = Path(__file__).parent / "video" / "episode.mp4"
FFMPEG           = Path(__file__).parent / "assets" / "audio" / "ffmpeg.exe"
IMAGES_PATH = Path(__file__).parent / "assets" / "news_images"
AUDIO_PATH_FILE = Path(__file__).parent / "assets" / "audio" / "output.wav"
SHORTS_AUDIO_PATH = Path(__file__).parent / "video" / "shorts"


def flow():
    # ------------------------------------------------------------------
    # 1. Get and filter the news
    # ------------------------------------------------------------------
    news     = read_feeds()

    selected = filter_agent(news)
    print(f'Selected {len(selected)} articles')
    print(selected)

    articles = get_articles(selected)
    print(articles)
    # ------------------------------------------------------------------
    # 2. Resume and quality test
    # ------------------------------------------------------------------
    resumes          = resume_agent(articles)
    print(f'Resumes {len(resumes)} articles')
    print(resumes)
    accepted, denied = control_agent(resumes)
    passed           = list(accepted)
    print(f"Accepted: {len(passed)}")
    print(passed)
    print(f"Denied: {len(denied)}")
    print(denied)

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
    script_dict = script_control_3(script_dict)

    for section in script_dict['sections']:
        section['images_paths'] = []

    with open(SCRIPT_DICT_PATH, "w", encoding="utf-8") as f:
        json.dump(script_dict, f, ensure_ascii=False, indent=2, default=str)
    print(f"script_dict guardado en {SCRIPT_DICT_PATH}")

    # ------------------------------------------------------------------
    # 4. Search and download images
    # ------------------------------------------------------------------
    script_dict = image_agent_v9(script_dict)
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

    produce_shorts()

    # --------------------------------------------------------------
    # 8. Delete temporal images and audios
    #---------------------------------------------------------------

    def delete():
        import os

        # Delete images
        for i in os.listdir(IMAGES_PATH):
            path = os.path.join(IMAGES_PATH, i)
            os.unlink(path)

        # Delete output.wav
        os.unlink(AUDIO_PATH_FILE)

        # Delete all short audios
        for i in os.listdir(SHORTS_AUDIO_PATH):
            if i.endswith(".wav"):
                path = os.path.join(SHORTS_AUDIO_PATH, i)
                os.unlink(path)


    delete()





if __name__ == "__main__":
    flow()