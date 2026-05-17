from pathlib import Path
from PIL import Image

ROOT = Path(__file__).parent

# NUEVO
EXPRESIONES = ROOT / "assets" / "presentador_no_fondo_2.png"
BASE = ROOT / "assets" / "presentador_fondo.png"

OUTPUT_TEST = ROOT / "test_cara.png"

# ===========================================================================
# AJUSTES
# ===========================================================================
EYE_CENTER = (415, 343)
MOUTH_CENTER = (415, 404)

EYE_SCALE = 0.19
MOUTH_SCALE = 0.19
# ===========================================================================

EYE_SPRITES = [
    (1624,  167, 2020,  307),
    (1624,  347, 2020,  480),
    (1624,  537, 2020,  676),
    (1624,  719, 2020,  880),
    (1624,  916, 2020, 1108),
    (1624, 1159, 2020, 1328),
]

MOUTH_SPRITES = [
    (2396,  169, 2612,  304),
    (2380,  341, 2598,  488),
    (2381,  524, 2597,  673),
    (2380,  709, 2597,  824),
    (2381,  862, 2599, 974),
    (2397, 1017, 2613, 1159),
    (2397, 1201,2611, 1339),
]

def previsualizar_rostro(indice_ojo=0, indice_boca=0):

    if not BASE.exists():
        print(f"[Error] No se encuentra la base: {BASE}")
        return

    if not EXPRESIONES.exists():
        print(f"[Error] No se encuentra el spritesheet: {EXPRESIONES}")
        return

    print("Cargando imágenes...")

    # Base del personaje
    body = Image.open(BASE).convert("RGBA")

    # Sprites de expresiones
    sheet = Image.open(EXPRESIONES).convert("RGBA")

    # OJOS
    eye_coords = EYE_SPRITES[indice_ojo]
    eye_img = sheet.crop(eye_coords)

    w_eye = int(eye_img.width * EYE_SCALE)
    h_eye = int(eye_img.height * EYE_SCALE)

    eye_img = eye_img.resize((w_eye, h_eye), Image.NEAREST)

    # BOCA
    mouth_coords = MOUTH_SPRITES[indice_boca]
    mouth_img = sheet.crop(mouth_coords)

    w_mouth = int(mouth_img.width * MOUTH_SCALE)
    h_mouth = int(mouth_img.height * MOUTH_SCALE)

    mouth_img = mouth_img.resize((w_mouth, h_mouth), Image.NEAREST)

    # PEGAR OJOS
    ex = EYE_CENTER[0] - eye_img.width // 2
    ey = EYE_CENTER[1] - eye_img.height // 2

    body.paste(eye_img, (ex, ey), eye_img)

    # PEGAR BOCA
    mx = MOUTH_CENTER[0] - mouth_img.width // 2
    my = MOUTH_CENTER[1] - mouth_img.height // 2

    body.paste(mouth_img, (mx, my), mouth_img)

    # GUARDAR
    body.save(OUTPUT_TEST)

    print(f"✓ Guardado en: {OUTPUT_TEST}")

    try:
        body.show()
    except Exception:
        pass


if __name__ == "__main__":
    previsualizar_rostro(indice_ojo=5, indice_boca=0)