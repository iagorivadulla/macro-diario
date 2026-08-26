import ollama
import json
from pathlib import Path
from pydantic import BaseModel, Field
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
from omnivoice import OmniVoice
import torch
import soundfile as sf

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

CONTEXT_DIR = Path(__file__).parent.parent / "context"

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
    link: str
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

class EpisodeSEO(BaseModel):
    main_news_id: int
    primary_keyword: str
    secondary_keywords: list[str]
    title: str
    description: str
    hashtags: list[str]


class ShortSEO(BaseModel):
    news_id: int
    primary_keyword: str
    secondary_keywords: list[str]
    title: str
    description: str
    hashtags: list[str]


class SEOFullMetadata(BaseModel):
    episode: EpisodeSEO
    shorts: list[ShortSEO] = Field(default_factory=list)

# ---------------------------------------------------------------------------
# Base agent
# ---------------------------------------------------------------------------

def run_agent(system: str, prompt: str, model: str, schema: BaseModel = None, temperature: float = 0.7, num_ctx: int = 6144) -> dict:
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        "options": {"temperature": temperature, "num_ctx": num_ctx},
        "keep_alive": True,
        "think": False,

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
'''
filter_model = "qwen2.5:7b-instruct-q4_K_M"
resume_model = "gemma2:9b-instruct-q4_K_M"
control_model = "llama3.1:8b-instruct-q4_K_M"
script_model = "gemma2:9b-instruct-q4_K_M"
script_control_model = "llama3.1:8b-instruct-q4_K_M"
image_model = "qwen2.5:7b-instruct-q4_K_M"
vision_model = "llava:7b"
'''
filter_model = "qwen3:8b"
resume_model = "qwen3:8b"
control_model = "qwen3:8b"
script_model = "qwen3:8b"
script_control_model = "qwen3:8b"
headline_model = "qwen3:8b"
headline_control_model = "qwen3:8b"
image_model = "qwen3:8b"
vision_model = "qwen3-vl:8b"
seo_model = "qwen3:8b"

