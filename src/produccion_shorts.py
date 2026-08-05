import argparse
import sys
import random
import textwrap
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from src.agents import broadcaster_kokoro

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
AUDIO = ROOT / "assets" / "audio" / "output.wav"
MUSIC = ROOT / "assets" / "audio" / "background_music.mp3"
BASE = ROOT / "assets" / "background" / "shorts.png"
EXPRESIONES = ROOT / "assets" / "background" / "presentador_no_fondo_2.png"
OUTPUT = ROOT / "video" / "short.mp4"

FPS = 25
VIDEO_H = 1672
VIDEO_W = 940

EYE_CENTER = (463, 853)
MOUTH_CENTER = (463, 916)

EYE_SCALE = 0.21
MOUTH_SCALE = 0.21

NEWS_IMAGE_X = 186
NEWS_IMAGE_Y = 391
NEWS_IMAGE_W = 572
NEWS_IMAGE_H = 268

# ---------------------------------------------------------------------------
# Subtítulos
# ---------------------------------------------------------------------------
SUB_FONT_SIZE       = 28
SUB_LINE_HEIGHT     = 42
SUB_LINES_VISIBLE   = 1
SUB_WRAP_WIDTH      = 38
SUB_PADDING_X       = 40
SUB_PADDING_Y       = 25
SUB_BG_ALPHA        = 175
SUB_Y_BOTTOM_MARGIN = 30
SUB_COLOR           = (255, 255, 255, 255)
SUB_SHADOW_COLOR    = (0, 0, 0, 210)
SUB_SHADOW_OFFSET   = 2

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

EYE_SPRITES = [
    (1624, 167, 2020, 307),
    (1624, 347, 2020, 480),
    (1624, 537, 2020, 676),
    (1624, 719, 2020, 880),
    (1624, 916, 2020, 1108),
    (1624, 1159, 2020, 1328),
]

MOUTH_SPRITES = [
    (2396, 169, 2612, 304),
    (2380, 341, 2598, 488),
    (2381, 524, 2597, 673),
    (2380, 709, 2597, 824),
    (2381, 862, 2599, 974),
    (2397, 1017, 2613, 1159),
    (2397, 1201, 2611, 1339),
]

BLINK_DURATION_FRAMES = 2
BLINK_INTERVAL_MIN = 1.0
BLINK_INTERVAL_MAX = 3.0

MOUTH_SEQUENCE = [0, 4, 1, 5, 2]


def rms_to_mouth(r: float) -> int:
    if r < 0.05:
        return MOUTH_SEQUENCE[0]
    return MOUTH_SEQUENCE[min(4, int(r * 5))]


def _cargar_fuente(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def eliminar_fondo_piel(pil_img):
    """
    Convierte en transparentes los píxeles del color de piel base
    de los recuadros para que solo se peguen los rasgos (ojos/boca/cejas).
    """
    img_rgba = pil_img.convert("RGBA")
    data = np.array(img_rgba)

    # Extraemos canales RGB
    r, g, b = data[:, :, 0], data[:, :, 1], data[:, :, 2]

    # Rango del tono de piel beige/grisáceo a eliminar en la hoja:
    # Ajustado a los valores exactos de la piel clara de presentador_no_fondo_2
    mask_piel = (
            (r >= 130) & (r <= 240) &
            (g >= 100) & (g <= 190) &
            (b >= 70) & (b <= 160)
    )

    # Ponemos el canal Alpha a 0 (transparente) en la piel del recuadro
    data[mask_piel, 3] = 0

    return Image.fromarray(data)


def cargar_sprites(base_path: Path, expresiones_path: Path):
    print("[sprites] Cargando base y expresiones...")
    body = Image.open(base_path).convert("RGBA")
    sheet = Image.open(expresiones_path).convert("RGBA")

    eyes = []
    for c in EYE_SPRITES:
        crop = sheet.crop(c).resize((int((c[2] - c[0]) * EYE_SCALE), int((c[3] - c[1]) * EYE_SCALE)), Image.NEAREST)
        eyes.append(eliminar_fondo_piel(crop))

    mouths = []
    for c in MOUTH_SPRITES:
        crop = sheet.crop(c).resize((int((c[2] - c[0]) * MOUTH_SCALE), int((c[3] - c[1]) * MOUTH_SCALE)), Image.NEAREST)
        mouths.append(eliminar_fondo_piel(crop))

    return body, eyes, mouths


def analizar_audio(audio_path: Path, fps: int) -> np.ndarray:
    import wave
    print(f"[audio] Analizando {audio_path.name}...")
    with wave.open(str(audio_path), "rb") as wf:
        sample_rate = wf.getframerate()
        samples = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)
        if wf.getnchannels() == 2:
            samples = samples.reshape(-1, 2).mean(axis=1)

    spf = sample_rate // fps
    n = len(samples) // spf
    rms = np.array([np.sqrt(np.mean(samples[i * spf:(i + 1) * spf] ** 2)) for i in range(n)])

    if rms.max() > 0:
        rms /= rms.max()
    return rms


