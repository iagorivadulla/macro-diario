import ollama
import json
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional
import os
import asyncio
import nest_asyncio
from datetime import datetime
from supertonic import TTS
from rapidfuzz import fuzz
from time import sleep
import random
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import base64
from PIL import Image
import io
import re
import subprocess
import warnings

# ----------------------------------
# Handel Warnings
# ----------------------------------------

warnings.filterwarnings("ignore")
nest_asyncio.apply()
#------UC __DEL__ HANDLE---------
_uc_del_original = uc.Chrome.__del__

def _uc_del_safe(self):
    try:
        _uc_del_original(self)
    except Exception:
        pass

uc.Chrome.__del__ = _uc_del_safe

# ---------------------------------------------------------------------------
# Context loader
# ---------------------------------------------------------------------------

CONTEXT_DIR = Path(__file__).parent / "context"

def load_context(*filenames: str) -> str:
    """
    Loads one or more .md files from the context/ directory and returns
    their contents concatenated with a separator, ready to be injected
    into a system prompt.

    Usage:
        load_context("editorial.md", "style.md")
    """
    parts = []
    for name in filenames:
        path = CONTEXT_DIR / name
        if not path.exists():
            raise FileNotFoundError(f"Context file not found: {path}")
        parts.append(path.read_text(encoding="utf-8"))
    return "\n\n---\n\n".join(parts)

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class SelectedItem(BaseModel):
    id: int
    headline: str
    reason: str

class FilteredIndex(BaseModel):
    selected: List[SelectedItem]

class QualityCheck(BaseModel):
    accepted: bool
    reason: str

class CorrectedSection(BaseModel):
    text: str

class ImageQueriesList(BaseModel):
    queries: List[str]


# ---------------------------------------------------------------------------
# Base agent
# ---------------------------------------------------------------------------

def run_agent(system: str, prompt: str, model: str, schema: BaseModel = None, temperature: float = 0.7,) -> dict:
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        "options": {"temperature": temperature},
    }
    if schema:
        kwargs["format"] = schema.model_json_schema()

    response = ollama.chat(**kwargs)
    content = response.message.content

    if schema:
        return schema.model_validate_json(content)
    return content

# ---------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------model
filter_model = "qwen2.5:7b-instruct-q4_K_M"
resume_model = "gemma2:9b-instruct-q4_K_M"
control_model = "llama3.1:8b-instruct-q4_K_M"
script_model = "gemma2:9b-instruct-q4_K_M"
script_control_model = "llama3.1:8b-instruct-q4_K_M"
image_model = "qwen2.5:7b-instruct-q4_K_M"
vision_model = "llava:7b"

# ---------------------------------------------------------------------------
# Filter Agent
# ---------------------------------------------------------------------------

def filter_agent(news: list) -> list:
    def deduplicate_news(news_list, threshold=75):
        '''
        clean the duplicated news
        '''
        unique_news = []
        for item in news_list:
            is_duplicate = False
            for unique_item in unique_news:
                # Compara la similitud de los titulares
                if fuzz.token_set_ratio(item['title'], unique_item['title']) > threshold:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_news.append(item)
        return unique_news

    news = deduplicate_news(news)

    # 1. Numeramos los titulares para que el modelo tenga una referencia numérica exacta
    headlines = "\n".join(
        f"[{i}] {item['title']}" for i, item in enumerate(news)
    )

    model = filter_model
    print(f'Reading the news, {len(news)} items')

    context = load_context("filter_criteria.md")

    system = (
        "Eres un editor senior de noticias económicas. "
        "Sigues un criterio de selección estricto y documentado. "
        "Ante el mismo conjunto de titulares, siempre tomas la misma decisión. "
        "Respondes únicamente en JSON estricto.\n\n"
        f"{context}"
    )

    prompt = (
        f"Aplica los criterios de selección a esta lista de titulares "
        f"y elige EXACTAMENTE 10 noticias:\n\n{headlines}\n\n"
        "Para cada noticia seleccionada, indica:\n"
        "- 'id': El número entero entre corchetes.\n"
        "- 'headline': El texto exacto del titular.\n"
        "- 'reason': El criterio (prioridad 1, 2 o 3) que justifica su inclusión.\n"
        "Descarta duplicados según el criterio de exclusión definido."
    )

    result = run_agent(system, prompt, model, FilteredIndex, temperature=0)

    news_return = []
    seen_ids = set()

    # 2. Extraemos las noticias usando el ID numérico para asegurar precisión total
    for selected in result.selected:
        idx = selected.id

        # Validamos que el ID exista en nuestra lista y no esté repetido
        if 0 <= idx < len(news) and idx not in seen_ids:
            item = news[idx].copy()
            item["reason"] = selected.reason

            # (Opcional) Si en el futuro necesitas validar qué devolvió exactamente el LLM:
            # item["llm_headline"] = selected.headline

            news_return.append(item)
            seen_ids.add(idx)

    return news_return


# ---------------------------------------------------------------------------
# Resume Agent
# ---------------------------------------------------------------------------