filter_temperature = 0.0
resume_temperature = 0.2
control_temperature = 0.0
script_temperature = 0.5
script_control_temperature = 0.1
headline_model_temperature = 0.2
headline_control_model_temperature = 0.0
image_temperature = 0.6
vision_temperature = 0.0
seo_temperature = 0.3

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
        f"y elige EXACTAMENTE 7 noticias:\n\n{headlines}\n\n"
        "Para cada noticia seleccionada, indica:\n"
        "- 'id': El número entero entre corchetes.\n"
        "- 'headline': El texto exacto del titular.\n"
        "- 'reason': El criterio (prioridad 1, 2 o 3) que justifica su inclusión.\n"
        "Descarta duplicados según el criterio de exclusión definido."
    )

    result = run_agent(system, prompt, model, FilteredIndex, temperature=filter_temperature, num_ctx=6144)

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
        "/no_think\n"
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
            i['resume'] = run_agent(system, prompt, model, num_ctx= 4608, temperature=resume_temperature)

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
            i['resume'] = run_agent(system, prompt, model=model, temperature=resume_temperature)
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

        if article and not resume:
            i['accepted'] = False
            i['control_reason'] = "El resumen llegó vacío (posible fallo del modelo)."
            continue

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
            result = run_agent(system, prompt, model, QualityCheck, num_ctx= 4096, temperature=control_temperature)
            i['accepted'] = result.accepted
            i['control_reason'] = result.reason

    accepted: list = [i for i in news if i.get('accepted') is True]
    denied: list = [i for i in news if i.get('accepted') is False]

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
        "Eres el guionista principal de 'Macro Diario', un informativo diario sobre economía, mercados, empresas, tecnología e inteligencia artificial.\n\n"

        "Tu misión NO es resumir noticias.\n"
        "Tu misión es conseguir que el espectador quiera ver el episodio completo.\n\n"

        "Escribes para ser leído en voz alta por un presentador.\n"
        "Cada frase debe sonar natural, clara y dinámica.\n"
        "Escribe como un periodista profesional adaptado a YouTube, no como un periódico ni como una IA.\n\n"

        "Cada bloque debe responder de forma natural a estas preguntas:\n"
        "- ¿Qué ha ocurrido?\n"
        "- ¿Por qué importa?\n"
        "- ¿Qué consecuencias puede tener?\n"
        "- ¿Qué debería vigilar el espectador?\n\n"

        "Prioriza siempre la claridad antes que el lenguaje técnico.\n"
        "Cuando aparezcan cifras, explica por qué son relevantes.\n"
        "Cada frase debe aportar información nueva.\n"
        "Evita repeticiones.\n"
        "Evita frases vacías.\n\n"

        "PROHIBIDO inventar cualquier dato, nombre, cargo, empresa o contexto.\n"
        "Solo puedes utilizar la información proporcionada en los resúmenes.\n\n"

        "No escribas listas.\n"
        "No escribas encabezados.\n"
        "No escribas etiquetas.\n"
        "Devuelve únicamente el texto solicitado.\n\n"

        f"{context}"
    )

    headlines = "\n".join(f"- {i['title']}" for i in news)

    script_estructura = {"sections": []}

    # --- 1. INTRO ---
    intro_prompt = (
        f"Escribe la apertura del episodio de hoy.\n\n"

        f"La fecha de hoy es exactamente: {fecha_exacta}.\n"
        "Comienza mencionando esa fecha de forma completamente natural.\n\n"

        "Después presenta únicamente los dos o tres temas más importantes del día como titulares breves que despierten curiosidad.\n"
        "No desarrolles todavía ninguna noticia.\n"
        "No reveles cifras.\n"
        "No adelantes conclusiones.\n\n"

        "Incluye exactamente esta frase:\n"
        "'Bienvenidos a Macro Diario.'\n\n"

        "Finaliza con una única frase que conecte de forma natural con la primera noticia.\n\n"

        "Objetivo: conseguir que el espectador quiera seguir escuchando.\n\n"

        f"Noticias disponibles:\n{headlines}"
    )
    intro_text = run_agent(system, intro_prompt, model, temperature=0)

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
        link = item.get("link", "")

        next_title = news[idx + 1]["title"] if idx + 1 < len(news) else None
        next_resume = news[idx + 1].get("resume", "") if idx + 1 < len(news) else None

        block_prompt = (
            f"Escribe el bloque correspondiente a esta noticia.\n\n"

            f"Titular:\n{title}\n\n"

            f"Resumen:\n{resume}\n\n"

            "Empieza directamente por el hecho más importante.\n"
            "Después explica por qué esta noticia importa realmente.\n"
            "Si afecta a empresas, gobiernos, mercados o ciudadanos, explícalo de forma sencilla.\n"
            "Cuando aparezcan cifras, intégralas de forma natural explicando su significado.\n"
            "Termina indicando qué debería vigilar el espectador durante los próximos días.\n\n"

            "Debe sonar como un periodista que habla directamente al espectador.\n"
            "No repitas literalmente el titular.\n"
            "No inventes contexto.\n"
            "No añadas información externa.\n"
            "No utilices frases como:\n"
            "'Ahora hablamos de...'\n"
            "'En otra noticia...'\n"
            "'Pasamos a...'\n\n"

            "Todos los números deben escribirse con palabras.\n"
            "Longitud aproximada: entre noventa y ciento cuarenta palabras."
        )

        short_prompt = (
            "Escribe el guion de un YouTube Short basado exclusivamente en la noticia proporcionada.\n\n"


        f"Titular:\n{title}\n\n"
        f"Resumen:\n{resume}\n\n"

        "IMPORTANTE: Este texto NO debe ser una versión resumida ni una copia del bloque principal del noticiero. "
        "Debe estar escrito desde cero y tener una estructura, ritmo y enfoque propios de un YouTube Short.\n\n"

        "OBJETIVO:\n"
        "Captar la atención durante los primeros segundos y conseguir que el espectador quiera seguir viendo el vídeo hasta el final.\n\n"

        "ESTRUCTURA:\n"
        "1. HOOK INICIAL: Empieza con una frase muy potente que genere curiosidad, sorpresa, tensión o interés inmediato. "
        "No empieces diciendo simplemente el titular ni con fórmulas como 'Hoy...', 'Esta noticia...' o 'En esta noticia...'. "
        "El espectador debe sentir desde la primera frase que está a punto de descubrir algo importante.\n\n"

        "2. DESARROLLO: Explica rápidamente qué ha ocurrido utilizando únicamente la información del resumen. "
        "Prioriza los datos y hechos más interesantes. Mantén frases cortas, dinámicas y fáciles de escuchar.\n\n"

        "3. IMPORTANCIA: Explica por qué este hecho merece atención. "
        "Si existen consecuencias mencionadas explícitamente en el resumen, intégralas de forma clara. "
        "No inventes consecuencias ni contexto adicional.\n\n"

        "4. CIERRE: Termina dejando una última idea que refuerce la importancia de la noticia o despierte curiosidad, "
        "sin inventar información ni utilizar preguntas cuya respuesta no esté en el material proporcionado.\n\n"

        "5. CTA FINAL: Termina exactamente con una frase equivalente a: "
        "'Esto fue Macro Diario Shorts. El vídeo completo está en el canal de YouTube.' "
        "Puedes adaptar ligeramente la redacción para que suene natural al ser narrada, "
        "pero debe mencionar obligatoriamente 'Macro Diario Shorts' y que el vídeo completo está en el canal de YouTube.\n\n"

        "REGLAS:\n"
        "- CERO ALUCINACIONES. Utiliza exclusivamente la información proporcionada en el titular y resumen.\n"
        "- No añadas nombres, cifras, empresas, cargos, fechas o consecuencias que no aparezcan en el material.\n"
        "- No copies frases del guion principal.\n"
        "- No repitas literalmente el titular como primera frase.\n"
        "- No escribas encabezados ni etiquetas como 'HOOK', 'DESARROLLO' o 'CIERRE'.\n"
        "- No escribas listas.\n"
        "- Todos los números deben escribirse con palabras.\n"
        "- El texto debe sonar natural al ser leído por un presentador.\n"
        "- Utiliza un ritmo más rápido y directo que el noticiero completo.\n"
        "- Evita introducciones genéricas.\n"
        "- Evita frases vacías como 'vamos a hablar de', 'quédate hasta el final' o 'no te lo vas a creer'.\n"
        "- El hook debe estar relacionado directamente con el hecho real de la noticia.\n"
        "- No exageres ni utilices clickbait que contradiga la información disponible.\n\n"

        "LONGITUD:\n"
        "Entre setenta y ciento diez palabras aproximadamente, incluyendo la llamada a la acción final.\n\n"

        "Devuelve únicamente el texto final que será leído en voz alta."
        )


        block_text = run_agent(system, block_prompt, model, temperature=script_temperature)
        short_text = run_agent(system, short_prompt, model, temperature=script_temperature)

        script_estructura["sections"].append({
            "type": f"news_{idx + 1}",
            "title": title,
            "link": link,
            "text": block_text,
            "short_text": short_text,
            "resume": resume,
            "images_paths": item.get("images_paths"),
        })

        if next_title:
            transition_prompt = (
                "DEVUELVE EXACTAMENTE UNA FRASE"
                f"Escribe una única frase que conecte de forma natural la noticia titulada:\n"
                f"'{title}'\n"
                f"con la siguiente noticia:\n"
                f"'{next_title}'.\n\n"

                "Debe sonar como una conversación natural.\n"
                "No repitas información.\n"
                "No adelantes detalles.\n"
                "Debe despertar curiosidad.\n"
                "Máximo veinte palabras."
                
                "NO PUEDE CONTENER:"
                "-cifras"
                "-explicaciones"
                "-consecuencias"
                "-contexto"
                
                "Tu unica función es enlazar el bloque anterior con el siguiente."
                "Es preferible separar las secciones con una ráfaga gráfica/sonora breve y una entradilla directa "
                "(Pasando a resultados industriales...) en lugar de intentar forzar una relación causal que no existe entre dos empresas o sectores distintos."
                "Mas adelante corto por codigo a 18 palabras"
            )

            transition_text = run_agent(system, transition_prompt, model, temperature=script_temperature)

            words = transition_text.split()
            if len(words) > 18:
                transition_text = " ".join(words[:18]).rstrip(",;:") + "."

            script_estructura["sections"].append({
                "type": f"transition_{idx + 1}",
                "title": f"Transición {idx + 1}",
                "text": transition_text,
                "images_paths": [],
            })

    # --- 3. OUTRO ---
    outro_prompt = (
        "Escribe el cierre del episodio.\n\n"

        "No repitas ninguna noticia.\n"
        "Despide el programa de forma natural.\n"
        "Invita al espectador a volver mañana para conocer las noticias económicas más importantes del día.\n"
        "Mantén un tono cercano y profesional.\n"
        "Máximo cuatro líneas."
    )
    outro_text = run_agent(system, outro_prompt, model, temperature=script_temperature)

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

