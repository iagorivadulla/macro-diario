import json
from src.agents import run_agent
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent.parent
IMG_PATH_MINIATURE = ROOT / 'assets' / 'background' / 'miniature.jpg'
IMG_PATH_MINIATURE_OUT = ROOT / 'assets' / 'miniature' / 'miniature_out.jpg'
FONT = str(ROOT / "assets" / "fonts" / "PressStart2P-Regular.ttf")
SEO_PATH = ROOT / "seo_dict.json"

# --- COORDENADAS Y CONFIGURACIÓN ---
DATE_BOX = (914, 62, 715, 185)       # Recuadro blanco superior (x1, y1, x2, y2)
DATE_COLOR = (15, 32, 67)           # Azul muy oscuro
DATE_FONT_SIZE = 40

# Área central donde irán TODOS los titulares apilados
TITLE_AREA = (100, 220, 1180, 560)   # (x1, y1, x2, y2)
TITLE_COLOR = (240, 240, 240)        # Texto principal blanco/gris
STROKE_COLOR = (10, 10, 10)         # Borde negro pixel art
STROKE_WIDTH = 4


def get_date() -> str:
    meses = ["ENE", "FEB", "MAR", "ABR",
             "MAY", "JUN", "JUL", "AGO",
             "SEP", "OCT", "NOV", "DIC"]

    dt = datetime.now()

    return f"{dt.day:02d} {meses[dt.month - 1]} {dt.year}"

def miniatures_title(seo_dict: dict) -> dict:

    model = 'qwen3:8b'
    miniatures = {}

    #long video miniature
    main_new_id = seo_dict['episode']['main_news_id']
    main_new_short = None

    for short in seo_dict.get('shorts', []):
        if short.get('news_id') == main_new_id:
            main_new_short = short

    system = "Eres un publicista especialista en crear thumbnails y ganchos para miniaturas de youtube"

    prompt = f"""Crea un texto muy breve para la miniatura de YouTube de la siguiente noticia:
                    {main_new_short}
                    
                    Devuelve ÚNICAMENTE la palabra o frase corta que irá escrita sobre la imagen.
                    
                    Reglas:
                    - Sé muy corto (3 a 5 palabras máximo).
                    - Sé conciso.
                    - No seas alarmista ni amarillista.
                    - Genera curiosidad para ver el vídeo."""

    result = run_agent(system, prompt, model)

    miniatures['episode'] = result #stores result in the dict

    for short in seo_dict.get('shorts', []):
        prompt = f"""Crea un texto muy breve para la miniatura de YouTube SHORTS de la siguiente noticia:
                            {short}

                            Devuelve ÚNICAMENTE la palabra o frase corta que irá escrita sobre la imagen.

                            Reglas:
                            - Sé muy corto (3 a 5 palabras máximo).
                            - Sé conciso.
                            - No seas alarmista ni amarillista.
                            - Genera curiosidad para ver el vídeo."""

        result = run_agent(system, prompt, model)
        index = short.get('news_id')
        miniatures[f'short_{index}'] = result


        for i in miniatures:
            print(i, miniatures[i])


    return miniatures

def draw_text_centered(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
                       box: tuple, color: tuple, stroke_color=None, stroke_width=0):
    """Dibuja un texto centrado exactamente dentro de un recuadro."""
    x1, y1, x2, y2 = box
    box_width = x2 - x1
    box_height = y2 - y1

    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = x1 + (box_width - text_width) / 2
    y = y1 + (box_height - text_height) / 2 - bbox[1]

    draw.text((x, y), text, font=font, fill=color,
              stroke_fill=stroke_color, stroke_width=stroke_width)

def render_miniature():

    with open(SEO_PATH, 'r', encoding='utf-8') as f:
        seo_dict = json.load(f)

    miniatures = miniatures_title(seo_dict)

    #extract all valid texts
    titles = [v.strip().upper() for v in miniatures.values() if v]

    if not titles:
        print('Error: no miniature titles found')
        return

    date_text = get_date()

    with Image.open(IMG_PATH_MINIATURE) as img:
        img = img.convert('RGBA')
        draw = ImageDraw.Draw(img)

        #Draw the date
        date_font = ImageFont.truetype(FONT, DATE_FONT_SIZE)
        draw_text_centered(draw, date_text, date_font, DATE_BOX, DATE_COLOR)

        #Draw all titles
        x1, y1, x2, y2 = TITLE_AREA
        area_width = x2 - x1
        area_height = y2 - y1

        font_size = 55
        min_font_size = 14

        while font_size >= min_font_size:
            font = ImageFont.truetype(FONT, font_size)
            line_height = []
            max_line_width = 0

            for line in titles:
                bbox = draw.textbbox((0,0), line, font=font, stroke_width=STROKE_WIDTH)
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                if w > max_line_width:
                    max_line_width = w
                line_height.append(h)

            line_spacing = font_size * 0.4
            total_block_height = sum(line_height) + line_spacing * (len(titles) - 1)

            if max_line_width <= area_width - 20 and total_block_height <= area_height:
                break
            font_size -= 2

        font = ImageFont.truetype(FONT, font_size)
        current_y = y1 + (area_height - total_block_height) / 2

        for line in titles:
            bbox = draw.textbbox((0,0), line, font=font, stroke_width=STROKE_WIDTH)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]

            x = x1 + (area_width - w) / 2
            y = current_y - bbox[1]

            draw.text((x, y), line, font=font, fill=TITLE_COLOR,
                      stroke_fill=STROKE_COLOR, stroke_width=STROKE_WIDTH)

            current_y += h + line_spacing

        #save final image

        IMG_PATH_MINIATURE_OUT.parent.mkdir(parents=True, exist_ok=True)
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])  # Usa el canal Alfa como máscara

        background.save(IMG_PATH_MINIATURE_OUT, "JPEG", quality=95)



if __name__ == '__main__':

    render_miniature()