def resume_agent(news: list) -> list:
    model = resume_model
    # Se recomienda cargar el contexto una vez fuera del loop si es pesado
    context = load_context("standards.md", "style.md")

    system = (
        "Eres un analista macroeconómico senior. "
        "Tu tarea es resumir artículos financieros de forma concisa y estructurada. "
        "Respondes SIEMPRE en español, en un único párrafo de texto plano, absolutamente SIN markdown (ni negritas, ni asteriscos).\n\n"
        f"{context}"
    )

    print(f'Summarizing news, {len(news)} items')

    for i in news:
        title = i['title']
        # TRUNCAMIENTO UNIFICADO: Aseguramos que el resumidor lea lo mismo que el controlador
        raw_article = i.get('article', '')
        article = raw_article[:4000] if raw_article else ''

        control_reason = i.get('control_reason')
        last_resume = i.get('resume')
        accepted = i.get('accepted')

        if article and not control_reason:
            prompt = (
                f"Titular: {title}\n\n"
                f"Artículo:\n{article}\n\n"
                "Redacta un resumen en un solo párrafo (entre 3 y 4 oraciones). "
                "Debes responder en este orden exacto: "
                "1) qué ocurrió (con cifras concretas), "
                "2) por qué importa (qué cambia, quién se afecta), "
                "3) qué hay que vigilar a futuro. "
                "Texto plano estricto. Cero markdown, cero viñetas."
            )
            i['resume'] = run_agent(system, prompt, model)

        if article and accepted == False:
            prompt = (
                f"Titular: {title}\n\n"
                f"Artículo original:\n{article}\n\n"
                f"Tu resumen anterior:\n{last_resume}\n\n"
                f"Motivo exacto del rechazo:\n{control_reason}\n\n"
                "Tu resumen no pasó el control de calidad por el motivo indicado arriba. "
                "Corrige ÚNICAMENTE el problema señalado y mantén el formato de "
                "un solo párrafo de 3-4 oraciones en texto plano, sin markdown. "
                "Asegúrate de incluir: qué ocurrió, por qué importa y qué vigilar."
            )
            i['resume'] = run_agent(system, prompt, model=model)
            i['control_reason'] = None
            i['accepted'] = None

    return news


# ---------------------------------------------------------------------------
# Control Agent
# ---------------------------------------------------------------------------

def control_agent(news: list) -> list:
    model = control_model
    print('Quality control in progress...')

    context = load_context("standards.md")

    system = (
        "Eres un auditor de calidad implacable pero justo para Macro Diario. "
        "Tu trabajo es validar si el resumen cumple con las reglas mínimas. "
        "NO evalúas estilo literario. "
        "Respondes ÚNICAMENTE en JSON con los campos 'accepted' (booleano) y 'reason' (string).\n\n"
        f"{context}"
    )

    for i in news:
        title = i['title']
        raw_article = i.get('article', '')
        # Leemos exactamente los mismos caracteres que el resumidor
        article = raw_article[:4000] if raw_article else ''
        resume = i.get('resume')

        if article and resume:
            prompt = (
                f"Titular: {title}\n\n"
                f"Artículo original:\n{article}\n\n"
                f"Resumen generado:\n{resume}\n\n"
                "Verifica EXCLUSIVAMENTE estos 3 puntos (si cumple los 3, aprueba):\n"
                "1. Factualidad: Las cifras y datos mencionados en el resumen existen en el artículo original. No hay predicciones inventadas.\n"
                "2. Formato: Es un solo párrafo, no usa markdown (no hay ** ni # ni -), y está en español.\n"
                "3. Estructura: Menciona qué ocurrió, por qué importa y qué vigilar.\n\n"
                "Si apruebas, reason debe ser null o vacío. "
                "Si rechazas, escribe en 'reason' UNA instrucción directa de cómo solucionarlo (ej: 'Quita los asteriscos de negrita' o 'El dato del 5% no aparece en el texto')."
            )
            result = run_agent(system, prompt, model, QualityCheck)
            i['accepted'] = result.accepted
            i['control_reason'] = result.reason

    accepted = [i for i in news if i.get('accepted') is True]
    denied = [i for i in news if i.get('accepted') is False]

    return accepted, denied

# ---------------------------------------------------------------------------
# Script Agent
# ---------------------------------------------------------------------------