def script_control_3(script_dict: dict) -> dict:
    # ------------------------------------------------------------------
    # Prompt base
    # ------------------------------------------------------------------

    BASE_SYSTEM = """
    Eres el editor de continuidad de Macro Diario.

    NO eres el guionista.

    NO debes mejorar el estilo.

    NO debes reescribir frases porque escribirías diferente.

    Tu única misión es detectar incumplimientos de las reglas y corregirlos.

    Si el texto ya cumple las reglas, devuélvelo EXACTAMENTE igual.

    Devuelve únicamente el texto final.
    """

    # ------------------------------------------------------------------
    # Función genérica
    # ------------------------------------------------------------------

    def review(text: str, summary: str = "", rules: str = "", model=None):
        prompt = f"""
    Resumen original:

    {summary}

    Texto:

    {text}

    REGLAS:

    {rules}

    Si el texto ya cumple todas las reglas:

    DEVUÉLVELO EXACTAMENTE IGUAL.

    No cambies estilo.

    No cambies tono.

    No cambies ritmo.

    No reescribas frases simplemente porque prefieras otra forma de escribir.
    """

        result = run_agent(BASE_SYSTEM, prompt, model, CorrectedSection)

        return result.text.strip()

    # ------------------------------------------------------------------
    # Intro
    # ------------------------------------------------------------------

    def review_intro(text, today, model):

        rules = f"""
    La introducción debe:

    - durar poco
    - no explicar noticias
    - no contener spoilers
    - solo presentar titulares
    - decir al acabar "Bienvenidos a Macro Diario."
    
    La fecha correcta es:

    {today}
    """

        return review(text=text,
                      rules=rules,
                      model=model)

    # ------------------------------------------------------------------
    # Noticias
    # ------------------------------------------------------------------

    def review_news(text, resume, model):

        rules = """
    Comprueba únicamente:

    - datos inventados
    - contradicciones con el resumen
    - inglés (debe estar en castellano)
    - errores gramaticales

    NO cambies absolutamente nada más.
    """

        return review(
            text=text,
            summary=resume,
            rules=rules,
            model=model
        )

    # ------------------------------------------------------------------
    # Transiciones
    # ------------------------------------------------------------------

    def review_transition(text, next_news, model):

        rules = f"""
    Una transición:

    - máximo 18 palabras
    - una única frase
    - ESTA EN CASTELLANO
    - no explica la siguiente noticia
    - no contiene cifras
    - no contiene porcentajes
    - no contiene fechas
    - no contiene nombres propios nuevos
    - no resume la noticia siguiente
    - no debe incluir frases como:
        "la siguiente noticia"
        "deberías vigilar"
        "la clave está"

    La noticia siguiente es:

    {next_news}

    Si incumple alguna regla:

    reescríbela completamente.

    Si ya es correcta:

    devuélvela igual.
    """

        return review(
            text=text,
            rules=rules,
            model=model
        )

    # ------------------------------------------------------------------
    # Outro
    # ------------------------------------------------------------------

    def review_outro(text, model):

        rules = """
    El cierre:

    - debe ser corto
    - no volver a resumir todas las noticias
    - no repetir el contenido del vídeo
    """

        return review(
            text=text,
            rules=rules,
            model=model
        )

    # ------------------------------------------------------------------
    # Agente principal
    # ------------------------------------------------------------------

    def script_control_(script_dict: dict):

        print("Running Script Control v3...")

        model = script_control_model

        dias = [
            "Lunes",
            "Martes",
            "Miércoles",
            "Jueves",
            "Viernes",
            "Sábado",
            "Domingo"
        ]

        meses = [
            "enero",
            "febrero",
            "marzo",
            "abril",
            "mayo",
            "junio",
            "julio",
            "agosto",
            "septiembre",
            "octubre",
            "noviembre",
            "diciembre"
        ]

        hoy = datetime.now()

        fecha = f"{dias[hoy.weekday()]} {hoy.day} de {meses[hoy.month - 1]} de {hoy.year}"

        sections = script_dict["sections"]

        for i, section in enumerate(sections):

            print(f"Reviewing {section['type']}")

            try:

                if section["type"] == "intro":

                    section["text"] = review_intro(
                        section["text"],
                        fecha,
                        model
                    )

                elif section["type"].startswith("news"):

                    section["text"] = review_news(
                        section["text"],
                        section.get("resume", ""),
                        model
                    )

                    section['short_text'] = review_news(
                        section["short_text"],
                        section.get("resume", ""),
                        model
                    )

                elif section["type"].startswith("transition"):

                    next_news = ""

                    if i + 1 < len(sections):

                        nxt = sections[i + 1]

                        if nxt["type"].startswith("news"):
                            next_news = nxt["text"]

                    section["text"] = review_transition(
                        section["text"],
                        next_news,
                        model
                    )

                elif section["type"] == "outro":

                    section["text"] = review_outro(
                        section["text"],
                        model
                    )

            except Exception as e:

                print(
                    f"Error revisando {section['type']}: {e}"
                )

        return script_dict


    return script_control_(script_dict)

