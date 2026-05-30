import argparse
import sys
import random
import textwrap
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent
AUDIO = ROOT / "output.wav"
BASE = ROOT / "assets" / "presentador_fondo.png"
EXPRESIONES = ROOT / "assets" / "presentador_no_fondo_2.png"
OUTPUT = ROOT / "video" / "episode.mp4"

FPS = 25
VIDEO_W = 1672
VIDEO_H = 941

EYE_CENTER = (415, 346)
MOUTH_CENTER = (415, 404)
EYE_SCALE = 0.19
MOUTH_SCALE = 0.19

NEWS_IMAGE_X = 797
NEWS_IMAGE_Y = 240
NEWS_IMAGE_W = 750
NEWS_IMAGE_H = 360

# ---------------------------------------------------------------------------
# Configuración de Subtítulos
# ---------------------------------------------------------------------------
SUB_FONT_SIZE       = 35          # tamaño de fuente en px
SUB_LINE_HEIGHT     = 54          # espacio entre líneas en px
SUB_LINES_VISIBLE   = 1           # líneas mostradas a la vez
SUB_WRAP_WIDTH      = 72          # caracteres por línea antes de hacer wrap
SUB_PADDING_X       = 50          # margen horizontal interior de la banda
SUB_PADDING_Y       = 18          # margen vertical interior de la banda
SUB_BG_ALPHA        = 175         # opacidad del fondo (0=transparente, 255=sólido)
SUB_Y_BOTTOM_MARGIN = 30          # distancia al borde inferior del vídeo
SUB_COLOR           = (255, 255, 255, 255)   # blanco opaco
SUB_SHADOW_COLOR    = (0, 0, 0, 210)         # sombra oscura
SUB_SHADOW_OFFSET   = 2           # píxeles de desplazamiento de la sombra

# Fuentes en orden de preferencia (se usa la primera que exista)
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

EYE_SPRITES = [
    (1624, 167, 2020, 307),  # 0 close
    (1624, 347, 2020, 480),  # 1 left blink
    (1624, 537, 2020, 676),  # 2 up eyebow
    (1624, 719, 2020, 880),  # 3 half closed
    (1624, 916, 2020, 1108),  # 4 mad
    (1624, 1159, 2020, 1328),  # 5 full open
]

MOUTH_SPRITES = [
    (2396, 169, 2612, 304),  # 0 close
    (2380, 341, 2598, 488),  # 1 half open
    (2381, 524, 2597, 673),  # 2 máx open
    (2380, 709, 2597, 824),  # 3 closed serious
    (2381, 862, 2599, 974),  # 4 min open
    (2397, 1017, 2613, 1159),  # 5 half open long
    (2397, 1201, 2611, 1339),  # 6 mid smile
]

BLINK_DURATION_FRAMES = 2
BLINK_INTERVAL_MIN = 1.0
BLINK_INTERVAL_MAX = 3.0

MOUTH_SEQUENCE = [0, 4, 1, 5, 2]


def rms_to_mouth(r: float) -> int:
    if r < 0.05:
        return MOUTH_SEQUENCE[0]
    return MOUTH_SEQUENCE[min(4, int(r * 5))]


# ---------------------------------------------------------------------------
# Process
# ---------------------------------------------------------------------------

def _cargar_fuente(size: int) -> ImageFont.FreeTypeFont:
    """Carga la primera fuente TTF disponible; fallback a la fuente por defecto."""
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    print("[subtítulos] ⚠ No se encontró fuente TTF, usando fuente por defecto (sin tildes)")
    return ImageFont.load_default()

def cargar_sprites(base_path: Path, expresiones_path: Path):
    print("[sprites] Cargando base y expresiones...")
    body = Image.open(base_path).convert("RGBA")
    sheet = Image.open(expresiones_path).convert("RGBA")

    eyes = [
        sheet.crop(c).resize((int((c[2] - c[0]) * EYE_SCALE), int((c[3] - c[1]) * EYE_SCALE)), Image.NEAREST)
        for c in EYE_SPRITES
    ]
    mouths = [
        sheet.crop(c).resize((int((c[2] - c[0]) * MOUTH_SCALE), int((c[3] - c[1]) * MOUTH_SCALE)), Image.NEAREST)
        for c in MOUTH_SPRITES
    ]
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
    seq = [5] * n_frames  # 5 = abierto normal
    frame = 0
    while frame < n_frames:
        frame += int(random.uniform(BLINK_INTERVAL_MIN, BLINK_INTERVAL_MAX) * fps)
        for d in range(BLINK_DURATION_FRAMES):
            if frame + d < n_frames:
                seq[frame + d] = 0  # 0 = cerrado
        frame += BLINK_DURATION_FRAMES
    return seq