def script_agent_2(news: list) -> dict:
    model = script_model
    print('Writing the structured script...')

    context = load_context("editorial.md", "style.md", "structure.md")

    redaction_rules = """
        REGLAS PERIODÍSTICAS Y DE FORMATO INQUEBRANTABLES:
        1. PROHIBIDO INCLUIR ETIQUETAS: Escribe un texto fluido para ser leído en voz alta. NUNCA incluyas las palabras de mis instrucciones en tu respuesta final (por ejemplo, está ESTRICTAMENTE PROHIBIDO escribir "ENTRADA DIRECTA AL HECHO:", "Contextualiza:", "Cierra con:", etc.).
        2. CERO ALUCINACIONES: Eres un periodista riguroso. NO inventes absolutamente nada. Si el resumen no menciona el nombre de un equipo (como Real Madrid), no lo añadas. Si no menciona un cargo político exacto o una imputación legal, NO LA INVENTES. Cíñete al 100% al texto base.
        3. LONGITUD MÍNIMA: Tu respuesta no puede ser solo el titular. Debes redactar un párrafo completo, natural y explicativo de al menos 40 palabras.
        """

    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
             "noviembre", "diciembre"]

    hoy = datetime.now()
    fecha_exacta = f"{dias[hoy.weekday()]} {hoy.day} de {meses[hoy.month - 1]} de {hoy.year}"

    system = (
        "Eres guionista de 'Macro Diario', un podcast financiero diario en español. "
        "Devuelves SOLO el texto del guión del bloque solicitado, sin comentarios, sin meta-texto.\n\n"
        f"{context}"
        f"{redaction_rules}"
    )

    headlines = "\n".join(f"- {i['title']}" for i in news)

    script_estructura = {"sections": []}

    # --- 1. INTRO ---
    intro_prompt = (
        f"Escribe la APERTURA del episodio de hoy siguiendo EXACTAMENTE la estructura "
        f"de cuatro elementos definida en structure.md.\n\n"
        f"La fecha de hoy es EXACTAMENTE: {fecha_exacta}. Comienza el texto diciendo esta fecha.\n\n"
        "REGLA PERIODÍSTICA CRÍTICA: Basa tu texto ÚNICA Y EXCLUSIVAMENTE en la información de las noticias proporcionadas. "
        "PROHIBIDO inventar o deducir cargos políticos (no asumas quién es presidente, ministro o CEO si no lo especifica el texto). "
        "PROHIBIDO añadir contexto histórico o datos que no estén explícitamente en los resúmenes.\n\n"
        f"Noticias del día:\n{headlines}\n\n"
        "Orden obligatorio:\n"
        "[1] Primera frase con la fecha del día integrada de forma natural.\n"
        "[2] 2 o 3 cabeceras: los temas más importantes. Una línea por tema, como titulares de portada.\n"
        "[3] Exactamente esta frase y ninguna más: 'Bienvenidos a Macro Diario.'\n"
        "[4] Una sola frase de transición que lleve directo al primer bloque.\n\n"
        "REGLA DE ORO PROHIBIDA: NO debes desarrollar las noticias, NO des datos numéricos, cifras ni desveles el desenlace en esta apertura. El oyente solo debe escuchar los titulares.\n"
        "Duración objetivo: ~100 palabras."
    )
    intro_text = run_agent(system, intro_prompt, model)

    script_estructura["sections"].append({
        "type": "intro",
        "title": "Apertura",
        "text": intro_text,
        "images_paths": []
    })

    # --- 2. BLOQUES DE NOTICIAS ---
    for idx, item in enumerate(news):
        title = item["title"]
        resume = item.get("resume", "")

        next_title = news[idx + 1]["title"] if idx + 1 < len(news) else None
        next_resume = news[idx + 1].get("resume", "") if idx + 1 < len(news) else None

        block_prompt = (
            f"Escribe el BLOQUE de noticia para:\n\n"
            f"Titular: {title}\n"
            f"Resumen: {resume}\n\n"
            "Sigue la estructura interna definida en structure.md:\n"
            "- Entra directo al hecho con datos concretos (sin 'Ahora hablamos de...').\n"
            "- Contextualiza: qué cambia esto, quién gana, quién pierde.\n"
            "- Cierra con qué hay que vigilar: un dato, evento o reacción concreta.\n"
            "Los números se escriben fonéticamente (ej: 'veinte mil', 'dos punto ocho por ciento'). "
        )
        block_text = run_agent(system, block_prompt, model)

        script_estructura["sections"].append({
            "type": f"news_{idx + 1}",
            "title": title,
            "text": block_text,
            "resume": resume,
            "images_paths": item.get("images_paths"),
        })

        if next_title:
            transition_prompt = (
                f"Escribe UNA sola frase de transición causal o temática "
                f"desde '{title}' hacia '{next_title}'. "
                f"Contexto del siguiente bloque: {next_resume[:300]}\n"
                "PROHIBIDO: Repetir datos de la noticia anterior o adelantar cifras o detalles de la siguiente noticia. Debe ser un simple puente corto.\n"
                "No más de 200 caracteres."
            )

            transition_text = run_agent(system, transition_prompt, model)

            script_estructura["sections"].append({
                "type": f"transition_{idx + 1}",
                "title": f"Transición {idx + 1}",
                "text": transition_text,
                "images_paths": [],
            })

    # --- 3. OUTRO ---
    outro_prompt = (
        f"Escribe el CIERRE del episodio siguiendo la estructura definida.\n\n"
        f"Temas cubiertos hoy:\n{headlines}\n\n"
        "Máximo 4 líneas. Agradece a los espectadores y despide Macro Diario."
    )
    outro_text = run_agent(system, outro_prompt, model)

    script_estructura["sections"].append({
        "type": "outro",
        "title": "Cierre",
        "text": outro_text,
        "images_paths": []
    })

    return script_estructura

# ---------------------------------------------------------------------------
# Script Control Agent
# ---------------------------------------------------------------------------

def script_control_2(news: list, script_dict: dict) -> dict:
    model = script_control_model
    print('Revising the structured script and enforcing limits...')

    redaction_rules = """
    REGLAS PERIODÍSTICAS Y DE FORMATO INQUEBRANTABLES:
    1. PROHIBIDO INCLUIR ETIQUETAS: Escribe un texto fluido para ser leído en voz alta. NUNCA incluyas las palabras de mis instrucciones en tu respuesta final (por ejemplo, está ESTRICTAMENTE PROHIBIDO escribir "ENTRADA DIRECTA AL HECHO:", "Contextualiza:", "Cierra con:", etc.).
    2. CERO ALUCINACIONES: Eres un periodista riguroso. NO inventes absolutamente nada. Si el resumen no menciona el nombre de un equipo (como Real Madrid), no lo añadas. Si no menciona un cargo político exacto o una imputación legal, NO LA INVENTES. Cíñete al 100% al texto base.
    3. LONGITUD MÍNIMA: Tu respuesta no puede ser solo el titular. Debes redactar un párrafo completo, natural y explicativo de al menos 40 palabras.
    """

    context = load_context("editorial.md", "style.md", "structure.md")
    system = (
        "Eres un estricto revisor de guiones de 'Macro Diario', un podcast financiero diario en español. "
        "Tu trabajo es corregir el guión para que cumpla con los resúmenes originales "
        "y limpiar el texto de desbordamientos de información (spoilers).\n"
        "Devuelves SOLO el texto del guión corregido en formato JSON estricto.\n\n"
        f"{context}"
        f"{redaction_rules}"
    )

    sections = script_dict["sections"]

    # Revisamos el texto de cada sección de manera aislada
    for i, section in enumerate(sections):

        # Filtros específicos según el tipo de bloque
        specific_rules = ""
        if section['type'] == 'intro':
            specific_rules = "- Si la apertura desarrolla noticias, da cifras o resume los eventos a fondo, CÓRTALA. Solo debe presentar los titulares por encima.\n"
        elif "transition" in section['type']:

            next_new = ''
            if i + 1 < len(sections):
                next_section = sections[i + 1]
                if next_section['type'].startswith('news_'):
                    next_new = next_section.get('text', '')

            specific_rules = ("- Si la transición explica la noticia siguiente o incluye números, REDÚCELA a una sola frase puente. No puede contener datos duros.\n"
                              f"- La siguiente noticia es {next_new}")
        elif section['type'] == 'outro':
            specific_rules = "- Si el cierre se hace muy largo, acortalo, no debe volver a hablarse de cada noticia ni de todo el cuerpo."

        resume = section.get('resume', '')

        prompt = (
            f"Resúmen de referencia:\n\n{resume}\n\n"
            f"Texto de la sección ({section['type']}) a revisar:\n\n{section['text']}\n\n"
            "Corrige ÚNICAMENTE:\n"
            f"{specific_rules}"
            "- Datos, cifras o hechos que no coincidan con los resúmenes.\n"
            "- Afirmaciones inventadas que no aparezcan en ningún resumen.\n"
            "- Frases prohibidas según style.md.\n"
            "- Números en formato numérico en vez de fonético (ej: '20.000' → 'veinte mil', '$5' -> 'cinco dólares').\n"
            "- Elimina cualquier fragmento en inglés o Spanglish.\n"
            "- Elimina cualquier meta-texto o nombre de variable como 'transition_1:'.\n"
            "Si el texto es correcto, devuélvelo exactamente igual sin añadir comentarios extra."
        )

        try:
            # Usamos el esquema Pydantic para forzar salida estructurada limpia
            result = run_agent(system, prompt, model, CorrectedSection)
            section["text"] = result.text.strip()
        except Exception as e:
            print(f"  [!] Falló la corrección de la sección {section['type']}: {e}")
            # Si el modelo alucina y rompe el JSON, conservamos el texto original
            pass

    return script_dict