# --------------------------------------------------------------------------
# Headline Agent
# --------------------------------------------------------------------------

def headline_agent(script_dict: dict) -> dict:
    '''
    writes the headlines and de sublines
    for the production wich will show like 5 secs
    for every new
    '''

    model = headline_model

    system = """Eres el redactor editorial de MACRO DIARIO, un medio de noticias económicas y financieras.

    Tu función es redactar textos breves para gráficos informativos que aparecen en pantalla durante un vídeo.

    Debes seguir estrictamente las instrucciones específicas de cada tarea.

    El contenido debe ser:
    - Claro y fácil de entender a primera vista.
    - Informativo y periodístico.
    - Directo y natural.
    - Basado únicamente en la información proporcionada.
    - En español.
    - Centrado en el hecho más importante de la noticia.

    Nunca inventes datos, cifras, declaraciones, causas o consecuencias.
    No utilices clickbait ni exageraciones.
    Devuelve únicamente el texto solicitado, sin explicaciones ni comillas.
    """

    for i in script_dict['sections']:
        if i['type'].startswith("news_"):
            print("Making headline for " + i['type'])
            new = i.get("resume", "")

            prompt_headline = f"""Crea el HEADLINE que aparecerá en pantalla durante los primeros 5 segundos de esta noticia.

                                NOTICIA:
                                {new}

                                Reglas:

                                REGLAS:
                                - Máximo 4 palabras.
                                - Debe ser un titular periodístico, no una oración explicativa.
                                - Debe comunicar inmediatamente el acontecimiento principal.
                                - Prioriza sujeto + acción cuando sea posible.
                                - Utiliza palabras concretas y con fuerza informativa.
                                - Incluye nombres propios, empresas, países o cifras cuando sean relevantes.
                                - Evita titulares genéricos o vagos.
                                - No repitas información innecesaria.
                                - No uses clickbait ni exageraciones.
                                - No inventes información.
                                - No termines con un punto.
                                - Devuelve únicamente el headline, sin comillas ni explicaciones.
                                """

            i["headline"] = run_agent(system, prompt_headline, model, temperature=headline_model_temperature, num_ctx=4096)
            headline = i["headline"]
            print(headline)

            prompt_subhead = f"""Crea el SUBHEADLINE que acompañará al headline de esta noticia.

                                    HEADLINE:
                                    {headline}

                                    NOTICIA:
                                    {new}

                                    REGLAS:
                                    - Máximo 10 palabras.
                                    - Una sola frase.
                                    - Debe aportar información nueva respecto al headline.
                                    - No debe repetir las mismas palabras del headline.
                                    - No repetir nombre de la empresa o activo, darle continuidad al headline.
                                    - Aporta el dato, cifra, contexto, lugar, empresa, motivo o consecuencia más relevante.
                                    - Si existe una cifra especialmente relevante, priorízala.
                                    - Debe poder entenderse rápidamente al leerlo en pantalla.
                                    - Lenguaje periodístico, natural y directo.
                                    - No hagas preguntas.
                                    - No uses clickbait ni exageraciones.
                                    - No inventes información.
                                    - No termines con un punto.
                                    
                                    Devuelve únicamente el subheadline.
                                    """
            print("Subheadline for " + i['type'])
            i["subhead"] = run_agent(system, prompt_subhead, model, temperature=headline_model_temperature, num_ctx=4096)
            print(i["subhead"])
    return script_dict