def componer_frame(body, eye_img, mouth_img, video_size, news_image=None):
    frame = body.copy()

    frame.paste(eye_img, (EYE_CENTER[0] - eye_img.width // 2, EYE_CENTER[1] - eye_img.height // 2), eye_img)
    frame.paste(mouth_img, (MOUTH_CENTER[0] - mouth_img.width // 2, MOUTH_CENTER[1] - mouth_img.height // 2), mouth_img)

    # Redimensión final al tamaño de vídeo
    final = frame.resize(video_size, Image.NEAREST).convert("RGB")

    # Overlay de imagen de noticia (se aplica DESPUÉS del resize para usar coordenadas 1280x720)
    if news_image is not None:
        scaled = news_image.resize((NEWS_IMAGE_W, NEWS_IMAGE_H), Image.LANCZOS)
        final.paste(scaled, (NEWS_IMAGE_X, NEWS_IMAGE_Y))

    return np.array(final)[:, :, ::-1]
# ---------------------------------------------------------------------------
# Subtítulos
# ---------------------------------------------------------------------------

def _texto_a_lineas(texto: str) -> list[str]:
    """
    Limpia el texto y lo divide en líneas de ancho máximo SUB_WRAP_WIDTH.
    Elimina marcado Markdown simple (*texto*) y saltos de párrafo redundantes.
    """
    # Quitar asteriscos de énfasis Markdown
    texto = texto.replace("*", "")
    # Colapsar múltiples saltos de línea en uno solo
    import re
    texto = re.sub(r"\n+", " ", texto).strip()
    return textwrap.wrap(texto, width=SUB_WRAP_WIDTH)


def build_subtitle_timeline(script_dict: dict, fps: int) -> list:
    """
    Devuelve una lista de tuplas:
        (start_frame, end_frame, lineas_totales: list[str])

    Cada sección tiene su bloque de líneas; el renderizador decide qué
    ventana de SUB_LINES_VISIBLE líneas mostrar en cada frame.
    """
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
    """
    Devuelve las SUB_LINES_VISIBLE líneas a mostrar en el frame actual.
    El avance es proporcional al progreso dentro de la sección.
    """
    for start, end, lineas in sub_timeline:
        if start <= frame_idx < end:
            if not lineas:
                return []
            total_lineas = len(lineas)
            # Número de ventanas posibles (pueden solaparse 0 líneas entre ventanas)
            n_ventanas = max(1, total_lineas - SUB_LINES_VISIBLE + 1)
            progreso = (frame_idx - start) / max(1, end - start - 1)
            ventana_idx = min(int(progreso * n_ventanas), n_ventanas - 1)
            return lineas[ventana_idx: ventana_idx + SUB_LINES_VISIBLE]
    return []


def render_subtitle(frame_bgr: np.ndarray, lines: list[str], font: ImageFont.FreeTypeFont) -> np.ndarray:
    """
    Dibuja la banda de subtítulos en la parte inferior del frame.
    Recibe y devuelve un array BGR de NumPy.
    """
    if not lines:
        return frame_bgr

    h, w = frame_bgr.shape[:2]

    # Altura de la banda
    band_h = SUB_PADDING_Y * 2 + len(lines) * SUB_LINE_HEIGHT
    band_y = h - SUB_Y_BOTTOM_MARGIN - band_h

    # Convertir frame BGR → PIL RGBA para poder usar transparencia
    frame_pil = Image.fromarray(frame_bgr[:, :, ::-1]).convert("RGBA")

    # Banda semitransparente
    overlay = Image.new("RGBA", (w, band_h), (0, 0, 0, SUB_BG_ALPHA))
    frame_pil.paste(overlay, (0, band_y), overlay)

    # Texto
    draw = ImageDraw.Draw(frame_pil)
    for i, line in enumerate(lines):
        y = band_y + SUB_PADDING_Y + i * SUB_LINE_HEIGHT
        # Sombra
        draw.text(
            (SUB_PADDING_X + SUB_SHADOW_OFFSET, y + SUB_SHADOW_OFFSET),
            line,
            font=font,
            fill=SUB_SHADOW_COLOR,
        )
        # Texto blanco
        draw.text((SUB_PADDING_X, y), line, font=font, fill=SUB_COLOR)

    # Volver a BGR
    return np.array(frame_pil.convert("RGB"))[:, :, ::-1]

# ---------------------------------------------------------------------------
# Construcción del timeline de imágenes a partir de script_dict
# ---------------------------------------------------------------------------

def build_image_timeline(script_dict: dict, fps: int) -> list:
    """
    Devuelve una lista de tuplas (start_frame, end_frame, PIL.Image | None).
    Si una sección tiene múltiples imágenes en 'image_paths', se reparte
    la duración equitativamente entre ellas para que roten en pantalla.
    """
    timeline = []
    cursor = 0

    for section in script_dict.get("sections", []):
        duration = section.get("audio_duration", 0.0)
        sec_frames = max(1, int(round(duration * fps)))

        # Recoger lista de imágenes (nuevo campo) o imagen única (retro-compatibilidad)
        paths = section.get("images_paths") or (
            [section["image_path"]] if section.get("image_path") else []
        )

        if not paths:
            timeline.append((cursor, cursor + sec_frames, None))
            print(f"[timeline] {section['type']:12s} → {sec_frames} frames | sin imagen")
        else:
            # Repartir frames entre las imágenes disponibles
            frames_per_img = sec_frames // len(paths)
            remainder = sec_frames % len(paths)

            for i, path in enumerate(paths):
                img = None
                try:
                    img = Image.open(path).convert("RGB")
                except Exception as e:
                    print(f"[timeline] No se pudo cargar {path}: {e}")

                # El último tramo se lleva el resto de frames
                chunk = frames_per_img + (remainder if i == len(paths) - 1 else 0)
                timeline.append((cursor, cursor + chunk, img))
                cursor += chunk

            print(f"[timeline] {section['type']:12s} → {sec_frames} frames | "
                  f"{len(paths)} imágenes × ~{frames_per_img}f")
            continue  # cursor ya avanzado dentro del bucle

        cursor += sec_frames

    return timeline


def get_current_image(timeline: list, frame_idx: int):
    """Devuelve la imagen PIL correspondiente al frame actual, o None."""
    for start, end, img in timeline:
        if start <= frame_idx < end:
            return img
    return None


# ---------------------------------------------------------------------------
# Renderizado Principal
# ---------------------------------------------------------------------------

def render(
        audio: Path = AUDIO,
        base: Path = BASE,
        expresiones: Path = EXPRESIONES,
        output: Path = OUTPUT,
        script_dict: dict = None,
) -> Path:
    try:
        import cv2
    except ImportError:
        print("[error] Instala opencv: pip install opencv-python")
        sys.exit(1)

    output.parent.mkdir(parents=True, exist_ok=True)
    body, eyes, mouths = cargar_sprites(base, expresiones)
    rms = analizar_audio(audio, FPS)
    n_frames = len(rms)
    ojo_seq = generar_secuencia_ojos(n_frames, FPS)

    # Construir timeline de imágenes si hay script_dict
    img_timeline = []
    sub_timeline = []
    font = None

    if script_dict:
        img_timeline = build_image_timeline(script_dict, FPS)
        sub_timeline = build_subtitle_timeline(script_dict, FPS)
        font = _cargar_fuente(SUB_FONT_SIZE)
        print(f"[subtítulos] Fuente cargada a {SUB_FONT_SIZE}px — {len(sub_timeline)} secciones")

        total_timeline_frames = img_timeline[-1][1] if img_timeline else 0
        if abs(total_timeline_frames - n_frames) > FPS * 2:
            print(
                f"[render] ⚠ Desfase: audio={n_frames}f "
                f"vs timeline={total_timeline_frames}f "
                f"({abs(total_timeline_frames - n_frames) / FPS:.1f}s). "
                "Comprueba que las duraciones de audio por sección son correctas."
            )

    temp = output.parent / "_presenter_raw.mp4"
    writer = cv2.VideoWriter(str(temp), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (VIDEO_W, VIDEO_H))

    print(f"\n[render] Generando {n_frames} frames ({n_frames / FPS:.1f}s)...")
    for i in range(n_frames):
        news_img = get_current_image(img_timeline, i) if img_timeline else None

        # Frame base (BGR)
        frame = componer_frame(body, eyes[ojo_seq[i]], mouths[rms_to_mouth(rms[i])], (VIDEO_W, VIDEO_H), news_img)

        # Subtítulos encima del frame
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
    """
    Pipeline completo de producción de vídeo:
      1. Renderiza frames con overlay de imágenes  →  vídeo mudo temporal
      2. Muxea vídeo + audio con ffmpeg            →  output final con audio
    Devuelve True si fue bien, False si ffmpeg falló.
    """
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
            "-i", str(temp),
            "-i", str(audio),
            "-c:v", "libx264", "-c:a", "aac", "-shortest",
            str(output),
        ],
        capture_output=True,
    )

    temp.unlink(missing_ok=True)

    if result.returncode != 0:
        print(f"[producir] ffmpeg falló:\n{result.stderr.decode()}")
        return False

    print(f"[producir] Episodio exportado: {output}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Renderizador optimizado de presentador Pixel-Art")
    parser.add_argument("--audio", type=Path, default=AUDIO)
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--expresiones", type=Path, default=EXPRESIONES)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--ffmpeg", type=Path, default=ROOT / "ffmpeg.exe")
    parser.add_argument("--script", type=Path, default=None,
                        help="Ruta al script_dict.json generado por main.py (opcional, activa overlays)")
    args = parser.parse_args()

    for p in (args.audio, args.base, args.expresiones):
        if not p.exists():
            print(f"[error] No se encuentra el archivo crítico: {p}")
            sys.exit(1)

    # Cargar script_dict si se proporcionó
    script_dict = None
    if args.script and args.script.exists():
        import json
        with open(args.script, encoding="utf-8") as f:
            script_dict = json.load(f)
        print(f"[main] script_dict cargado: {len(script_dict.get('sections', []))} secciones")
    elif args.script:
        print(f"[main] ⚠ No se encontró {args.script}, renderizando sin imágenes.")

    ok = producir(
        script_dict=script_dict,
        output=args.output,
        audio=args.audio,
        base=args.base,
        expresiones=args.expresiones,
        ffmpeg=args.ffmpeg,
    )
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()