# -------------------------------------------------------------------------
# Images
# -------------------------------------------------------------------------

def image_agent_v7(script_dict: dict) -> dict:
    def validate_image_with_llava(image_path: str, query: str) -> bool:
        try:
            with Image.open(image_path) as img:
                img.load()
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.thumbnail((800, 800))
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=80)
                image_bytes = buffer.getvalue()

            # PROMPT REESCRITO: Verificación estricta del sujeto principal
            prompt = (
                f"You are a photo editor. Target: '{query}'. "
                f"Is this image an acceptable news photo for the topic '{query}'? "
                f"Be reasonable: if the photo depicts the correct person, the correct place, or the correct object (even if it's a bit blurry or has background elements), answer YES. "
                f"Reject ONLY if it is completely the wrong subject, a meme, or an irrelevant landscape. "
                f"Answer EXACTLY with one word: YES or NO."
            )

            response = ollama.generate(
                model=vision_model,
                prompt=prompt,
                images=[image_bytes],
                options={
                    'temperature': 0.1,
                    'num_predict': 5
                }
            )

            result_text = response.get('response', '').strip().upper()
            print(f"  [DEBUG] Llava opinó: {result_text}")
            return 'YES' in result_text

        except Exception as e:
            print(f"  [!] Error procesando la imagen o conectando: {e}")
            return False

    def image_agent(script_dict: dict) -> dict:

        def search_queries(script_dict: dict) -> dict:
            N = 15
            model = image_model
            print('Searching images')

            # 1. PROMPT A PRUEBA DE BALAS: Enseñamos con ejemplos físicos
            system = f"""You are a visual search specialist for a financial news video program.
        Your task: generate EXACTLY {N} Bing Images search queries that return REAL PHOTOGRAPHS of physical things.

        CRITICAL RULE: You must translate abstract financial concepts into PHYSICAL, TANGIBLE objects, people, or places.
        - Instead of "inflation rate", use "supermarket checkout groceries" or "euro bills closeup".
        - Instead of "policy change", use "Bank of Japan headquarters building" or "Kazuo Ueda governor".
        - Instead of "bond market volatility", use "Tokyo stock exchange trading floor".

        HARD RULES:
        1. Output ONLY valid JSON: {{"queries": ["q1", "q2", ...]}}
        2. Queries must be 2-5 words.
        3. ABSOLUTELY NO NUMBERS, YEARS OR PERCENTAGES (Never use 2026, 3.2%, etc.).
        4. NO ABSTRACT WORDS: Do not use graph, chart, inflation, policy, rate, market, finance, volatility, meeting.
        5. ONLY specify physical entities: specific buildings, named people, concrete objects, or specific street locations.
        """

            for section in script_dict['sections']:
                if section['type'].startswith('news_'):
                    title = section.get('title', '')
                    text = section.get('text', '')

                    section['images_paths'] = []

                    prompt = (
                        f"News title: {title}\n\n"
                        f"News text:\n{text[:800]}\n\n"
                        f"Generate exactly {N} diverse Bing image search queries of PHYSICAL things.\n"
                        f'Return JSON: {{"queries": ["...", "...", ...]}}'
                    )

                    try:
                        result = run_agent(system, prompt, model, ImageQueriesList, temperature=0.3)
                        raw_queries = result.queries[:N]
                    except Exception as e:
                        print(f"  [!] Query generation failed: {e}")
                        raw_queries = [title[:50]]

                    cleaned, seen = [], set()

                    # 2. FILTRO PYTHON INCLEMENTE
                    forbidden_words = ['graph', 'chart', 'rate', 'inflation', 'policy', 'meeting', 'finance',
                                       'volatility', 'data', 'economy', 'subtle', 'market']

                    for q in raw_queries:
                        q = q.strip().replace('_', ' ')
                        q_lower = q.lower()

                        # Destruir la query si tiene números (ej. "2026", "3.2")
                        if any(char.isdigit() for char in q):
                            print(f"  [Filtro] Descartada por números: '{q}'")
                            continue

                        # Destruir la query si tiene palabras abstractas/prohibidas
                        if any(fw in q_lower for fw in forbidden_words):
                            print(f"  [Filtro] Descartada por palabra abstracta: '{q}'")
                            continue

                        if q_lower not in seen:
                            cleaned.append(q)
                            seen.add(q_lower)

                    # Si el filtro fue demasiado estricto y nos quedamos cortos, metemos unas de emergencia
                    if len(cleaned) < 5:
                        emergencies = ["Bank of Japan headquarters", "Tokyo street business people",
                                       "Japanese Yen currency notes closeup", "Tokyo Stock Exchange building",
                                       "Madrid business district"]
                        cleaned.extend([e for e in emergencies if e.lower() not in seen])

                    section['queries'] = cleaned
                    print(f"  [{section['type']}] Queries filtradas y listas: {cleaned}")

            return script_dict

        def scrape_images(script_dict: dict, headless=True) -> dict:

            USER_AGENTS = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
                "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
            ]

            for section in script_dict['sections']:
                if not section['type'].startswith('news_'):
                    continue

                section.setdefault('images_paths', [])
                headers = {"User-Agent": random.choice(USER_AGENTS)}

                options = uc.ChromeOptions()
                if headless:
                    options.add_argument("--headless=new")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")

                # Inicia el navegador
                driver = uc.Chrome(options=options, version_main=148)

                try:
                    driver.execute_cdp_cmd('Network.enable', {})
                    driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {'headers': headers})

                    downloaded = 0

                    for query in section['queries']:
                        if downloaded >= 5:
                            break  # Si ya tenemos 5 válidas, pasamos a la siguiente sección (news)

                        # Blinda la búsqueda individual por si Selenium o Bing fallan
                        try:
                            sleep(random.uniform(1.5, 3))
                            formatted_query = query.replace(' ', '%20').replace('"', '')
                            driver.get(f"https://www.bing.com/images/search?q={formatted_query}&safeSearch=Strict")
                            sleep(random.uniform(2, 4))

                            '''
                            # Evitar los carruseles de sugerencias de texto
                            carrousel = driver.find_elements(By.CLASS_NAME, 'carousel-title')
                            if carrousel and carrousel[0].text.startswith('Sugerencias '):
                                continue
                            '''

                            # Buscamos todas las imágenes válidas de la página de resultados
                            image_links = driver.find_elements(By.CSS_SELECTOR, 'a.iusc')

                            if not image_links:
                                print(f"  [!] Bing no devolvió imágenes estándar para '{query}'.")
                                continue

                            image_saved_for_this_query = False

                            # Probamos con las primeras 4 fotos resultantes de esta query
                            for img_idx in range(min(4, len(image_links))):
                                if image_saved_for_this_query:
                                    break

                                try:
                                    m_data = image_links[img_idx].get_attribute("m")
                                    if not m_data:
                                        continue

                                    img_info = json.loads(m_data)
                                    img_url = img_info.get('murl')

                                    if img_url and img_url.startswith('http'):
                                        try:
                                            response = requests.get(img_url, headers=headers, stream=True, timeout=8)
                                            content_type = response.headers.get('Content-Type', '').lower()

                                            # Verifica que el código sea 200 y el archivo realmente sea una imagen
                                            if response.status_code == 200 and 'image' in content_type:
                                                # Nombre temporal único con img_idx
                                                name = f'{section["type"]}_{downloaded}_{img_idx}_temp.jpg'
                                                path = f'assets/news_images/{name}'

                                                with open(path, 'wb') as f:
                                                    for chunk in response.iter_content(1024):
                                                        f.write(chunk)

                                                print(f'  [~] Evaluando imagen para "{query}"...')
                                                is_valid = validate_image_with_llava(path, query)

                                                if is_valid:
                                                    final_path = f'assets/news_images/{section["type"]}_{downloaded}.jpg'

                                                    try:
                                                        # Reemplaza la imagen definitiva (soluciona WinError 183)
                                                        os.replace(path, final_path)
                                                        print(f'  [+] Aprobada por Llava: {final_path}')
                                                        section['images_paths'].append(final_path)
                                                        downloaded += 1
                                                        image_saved_for_this_query = True
                                                    except Exception as replace_error:
                                                        print(
                                                            f"  [!] Error de sistema al guardar imagen definitiva: {replace_error}")
                                                        if os.path.exists(path):
                                                            os.remove(path)
                                                else:
                                                    # Limpia la imagen temporal si es rechazada
                                                    if os.path.exists(path):
                                                        os.remove(path)
                                                    print(
                                                        f'  [-] Rechazada por Llava (eliminada). Probando siguiente...')

                                        except requests.exceptions.RequestException:
                                            # Silenciamos errores HTTP (timeouts, certificados) para no saturar la consola
                                            pass

                                except Exception:
                                    # Silenciamos errores de lectura de JSON o atributos de Bing
                                    pass

                        except Exception as general_e:
                            print(
                                f"  [!] Fallo general buscando '{query}'. Saltando a la siguiente query. Error: {general_e}")
                            continue

                    if downloaded < 5:
                        print(
                            f"  [!] WARNING: Sólo se obtuvieron {downloaded}/5 imágenes válidas para {section['type']}.")

                finally:
                    try:
                        driver.quit()
                    except Exception:
                        pass

            return script_dict

        return scrape_images(search_queries(script_dict))
    return image_agent(script_dict)