# -------------------------------------------------------------------------
# Images
# -------------------------------------------------------------------------

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

    ASSETS_DIR    = Path(__file__).parent.parent / "assets" / "news_images"
    TARGET        = 5     # imágenes por sección
    MAX_PER_QUERY = 13      # URLs que se prueban por cada query
    N_QUERIES     = 9     # queries generadas por sección
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
                "/no_think\n"
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
                options={"temperature": 0.0, "num_predict": 300},
            )
            print(f"[llava] RAW: {resp}")
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

def image_agent_v9(script_dict: dict, headless: bool = True) -> dict:
    """
    Para cada sección de noticia, visita la URL original (section['link'])
    y captura una imagen del logo del medio, el titular y la foto de portada.
    """
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    ASSETS_DIR = Path(__file__).parent.parent / "assets" / "news_images"
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    VIEWPORT_W = 1280
    VIEWPORT_H = 1600
    PADDING_TOP = 12
    PADDING_BOTTOM = 40
    PADDING_SIDES = 16       # margen lateral alrededor del contenido real
    MAX_CROP_HEIGHT = 1100
    CONSENT_HOSTS = ("consent.", "guce.", "consent-page")
    ACCEPT_TEXTS = ["aceptar todo", "aceptar", "accept all", "agree", "entendido", "de acuerdo", "i agree"]
    BOT_PHRASES = [
        "verify you are human", "are you a robot", "please verify you are human",
        "checking your browser", "access denied", "attention required",
        "unusual traffic", "enable javascript and cookies",
    ]

    def _crear_driver():
        options = uc.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(f"--window-size={VIEWPORT_W},{VIEWPORT_H}")
        driver = uc.Chrome(options=options, version_main=152)
        driver.set_page_load_timeout(25)
        return driver

    def _click_por_texto(driver) -> bool:
        try:
            for b in driver.find_elements(By.TAG_NAME, "button"):
                txt = (b.text or "").strip().lower()
                if txt and any(p in txt for p in ACCEPT_TEXTS):
                    b.click()
                    sleep(0.8)
                    return True
        except Exception:
            pass
        return False

    def _aceptar_consentimiento(driver) -> bool:
        known_selectors = [
            "#onetrust-accept-btn-handler",
            "button[name='agree']",
            "#consent-page button[type='submit']",
            "button[aria-label*='Accept']",
            "button[aria-label*='Aceptar']",
        ]
        for sel in known_selectors:
            try:
                btn = WebDriverWait(driver, 1.5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                btn.click()
                sleep(0.8)
                return True
            except Exception:
                continue
        if _click_por_texto(driver):
            return True
        try:
            for frame in driver.find_elements(By.TAG_NAME, "iframe"):
                try:
                    driver.switch_to.frame(frame)
                    if _click_por_texto(driver):
                        driver.switch_to.default_content()
                        return True
                    driver.switch_to.default_content()
                except Exception:
                    driver.switch_to.default_content()
        except Exception:
            pass
        return False

    def _salir_de_consentimiento(driver, s_type: str) -> bool:
        if not any(h in driver.current_url for h in CONSENT_HOSTS):
            return True
        for intento in range(2):
            _aceptar_consentimiento(driver)
            try:
                WebDriverWait(driver, 8).until(
                    lambda d: not any(h in d.current_url for h in CONSENT_HOSTS)
                )
                return True
            except Exception:
                print(f"  [{s_type}] ⚠ intento {intento + 1}/2 aceptando consentimiento sin éxito...")
                continue
        print(f"  [{s_type}] ✗ atascado en consentimiento tras 2 intentos: {driver.current_url[:70]}")
        return False

    def _es_pagina_antibot(driver) -> bool:
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
            return any(p in body_text for p in BOT_PHRASES)
        except Exception:
            return False

    def _esperar_resolucion_antibot(driver, s_type: str, intentos: int = 3, espera: float = 3.0) -> bool:
        """
        Muchos retos anti-bot (Cloudflare, IBD...) se resuelven solos vía JS
        tras unos segundos. Reintenta la comprobación varias veces antes de
        descartar la sección, en vez de descartar al primer vistazo.
        Devuelve True si la página deja de ser un muro anti-bot.
        """
        for intento in range(intentos):
            if not _es_pagina_antibot(driver):
                return True
            print(f"  [{s_type}] ⏳ posible verificación anti-bot, esperando... ({intento + 1}/{intentos})")
            sleep(espera)
        return not _es_pagina_antibot(driver)

    # ------------------------------------------------------------------
    # ESTRATEGIA 1 — Elemento real de Yahoo Finance (.cover-wrap)
    # ------------------------------------------------------------------
    def _recorte_por_cover_wrap(driver):
        js = """
        function unionRect(els) {
            let top = Infinity, bottom = -Infinity, left = Infinity, right = -Infinity;
            for (const el of els) {
                const r = el.getBoundingClientRect();
                if (r.width === 0 && r.height === 0) continue;
                top = Math.min(top, r.top);
                bottom = Math.max(bottom, r.bottom);
                left = Math.min(left, r.left);
                right = Math.max(right, r.right);
            }
            return top === Infinity ? null : {top, bottom, left, right};
        }

        let covers = Array.from(document.querySelectorAll('.cover-wrap')).slice(0, 2);
        if (covers.length === 0) return null;

        if (covers.length === 1) {
            let videoEl = document.querySelector(
                '[data-testid="article-video-player"], [class*="video-player"], [class*="cover-video"]'
            );
            if (videoEl) covers.push(videoEl);
        }

        return unionRect(covers);
        """
        try:
            return driver.execute_script(js)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # ESTRATEGIA 2 — Fallback genérico (h1 + primera imagen grande)
    # ------------------------------------------------------------------
    def _recorte_generico(driver):
        js = """
        function esAnuncio(el) {
            let node = el;
            for (let i = 0; i < 6 && node; i++) {
                const cls = (node.className || '').toString().toLowerCase();
                const id = (node.id || '').toLowerCase();
                const testId = (node.getAttribute && node.getAttribute('data-testid') || '').toLowerCase();
                const blob = cls + ' ' + id + ' ' + testId;
                if (/(^|[-_ ])(ad|ads|advert|sponsor|promo)([-_ ]|$)/.test(blob)) return true;
                node = node.parentElement;
            }
            return false;
        }

        let h1 = document.querySelector('h1');
        if (!h1) return null;
        let h1Rect = h1.getBoundingClientRect();

        let bestTop = null, bestDist = Infinity, bestLeft = h1Rect.left;
        let candidates = Array.from(document.querySelectorAll('img, span, div, a, p'));
        for (const el of candidates) {
            if (el === h1 || el.contains(h1)) continue;
            const r = el.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) continue;
            const gap = h1Rect.top - r.bottom;
            if (gap < 0 || gap > 200) continue;
            if (Math.abs(r.left - h1Rect.left) > 80) continue;

            const isLogoImg = el.tagName === 'IMG' && r.height <= 60 && r.height >= 10;
            const text = (el.innerText || '').trim();
            const isKickerText = text.length > 0 && text.length <= 40 &&
                                  text === text.toUpperCase() && el.children.length === 0;

            if ((isLogoImg || isKickerText) && gap < bestDist) {
                bestDist = gap;
                bestTop = r.top;
                bestLeft = Math.min(bestLeft, r.left);
            }
        }
        let topY = bestTop !== null ? bestTop : h1Rect.top;

        let ogMeta = document.querySelector('meta[property="og:image"]');
        let ogUrl = ogMeta ? ogMeta.content : null;
        let ogHash = ogUrl ? ogUrl.split('/').pop().split('?')[0].split('.')[0] : null;

        let imgs = Array.from(document.querySelectorAll('img'))
            .filter(i => i.naturalWidth >= 300 && i.naturalHeight >= 200)
            .filter(i => !esAnuncio(i));

        let heroImg = null;
        if (ogHash) heroImg = imgs.find(i => i.src && i.src.includes(ogHash)) || null;
        if (!heroImg && imgs.length) heroImg = imgs[0];

        let heroRect = heroImg ? heroImg.getBoundingClientRect() : null;
        let bottomY = Math.max(h1Rect.bottom, heroRect ? heroRect.bottom : 0);
        let left = Math.min(bestLeft, h1Rect.left, heroRect ? heroRect.left : h1Rect.left);
        let right = Math.max(h1Rect.right, heroRect ? heroRect.right : h1Rect.right);

        return {top: topY, bottom: bottomY, left, right};
        """
        try:
            return driver.execute_script(js)
        except Exception:
            return None

    def _localizar_recorte(driver) -> tuple:
        res = _recorte_por_cover_wrap(driver)
        origen = "cover-wrap"
        if not res:
            res = _recorte_generico(driver)
            origen = "genérico"
        if not res:
            return 0, 0, VIEWPORT_W, MAX_CROP_HEIGHT, "sin-detección"

        left = max(0, int(res.get("left", 0)) - PADDING_SIDES)
        right = int(res.get("right", VIEWPORT_W)) + PADDING_SIDES
        top = max(0, int(res.get("top", 0)) - PADDING_TOP)
        bottom = int(res.get("bottom", 0)) + PADDING_BOTTOM

        width = max(1, right - left)
        height = bottom - top
        if height <= 0:
            height = MAX_CROP_HEIGHT
        height = min(height, MAX_CROP_HEIGHT)

        return left, top, width, height, origen

    def _capturar_region(driver, x: int, y: int, width: int, height: int, dest_path: str):
        result = driver.execute_cdp_cmd("Page.captureScreenshot", {
            "format": "png",
            "clip": {"x": x, "y": y, "width": width, "height": height, "scale": 1},
            "captureBeyondViewport": True,
        })
        with open(dest_path, "wb") as f:
            f.write(base64.b64decode(result["data"]))

    news_sections = [s for s in script_dict.get("sections", []) if s["type"].startswith("news_")]
    print(f"[image_agent_v9] {len(news_sections)} secciones con enlace")

    driver = _crear_driver()

    try:
        for section in news_sections:
            link = section.get("link")
            s_type = section["type"]
            section.setdefault("images_paths", [])

            if not link:
                print(f"  [{s_type}] sin link, se omite")
                continue

            try:
                driver.get(link)
                sleep(2.5)  # antes 1.5s

                if not _salir_de_consentimiento(driver, s_type):
                    continue

                try:
                    WebDriverWait(driver, 10).until(  # antes 6s
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".cover-wrap, h1"))
                    )
                except Exception:
                    print(f"  [{s_type}] ✗ no apareció contenido reconocible en {driver.current_url[:70]}, se omite")
                    continue

                sleep(1.5)  # antes 1s

                if not _esperar_resolucion_antibot(driver, s_type):
                    print(f"  [{s_type}] ✗ bloqueado por anti-bot ({driver.current_url[:70]}), se omite")
                    continue

                driver.execute_script("window.scrollTo(0, 0);")
                sleep(0.3)

                x, y, width, height, origen = _localizar_recorte(driver)

                final_path = str(ASSETS_DIR / f"{s_type}.png")
                _capturar_region(driver, x, y, width, height, final_path)

                section["images_paths"] = [final_path]
                print(f"  [{s_type}] ✓ captura guardada ({width}x{height}, x={x}, y={y}, método={origen}) → {final_path}")

            except Exception as e:
                print(f"  [{s_type}] ✗ fallo al capturar '{link[:60]}': {e}")

    finally:
        try:
            driver.quit()
        except Exception:
            pass

    found = sum(1 for s in news_sections if s.get("images_paths"))
    print(f"[image_agent_v9] Completado — {found}/{len(news_sections)} capturas")

    return script_dict