def generar_secuencia_ojos(n_frames: int, fps: int) -> list:
    seq = [5] * n_frames
    frame = 0
    while frame < n_frames:
        frame += int(random.uniform(BLINK_INTERVAL_MIN, BLINK_INTERVAL_MAX) * fps)
        for d in range(BLINK_DURATION_FRAMES):
            if frame + d < n_frames:
                seq[frame + d] = 0
        frame += BLINK_DURATION_FRAMES
    return seq


def componer_frame(body, eye_img, mouth_img, video_size, news_image=None):
    frame = body.copy()

    frame.paste(eye_img, (EYE_CENTER[0] - eye_img.width // 2, EYE_CENTER[1] - eye_img.height // 2), eye_img)
    frame.paste(mouth_img, (MOUTH_CENTER[0] - mouth_img.width // 2, MOUTH_CENTER[1] - mouth_img.height // 2), mouth_img)

    final = frame.resize(video_size, Image.NEAREST).convert("RGB")

    if news_image is not None:
        scaled = news_image.resize((NEWS_IMAGE_W, NEWS_IMAGE_H), Image.LANCZOS)
        final.paste(scaled, (NEWS_IMAGE_X, NEWS_IMAGE_Y))

    return np.array(final)[:, :, ::-1]


def _texto_a_lineas(texto: str) -> list[str]:
    import re
    texto = texto.replace("*", "")
    texto = re.sub(r"\n+", " ", texto).strip()
    return textwrap.wrap(texto, width=SUB_WRAP_WIDTH)


def build_subtitle_timeline(script_dict: dict, fps: int) -> list:
    timeline = []
    cursor = 0

    for section in script_dict.get("sections", []):
        duration = section.get("audio_duration", 0.0)
        sec_frames = max(1, int(round(duration * fps)))
        texto = section.get("text", "").strip()
        lineas = _texto_a_lineas(texto) if texto else []

        timeline.append((cursor, cursor + sec_frames, lineas))
        cursor += sec_frames

    return timeline


def get_current_subtitle_lines(sub_timeline: list, frame_idx: int) -> list[str]:
    for start, end, lineas in sub_timeline:
        if start <= frame_idx < end:
            if not lineas:
                return []
            total_lineas = len(lineas)
            n_ventanas = max(1, total_lineas - SUB_LINES_VISIBLE + 1)
            progreso = (frame_idx - start) / max(1, end - start - 1)
            ventana_idx = min(int(progreso * n_ventanas), n_ventanas - 1)
            return lineas[ventana_idx: ventana_idx + SUB_LINES_VISIBLE]
    return []


def render_subtitle(frame_bgr: np.ndarray, lines: list[str], font: ImageFont.FreeTypeFont) -> np.ndarray:
    if not lines:
        return frame_bgr

    h, w = frame_bgr.shape[:2]

    band_h = SUB_PADDING_Y * 2 + len(lines) * SUB_LINE_HEIGHT
    band_y = h - SUB_Y_BOTTOM_MARGIN - band_h

    frame_pil = Image.fromarray(frame_bgr[:, :, ::-1]).convert("RGBA")

    overlay = Image.new("RGBA", (w, band_h), (0, 0, 0, SUB_BG_ALPHA))
    frame_pil.paste(overlay, (0, band_y), overlay)

    draw = ImageDraw.Draw(frame_pil)
    for i, line in enumerate(lines):
        y = band_y + SUB_PADDING_Y + i * SUB_LINE_HEIGHT

        # --- Cálculo para centrar el texto horizontalmente ---
        bbox = font.getbbox(line)
        text_w = bbox[2] - bbox[0]
        x = (w - text_w) // 2
        # -----------------------------------------------------

        # Sombra
        draw.text(
            (x + SUB_SHADOW_OFFSET, y + SUB_SHADOW_OFFSET),
            line,
            font=font,
            fill=SUB_SHADOW_COLOR,
        )
        # Texto principal
        draw.text((x, y), line, font=font, fill=SUB_COLOR)

    return np.array(frame_pil.convert("RGB"))[:, :, ::-1]


def build_image_timeline(script_dict: dict, fps: int) -> list:
    timeline = []
    cursor = 0

    for section in script_dict.get("sections", []):
        duration = section.get("audio_duration", 0.0)
        sec_frames = max(1, int(round(duration * fps)))

        paths = section.get("images_paths") or (
            [section["image_path"]] if section.get("image_path") else []
        )

        if not paths:
            timeline.append((cursor, cursor + sec_frames, None))
        else:
            frames_per_img = sec_frames // len(paths)
            remainder = sec_frames % len(paths)

            for i, path in enumerate(paths):
                img = None
                try:
                    img = Image.open(path).convert("RGB")
                except Exception as e:
                    print(f"[timeline] No se pudo cargar {path}: {e}")

                chunk = frames_per_img + (remainder if i == len(paths) - 1 else 0)
                timeline.append((cursor, cursor + chunk, img))
                cursor += chunk
            continue

        cursor += sec_frames

    return timeline


def get_current_image(timeline: list, frame_idx: int):
    for start, end, img in timeline:
        if start <= frame_idx < end:
            return img
    return None


def render(
        audio: Path = AUDIO,
        base: Path = BASE,
        expresiones: Path = EXPRESIONES,
        output: Path = OUTPUT,
        script_dict: dict = None,
) -> Path:
    import cv2

    output.parent.mkdir(parents=True, exist_ok=True)
    body, eyes, mouths = cargar_sprites(base, expresiones)
    rms = analizar_audio(audio, FPS)
    n_frames = len(rms)
    ojo_seq = generar_secuencia_ojos(n_frames, FPS)

    img_timeline = []
    sub_timeline = []
    font = None

    if script_dict:
        img_timeline = build_image_timeline(script_dict, FPS)
        sub_timeline = build_subtitle_timeline(script_dict, FPS)
        font = _cargar_fuente(SUB_FONT_SIZE)

    temp = output.parent / f"_temp_{output.stem}.mp4"
    writer = cv2.VideoWriter(str(temp), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (VIDEO_W, VIDEO_H))

    print(f"\n[render] Generando {n_frames} frames ({n_frames / FPS:.1f}s)...")
    for i in range(n_frames):
        news_img = get_current_image(img_timeline, i) if img_timeline else None

        frame = componer_frame(body, eyes[ojo_seq[i]], mouths[rms_to_mouth(rms[i])], (VIDEO_W, VIDEO_H), news_img)

        if sub_timeline and font is not None:
            lines = get_current_subtitle_lines(sub_timeline, i)
            frame = render_subtitle(frame, lines, font)

        writer.write(frame)

        if i % (FPS * 15) == 0:
            print(f"  Progreso: {i / n_frames * 100:.0f}%")

    writer.release()
    return temp


def producir(
        script_dict: dict,
        output: Path = OUTPUT,
        audio: Path = AUDIO,
        base: Path = BASE,
        expresiones: Path = EXPRESIONES,
        ffmpeg: Path = ROOT / "ffmpeg.exe",
) -> bool:
    import subprocess

    for p in (base, expresiones, audio):
        if not p.exists():
            print(f"[producir] Error — archivo requerido no encontrado: {p}")
            return False

    temp = render(
        audio=audio,
        base=base,
        expresiones=expresiones,
        output=output,
        script_dict=script_dict,
    )

    result = subprocess.run(
        [
            str(ffmpeg), "-y",
            "-i", str(temp),  # Entrada 0: Vídeo mudo
            "-i", str(audio),  # Entrada 1: Voz del presentador
            "-stream_loop", "-1",  # Entrada 2: Repetir música en bucle
            "-i", str(MUSIC),
            "-filter_complex",
            # Multiplicamos la voz x1.0 y la música x0.12 (12% de volumen). Luego las mezclamos con amix.
            "[1:a]volume=1.0[voice];"
            "[2:a]volume=0.12[bgm];"
            "[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
            "-map", "0:v",  # Mapear el vídeo del temp
            "-map", "[aout]",  # Mapear el audio mezclado
            "-c:v", "libx264",
            "-c:a", "aac",
            "-shortest",
            str(output),
        ],
        capture_output=True,
    )

    temp.unlink(missing_ok=True)

    if result.returncode != 0:
        print(f"[producir] ffmpeg falló:\n{result.stderr.decode()}")
        return False

    print(f"[producir] Vídeo exportado: {output}")
    return True


# ---------------------------------------------------------------------------
# Bucle para crear los shorts
# ---------------------------------------------------------------------------

def crear_shorts(script_dict: dict, ffmpeg_path: Path = ROOT / "ffmpeg.exe"):
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
             "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

    hoy = datetime.now()
    fecha = f"{dias[hoy.weekday()]} {hoy.day} de {meses[hoy.month - 1]}"

    intro = {
        "type": "intro",
        "title": "Intro Shorts",
        "text": f"Bienvenidos a Macro Diario Shorts. Hoy es {fecha}.",
        "images_paths": []
    }

    outro = {
        "type": "outro",
        "title": "Outro Shorts",
        "text": "Si quieres conocer todas las noticias del día, tienes el noticiero completo en nuestro canal de YouTube. Hasta mañana.",
        "images_paths": []
    }

    news_sections = [
        s for s in script_dict.get("sections", [])
        if s.get("type", "").startswith("news_")
    ]

    shorts_dir = ROOT / "video" / "shorts"
    shorts_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[Shorts] Procesando {len(news_sections)} noticias como shorts...")

    for i, news in enumerate(news_sections, start=1):
        print(f"\n--- Procesando Short {i}/{len(news_sections)} ---")

        short_script = {
            "sections": [
                deepcopy(intro),
                deepcopy(news),
                deepcopy(outro)
            ]
        }

        # 1. Archivo de audio temporal/único para este short
        short_audio_path = shorts_dir / f"short_{i:02d}.wav"

        # 2. Sintetizar el audio usando Kokoro (actualiza audio_duration en short_script)
        broadcaster_kokoro(
            script_dict=short_script,
            output_path=str(short_audio_path)
        )

        # 3. Producir el vídeo asociando su audio y su script correspondientes
        producir(
            script_dict=short_script,
            output=shorts_dir / f"short_{i:02d}.mp4",
            audio=short_audio_path,
            base=BASE,
            expresiones=EXPRESIONES,
            ffmpeg=ffmpeg_path,
        )


def produce_shorts():
    parser = argparse.ArgumentParser(description="Generador de Shorts con Presentador Pixel-Art")
    parser.add_argument("--script", type=Path,
                        default=ROOT / "script_dict.json")
    parser.add_argument("--ffmpeg", type=Path, default=ROOT / "ffmpeg.exe")
    args = parser.parse_args()

    if not args.script.exists():
        print(f"[error] No se encuentra el script JSON: {args.script}")
        sys.exit(1)

    import json
    with open(args.script, encoding="utf-8") as f:
        script_dict = json.load(f)

    crear_shorts(script_dict, ffmpeg_path=args.ffmpeg)


if __name__ == "__main__":
    produce_shorts()