def image_agent_v8(script_dict: dict) -> dict:
    import io
    import json
    import os
    import random
    import re
    import time
    import requests
    from pathlib import Path
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from PIL import Image as PILImage

    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS

    ASSETS_DIR    = Path(__file__).parent / "assets" / "news_images"
    TARGET        = 5      # imágenes por sección
    MAX_PER_QUERY = 8      # URLs que se prueban por cada query
    N_QUERIES     = 15     # queries generadas por sección
    TIMEOUT       = 10
    MIN_WIDTH     = 350
    MIN_HEIGHT    = 250
    DDG_RETRIES   = 4
    DDG_BASE_DELAY = 3.0
    MAX_ACCEPT_PER_QUERY = 1  # máximo de imágenes aceptadas de una misma query

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    ]

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _random_ua():
        return random.choice(USER_AGENTS)

    def _is_valid_image(path: str) -> bool:
        try:
            with PILImage.open(path) as img:
                img.load()
                return img.width >= MIN_WIDTH and img.height >= MIN_HEIGHT
        except Exception:
            return False

    def _llava_validate(image_path: str, query: str) -> bool:
        """Valida con llava que la imagen sea pertinente a la query.
        Fail-open: si el modelo no está disponible, acepta la imagen."""
        try:
            with PILImage.open(image_path) as img:
                img.load()
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.thumbnail((800, 800))
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=80)
                image_bytes = buf.getvalue()

            prompt = (
                f"You are a photo editor. Target: '{query}'. "
                f"Is this image an acceptable news photo for the topic '{query}'? "
                f"Be reasonable: if the photo depicts the correct person, the correct place, or the correct object (even if it's a bit blurry or has background elements), answer YES. "
                f"Reject ONLY if it is completely the wrong subject, a meme, or an irrelevant landscape. "
                f"Answer EXACTLY with one word: YES or NO."
            )
            resp = ollama.generate(
                model=vision_model,
                prompt=prompt,
                images=[image_bytes],
                options={"temperature": 0.0, "num_predict": 5},
            )
            answer = resp.get("response", "").strip().upper()
            print(f"    [llava] {answer}")
            return "YES" in answer
        except Exception as e:
            print(f"    [llava] no disponible ({e}) → aceptando imagen")
            return True  # fail-open

    def _download(url: str, dest: str, ua: str) -> bool:
        """Descarga url en dest. Devuelve True si es una imagen válida."""
        try:
            r = requests.get(
                url,
                headers={"User-Agent": ua},
                stream=True,
                timeout=TIMEOUT,
            )
            content_type = r.headers.get("Content-Type", "").lower()
            if r.status_code != 200 or "image" not in content_type:
                return False
            with open(dest, "wb") as f:
                for chunk in r.iter_content(4096):
                    f.write(chunk)
            return _is_valid_image(dest)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # FASE 1 — Generar N_QUERIES queries por sección con el LLM
    # ------------------------------------------------------------------

    def _generar_queries(section: dict) -> list:
        system = (
            "Eres un especialista en búsqueda de imágenes para vídeos de noticias financieras. "
            f"Genera exactamente {N_QUERIES} queries de búsqueda en inglés (2-6 palabras) "
            "para Bing Images que devuelvan FOTOS REALES de cosas físicas.\n\n"
            "Reglas:\n"
            "- Traduce conceptos abstractos a objetos, personas o edificios concretos.\n"
            "- Varía el ángulo: edificios, retratos, objetos, escenas de calle.\n"
            "- Sin números, años ni porcentajes.\n"
            '- Devuelve SOLO JSON válido: {"queries": ["q1", "q2", ...]}'
        )
        prompt = (
            f"Titular: {section['title']}\n\n"
            f"Texto:\n{section.get('text', '')[:800]}\n\n"
            f"Genera {N_QUERIES} queries diversas. "
            'Devuelve JSON: {"queries": ["...", ...]}'
        )
        try:
            resp = ollama.chat(
                model=image_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": prompt},
                ],
                options={"temperature": 0.4},
            )
            raw = resp.message.content
            match = re.search(r'\{.*?"queries"\s*:\s*\[.*?\]\s*\}', raw, re.DOTALL)
            if match:
                queries = json.loads(match.group()).get("queries", [])
                cleaned, seen = [], set()
                for q in queries:
                    q = q.strip()
                    # Descarta solo si hay años o porcentajes explícitos
                    if re.search(r'\b(20\d{2}|19\d{2}|\d+%)\b', q):
                        continue
                    if q.lower() not in seen and 4 <= len(q) <= 80:
                        cleaned.append(q)
                        seen.add(q.lower())
                if cleaned:
                    return cleaned
        except Exception as e:
            print(f"[image_agent] LLM falló para '{section['title'][:50]}': {e}")

        # Fallback genérico si el LLM falla
        return [
            "Wall Street New York trading floor",
            "Federal Reserve building Washington DC",
            "stock market traders screens",
            "business people office meeting",
            "oil refinery industrial plant",
        ]

    # ------------------------------------------------------------------
    # FASE 2 — Buscar URLs con DDG (con backoff exponencial)
    # ------------------------------------------------------------------

    def _ddg_urls(query: str, max_results: int) -> list:
        for attempt in range(DDG_RETRIES):
            wait = DDG_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1.5)
            print(f"[image_agent] DDG espera {wait:.1f}s (intento {attempt + 1}/{DDG_RETRIES})...")
            time.sleep(wait)
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.images(query, max_results=max_results))
                return [r.get("image", "") for r in results
                        if r.get("image", "").startswith("http")]
            except Exception as e:
                msg = str(e)
                is_ratelimit = "403" in msg or "atelimit" in msg
                if is_ratelimit and attempt < DDG_RETRIES - 1:
                    print(f"[image_agent] Rate-limit, reintentando... ({msg[:60]})")
                    continue
                print(f"[image_agent] DDG error: {msg[:80]}")
                return []
        return []

    # ------------------------------------------------------------------
    # FASE 3 — Descargar y validar imágenes para una sección
    # ------------------------------------------------------------------

    def _procesar_seccion(section: dict) -> None:
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        s_type = section["type"]
        section.setdefault("images_paths", [])

        # Reutilizar queries ya generadas en paralelo si están disponibles
        queries = section.pop("_queries_cache", None) or _generar_queries(section)
        print(f"  [{s_type}] procesando con {len(queries)} queries...")

        downloaded = 0
        ua = _random_ua()

        for qi, query in enumerate(queries):
            if downloaded >= TARGET:
                break

            print(f"  [{s_type}] q{qi + 1}/{len(queries)}: '{query}'")
            urls = _ddg_urls(query, MAX_PER_QUERY)

            if not urls:
                print(f"  [{s_type}] sin resultados → siguiente query")
                continue

            accepted_this_query = 0

            for ui, url in enumerate(urls):
                if downloaded >= TARGET:
                    break
                if accepted_this_query >= MAX_ACCEPT_PER_QUERY:
                    break

                tmp = str(ASSETS_DIR / f"{s_type}_{downloaded}_{qi}_{ui}_tmp.jpg")

                if not _download(url, tmp, ua):
                    if os.path.exists(tmp):
                        os.remove(tmp)
                    continue

                if _llava_validate(tmp, query):
                    final = str(ASSETS_DIR / f"{s_type}_{downloaded}.jpg")
                    try:
                        os.replace(tmp, final)
                        section["images_paths"].append(final)
                        downloaded += 1
                        accepted_this_query += 1
                        print(f"  [{s_type}] ✓ imagen {downloaded}/{TARGET}")
                    except Exception as e:
                        print(f"  [{s_type}] error al guardar: {e}")
                        if os.path.exists(tmp):
                            os.remove(tmp)
                else:
                    if os.path.exists(tmp):
                        os.remove(tmp)

        if downloaded < TARGET:
            print(f"  [{s_type}] ⚠ {downloaded}/{TARGET} imágenes obtenidas")
        else:
            print(f"  [{s_type}] ✓ {downloaded}/{TARGET} completadas")


    # ------------------------------------------------------------------
    # Pipeline principal
    # ------------------------------------------------------------------

    news_sections = [s for s in script_dict.get("sections", [])
                     if s["type"].startswith("news_")]
    print(f"[image_agent] {len(news_sections)} secciones a procesar")

    # Queries en paralelo: no tocan DDG, no tienen rate-limit
    print("[image_agent] Fase 1/2 — Generando queries con LLM...")
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_generar_queries, s): s for s in news_sections}
        for future in as_completed(futures):
            section = futures[future]
            try:
                section["_queries_cache"] = future.result()
                print(f"  {section['type']:12s} → {len(section['_queries_cache'])} queries")
            except Exception as e:
                section["_queries_cache"] = None
                print(f"  {section['type']:12s} → fallback (error: {e})")

    # Descargas en serie para respetar el rate-limit de DDG
    print("[image_agent] Fase 2/2 — Descargando imágenes (serie)...")
    for section in news_sections:
        _procesar_seccion(section)

    found   = sum(len(s.get("images_paths", [])) for s in news_sections)
    total   = len(news_sections) * TARGET
    missing = total - found
    print(
        f"[image_agent] Completado — {found}/{total} imágenes"
        + (f" ({missing} sin descargar)" if missing else " ✓")
    )

    return script_dict