# ---------------------------------------------------------------------------
# Voice
# ---------------------------------------------------------------------------


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

def _prepare_for_tts(text: str) -> str:
    import re

    # eliminar dobles espacios
    text = re.sub(r"\s+", " ", text)

    # separar mejor los dos puntos
    text = text.replace(": ", ": ... ")

    # punto y coma = pausa media
    text = text.replace("; ", "; ... ")

    # guiones largos
    text = text.replace(" — ", " ... ")

    # paréntesis
    text = text.replace("(", ", ")
    text = text.replace(")", ", ")

    # tres puntos
    text = text.replace("...", "…")

    return text.strip()


def broadcaster(
        script_dict: dict,
        output_path: str = None,
        chunk_pause: float = 0.2,
        section_pause: float = 1.0,
) -> str:
    import numpy as _np
    from pathlib import Path
    from omnivoice import OmniVoice
    import torch

    try:
        import soundfile as _sf
    except ImportError:
        raise ImportError("Ejecuta: pip install soundfile")

    # ─────────────────────────────────────────────────────────────────────────

    model = OmniVoice.from_pretrained(
        "k2-fsa/OmniVoice",
        device_map="cuda:0",
        dtype=torch.float16,
        load_asr=False
    )

    def generate_omnivoice(text):

        from omnivoice import VoiceClonePrompt

        VOICE_PROMPT = VoiceClonePrompt.load(
            r"C:\Users\usuario\Desktop\Python\Macro News\assets\audio\omnivoice_voice.pt")

        samples = model.generate(
            text=text,
            language="es",
            voice_clone_prompt=VOICE_PROMPT,
            normalize_text=True
        )

        return samples[0], model.sampling_rate

    # ─────────────────────────────────────────────────────────────────────────

    FFMPEG = r"C:\Users\usuario\Desktop\Python\Macro News\assets\audio\ffmpeg.exe"

    if output_path is None:
        output_path = r"C:\Users\usuario\Desktop\Python\Macro News\assets\audio\output.wav"

    sections = script_dict.get("sections", [])
    print(f"[Broadcaster] Sintetizando {len(sections)} secciones")

    all_samples: list = []
    sample_rate: int | None = None

    for idx_sec, section in enumerate(sections):
        sec_type = section.get("type", "body")

        text = section["text"]
        chunks = _split_sentences(text)
        sec_samples: list = []

        for idx, chunk in enumerate(chunks, 1):
            samples, rate = generate_omnivoice(chunk)
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
        duration_s = float(len(section_audio) / sample_rate) if sample_rate else 0.0
        section["audio_duration"] = duration_s
        all_samples.append(section_audio)
        print(f"  {'':12s} → {duration_s:.1f}s  ✓")

    combined = _np.concatenate(all_samples)
    out = Path(output_path)
    _sf.write(str(out), combined, sample_rate)

    # Audio más tipo podcast
    processed_out = out.with_name(out.stem + "_processed.wav")

    '''subprocess.run([
        str(FFMPEG), "-y", "-i", str(out),
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
    ], check=True)'''

    subprocess.run([
        str(FFMPEG), "-y", "-i", str(out),
        "-af",
        "highpass=f=80,"
        "acompressor=threshold=-16dB:ratio=1.5:attack=25:release=300:makeup=1,"
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
    print(f"[Broadcaster] ✓ Audio total: {total:.1f}s  →  {out}")

    return "\n\n".join(s["text"] for s in sections)


# ---------------------------------------------------------------------------
# SEO Agent
# ---------------------------------------------------------------------------

try:
    locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")
except:
    pass

def seo_agent_v2(script_dict: dict):
    '''
    Genera toda la metadata SEO del episodio y de todos los Shorts
    '''

    full_seo_data = {}

    print("Generando metadata SEO...")

    meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct",
             "nov", "dic"]

    hoy = datetime.now()

    date = f"{hoy.day}/{meses[hoy.month - 1]}/{hoy.year}"

    news = []

    for section in script_dict.get("sections", []):

        if not section["type"].startswith("news_"):
            continue

        news.append({
            "news_id": int(section["type"].split("_")[1]),
            "title": section["title"],
            "summary": section.get("resume", ""),})
    #-------------------------------------------------------------
    # System Prompt
    #-------------------------------------------------------------

    system = """
        Eres un estratega senior de SEO en YouTube especializado en canales de finanzas, tecnología y macroeconomía.

        TU OBJETIVO:
        Maximizar el CTR (Click-Through Rate), el posicionamiento en búsquedas (SEO) y la tasa de descubrimiento por recomendación de algoritmo, manteniendo 100% de rigor informativo y honestidad periodística.

        REGLAS DE ORO DE SEO Y CTR:
        1. IDIOMA: Todo el contenido debe generarse estrictamente en CASTELLANO.
        2. KEYWORDS PRIMARIAS: Deben colocarse lo más a la IZQUIERDA posible en títulos y descripciones (los usuarios y algoritmos leen de izquierda a derecha).
        3. FRACTURA DE PATRÓN (HOOKS): Usa palabras de impacto y verbos de acción en títulos de Shorts ('Dispara', 'Caída', 'Clave', 'Alerta', 'Récord').
        4. SIN CARACTERES PROHIBIDOS: No uses emojis ni comillas. Usa números en lugar de palabras ($500B en lugar de 500 mil millones) para optimizar espacio y legibilidad.
        5. CERO ENGAÑOS: Sé provocativo y atractivo, pero NUNCA inventes o exageres datos que no estén en la noticia.
        """

    #----------------------------------------------------------------------------
    # Long Video Metadata
    #----------------------------------------------------------------------------

    print('Analizando video largo...')

    long_video_prompt = f"""
        Analiza TODAS las noticias del episodio para generar la metadata del VIDEO LARGO.

        FECHA: {date}
        NOTICIAS: {news}

        ==================================================
        INSTRUCCIONES DE METADATA
        ==================================================

        1. NOTICIA PROTAGONISTA (main_news_id):
           Selecciona la noticia con mayor impacto en bolsas, divisas o decisión de inversión.

        2. PRIMARY KEYWORD:
           Término exacto con alto volumen de búsqueda en Google/YouTube. Ejemplo: "Caída de Nvidia", "Precio del Petróleo", "Acciones de SpaceX".

        3. TÍTULO (MAX 90 CARACTERES):
           - Debe comenzar exactamente con: Macro Diario | {date}:
           - La keyword principal y la entidad relevante deben ir inmediatamente después del prefijo.
           - Debe plantear una consecuencia o evento clave para el inversor.
           - El total del título no debe ser superior a 90 caracteres contando los espacios.

        4. DESCRIPCIÓN (OPTIMIZADA PARA KEY MOMENTS Y SEO):
           Redacta la descripción estructurada en este orden exacto:
           - Línea 1-2 (Hook SEO): Resume la noticia principal respondiendo a la búsqueda del usuario e incluyendo la keyword principal.
           - Resumen del Programa: Presenta las noticias secundarias en párrafos fluidos utilizando términos semánticos (ej: Wall Street, Fed, tasa de interés, acciones, mercado).
           - Impacto Económico: Breve frase que explique cómo afecta esto al bolsillo/cartera del inversor.
           - CTA: "Suscríbete a Macro Diario para recibir el análisis diario de mercados."

        5. HASHTAGS (Entre 6 y 10):
           Combina: Entidades clave (#Nvidia, #SpaceX) + Sectores (#InteligenciaArtificial, #Petroleo) + Macro (#Mercados, #Bolsa, #Inversion).

        DEVUELVE JSON CON ESTA ESTRUCTURA:
        {{
            "main_news_id": 0,
            "primary_keyword": "",
            "secondary_keywords": [],
            "title": "",
            "description": "",
            "hashtags": []
        }}
        """

    long_video = run_agent(system=system, prompt=long_video_prompt, model= seo_model, schema=EpisodeSEO ,temperature=seo_temperature)
    full_seo_data['episode'] = long_video.model_dump()

    #-----------------------------------------------------------------------------------
    # Now for each short youtube and tik tok at same time
    #-----------------------------------------------------------------------------------

    print('Analizando shorts...')

    shorts_data = []

    for i in news:
        short_prompt = f"""
                Genera la metadata de YOUTUBE SHORTS para esta noticia:
                ID: {i["news_id"]} | TÍTULO: {i["title"]} | RESUMEN: {i["summary"]}

                REGLAS DE TÍTULO SHORTS (MAX 90 CARACTERES):
                - Debe comenzar exactamente con: Macro Diario |
                - Debe contener la entidad + evento clave + cifra impactante si existe.
                - Usa estructuras de alto CTR como: "¿Qué pasa con...?", "...se dispara tras...", "Alerta en...".
                - Ejemplo: Macro Diario | SpaceX se desploma tras su IPO: ¿Qué hacer?

                DESCRIPCIÓN SHORTS:
                - Explicación de 2 o 3 frases directas. Usa palabras clave como 'inversión', 'mercado' o el ticker de la empresa.
                - Cierra con: "Mira el análisis completo en el canal de Macro Diario."

                HASHTAGS (4 a 6):
                - Solo hashtags directamente relacionados con la entidad, el sector y el mercado.

                DEVUELVE JSON:
                {{
                    "news_id": {i["news_id"]},
                    "primary_keyword": "",
                    "secondary_keywords": [],
                    "title": "",
                    "description": "",
                    "hashtags": []
                }}
                """

        short_video = run_agent(system=system, prompt=short_prompt, model=seo_model, schema=ShortSEO, temperature=seo_temperature)
        shorts_data.append(short_video.model_dump())


    full_seo_data['shorts'] = shorts_data

    return full_seo_data