# ---------------------------------------------------------------------------
# Voice
# ---------------------------------------------------------------------------

def broadcaster(script: str) -> str:
    tts = TTS(auto_download=True)
    style = tts.get_voice_style(voice_name="M3")
    wav, duration = tts.synthesize(
        text=script,
        voice_style=style,
        lang="es",
        speed=1.20,
        total_steps=12,
        verbose=True,
    )
    tts.save_audio(wav, "output.wav")
    print(f"Generated audio")

def broadcaster_2(script_dict: dict) -> str:
    import numpy as _np

    tts   = TTS(auto_download=True)
    style = tts.get_voice_style(voice_name="M3")

    all_wavs = []
    print(f"[TTS] Sintetizando {len(script_dict['sections'])} secciones...")

    for section in script_dict["sections"]:
        wav, duration = tts.synthesize(
            text=section["text"],
            voice_style=style,
            lang="es",
            speed=1.3,
            total_steps=30,
            verbose=False,
        )
        # supertonic devuelve duration como numpy scalar/array → forzar float Python
        duration_s = float(_np.asarray(duration).flat[0])
        section["audio_duration"] = duration_s
        all_wavs.append(wav)
        print(f"  {section['type']:12s}  {duration_s:.1f}s")

    combined = _np.concatenate([w.reshape(-1) for w in all_wavs])
    tts.save_audio(combined, "output.wav")

    total = sum(s["audio_duration"] for s in script_dict["sections"])
    print(f"[TTS] Audio total: {total:.1f}s")

    return "\n\n".join(s["text"] for s in script_dict["sections"])


def _split_sentences(text: str, max_chars: int = 180) -> list[str]:
    """
    Divide el texto en fragmentos respetando puntuación.
    Kokoro tiene un límite de ~510 fonemas por llamada; con max_chars=180
    los chunks en español quedan muy por debajo de ese límite.
    """
    import re

    def _split_by_delimiters(src: str, limit: int) -> list[str]:
        """Parte src en trozos <= limit chars usando comas/punto y coma como corte."""
        parts = re.split(r'(?<=[,;])\s+', src)
        result, current = [], ""
        for p in parts:
            if len(current) + len(p) + 1 <= limit:
                current = f"{current} {p}".strip()
            else:
                if current:
                    result.append(current)
                # Si incluso la parte sola supera el límite, corte en espacio más cercano
                while len(p) > limit:
                    cut = p.rfind(' ', 0, limit)
                    cut = cut if cut > 0 else limit
                    result.append(p[:cut].strip())
                    p = p[cut:].strip()
                current = p
        if current:
            result.append(current)
        return result

    # Separar por punto, exclamación o interrogación seguido de espacio/fin
    raw = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks, current = [], ""
    for sentence in raw:
        if len(current) + len(sentence) + 1 <= max_chars:
            current = f"{current} {sentence}".strip()
        else:
            if current:
                chunks.append(current)
            current = ""
            # Si la frase individual supera max_chars, partirla por comas/punto y coma
            if len(sentence) > max_chars:
                sub = _split_by_delimiters(sentence, max_chars)
                # El último sub-trozo se convierte en current para poder fusionarse con lo siguiente
                chunks.extend(sub[:-1])
                current = sub[-1] if sub else ""
            else:
                current = sentence
    if current:
        chunks.append(current)
    return [c for c in chunks if c.strip()]


def broadcaster_kokoro(
        script_dict: dict,
        voice={"em_alex": 0.65, "em_santa": 0.25},
        speed: float = 0.9,
        lang: str = "es",
        output_path: str = "output.wav",
        chunk_pause: float = 0.6,
        section_pause: float = 1.0,
        section_voices: dict | None = None,
) -> str:

    import numpy as _np
    from pathlib import Path

    try:
        import soundfile as _sf
    except ImportError:
        raise ImportError("Ejecuta: pip install soundfile")
    try:
        from kokoro_onnx import Kokoro
    except ImportError:
        raise ImportError("Ejecuta: pip install kokoro-onnx")

    def blend_voices(voices: dict) -> _np.ndarray:
        total = sum(voices.values())
        blended = None
        for name, weight in voices.items():
            style = kokoro.get_voice_style(name)
            weighted = style * (weight / total)
            blended = weighted if blended is None else blended + weighted
        return blended

    def make_voice(spec):
        if isinstance(spec, str):
            return spec
        if isinstance(spec, dict):
            return blend_voices(spec)
        if isinstance(spec, _np.ndarray):
            return spec
        raise ValueError(f"Spec de voz no reconocida: {spec!r}")
    # ─────────────────────────────────────────────────────────────────────────

    ROOT = Path(__file__).parent
    MODEL_URL  = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
    VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"
    model_file  = ROOT / "kokoro-v1.0.onnx"
    voices_file = ROOT / "voices-v1.0.bin"

    def _download(url, dest):
        import urllib.request
        print(f"[Kokoro] Descargando {dest.name}...")
        tmp = dest.with_suffix(".tmp")
        urllib.request.urlretrieve(url, tmp)
        tmp.rename(dest)
        print(f"[Kokoro] ✓ {dest.name} ({dest.stat().st_size / 1e6:.0f} MB)")

    if not model_file.exists():  _download(MODEL_URL,  model_file)
    if not voices_file.exists(): _download(VOICES_URL, voices_file)

    kokoro = Kokoro(str(model_file), str(voices_file))

    base_voice = make_voice(voice)   # ← blend_voices ya tiene acceso a kokoro por closure

    sections = script_dict.get("sections", [])
    print(f"[Kokoro] Sintetizando {len(sections)} secciones | speed: {speed}x | lang: {lang}")

    all_samples: list = []
    sample_rate: int | None = None

    for idx_sec, section in enumerate(sections):
        sec_type  = section.get("type", "body")
        sec_voice = make_voice(section_voices[sec_type]) if (section_voices and sec_type in section_voices) else base_voice

        text   = section["text"]
        chunks = _split_sentences(text)
        sec_samples: list = []

        for idx, chunk in enumerate(chunks, 1):
            samples, rate = kokoro.create(chunk, voice=sec_voice, speed=speed, lang=lang)
            if sample_rate is None:
                sample_rate = rate

            sec_samples.append(samples)
            if idx < len(chunks):
                # Limpiamos espacios finales por si acaso y obtenemos el último carácter
                last_char = chunk.strip()[-1] if chunk.strip() else ""

                if last_char in {'.', '!', '?', '”', '"'}:
                    # Pausa completa para fin de frase (0.6s por defecto)
                    current_pause = chunk_pause
                elif last_char in {',', ';', ':'}:
                    # Pausa mucho más corta para encadenar ideas (~0.2s)
                    current_pause = chunk_pause * 0.35
                else:
                    # Si se cortó a la fuerza por el límite de caracteres sin puntuación
                    # casi no dejamos pausa para que la voz fluya (~0.05s)
                    current_pause = 0.05

                sec_samples.append(_np.zeros(int(sample_rate * current_pause), dtype=_np.float32))
                print(
                    f"  {sec_type:12s} chunk {idx:>2}/{len(chunks)}  ({len(chunk)} chars) [Pausa: {current_pause:.2f}s]")
            else:
                print(f"  {sec_type:12s} chunk {idx:>2}/{len(chunks)}  ({len(chunk)} chars)")

        if idx_sec < len(sections) - 1 and sample_rate:
            sec_samples.append(_np.zeros(int(sample_rate * section_pause), dtype=_np.float32))

        section_audio = _np.concatenate(sec_samples) if sec_samples else _np.array([], dtype=_np.float32)
        duration_s    = float(len(section_audio) / sample_rate) if sample_rate else 0.0
        section["audio_duration"] = duration_s
        all_samples.append(section_audio)
        print(f"  {'':12s} → {duration_s:.1f}s  ✓")

    combined = _np.concatenate(all_samples)
    out = Path(output_path)
    _sf.write(str(out), combined, sample_rate)

    # Audio más tipo podcast
    processed_out = out.with_name(out.stem + "_processed.wav")

    subprocess.run([
        "ffmpeg", "-y", "-i", str(out),
        "-af",
        "highpass=f=80,"
        "acompressor=threshold=-20dB:ratio=2.5:attack=10:release=200:makeup=2,"
        "anequalizer=c0 f=500 w=200 g=-2 t=0|c0 f=3000 w=1000 g=2.5 t=0,"
        "lowpass=f=16000,"
        "loudnorm=I=-16:TP=-1.5:LRA=11,"
        "aresample=24000",
        "-acodec", "pcm_s16le",
        "-ar", "24000",
        "-ac", "1",
        str(processed_out)
    ], check=True)

    out.unlink()  # elimina el original
    processed_out.rename(out)

    total = sum(s["audio_duration"] for s in sections)
    print(f"[Kokoro] ✓ Audio total: {total:.1f}s  →  {out}")

    return "\n\n".join(s["text"] for s in sections)