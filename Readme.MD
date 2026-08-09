# Macro Diario

[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)](https://www.python.org/)
[![Ollama](https://img.shields.io/badge/Ollama-local%20LLM-black?style=flat-square)](https://ollama.com/)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2-red?style=flat-square)](https://docs.pydantic.dev/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-audio%20post-green?style=flat-square&logo=ffmpeg)](https://ffmpeg.org/)
[![Selenium](https://img.shields.io/badge/Selenium-scraping-43B02A?style=flat-square&logo=selenium)](https://www.selenium.dev/)
[![OpenCV](https://img.shields.io/badge/OpenCV-video-5C3EE8?style=flat-square&logo=opencv)](https://opencv.org/)
[![Pillow](https://img.shields.io/badge/Pillow-pixel--art-orange?style=flat-square)](https://pillow.readthedocs.io/)

Macro Diario es un sistema de producción automatizada para crear contenido financiero en formato de vídeo y short a partir de noticias reales. Reúne información de fuentes RSS, la filtra con IA local, valida calidad editorial, genera guiones, busca imágenes, sintetiza la voz y compone el material final listo para publicar.

📺 Canal actual: https://www.youtube.com/@MacroDiario

El proyecto se publica diariamente en este canal, donde se comparte el episodio generado por el pipeline y sus versiones cortas para redes sociales.

## ¿Qué hace este proyecto?

Macro Diario automatiza todo el ciclo editorial y audiovisual de un programa de noticias económicas:

- recoge titulares y enlaces desde fuentes de información financiera
- selecciona las historias más relevantes con criterios editoriales
- resume y valida cada artículo para descartar ruido o contenido débil
- escribe un guion estructurado con tono periodístico y claridad narrativa
- revisa la redacción para mantener estándares de calidad
- busca recursos visuales compatibles con cada tema
- genera voz en off local con síntesis de texto a voz
- compone el vídeo final con presentador, imágenes y audio
- prepara versiones cortas para redes sociales y metadatos SEO

---

## Visión general del flujo

```text
RSS / fuentes financieras
        ↓
Filtrado editorial con IA
        ↓
Resumen + validación de calidad
        ↓
Guion + revisión periodística
        ↓
Búsqueda de imágenes
        ↓
voz sintética
        ↓
Composición del video final + Shorts
        ↓
Metadata SEO
        ↓
Publicación
```

---

## Arquitectura del proyecto

```text
macro-diario/
├── main.py                     # orchestrator principal
├── src/
│   ├── rss.py                  # lectura de feeds / titulares
│   ├── scraper.py              # extracción de contenido de artículos
│   ├── agents.py               # agentes LLM: filtro, resumen, control, texto, imágenes y SEO
│   ├── produccion.py           # edición de audio y composición del video principal
│   ├── produccion_shorts.py    # generación de shorts
│   ├── youtube.py              # metadata / publicación
│   └── __init__.py
├── context/
│   ├── editorial.md            # identidad del programa
│   ├── filter_criteria.md      # criterios de selección
│   ├── standards.md            # estándares editoriales
│   ├── structure.md            # formato del guion
│   └── style.md                # tono y estilo de redacción
├── assets/
│   ├── audio/
│   ├── background/
│   └── ...
├── requirements.txt
├── Readme.MD
├── seo_dict.json
├── script_dict.json
└── main.py
```

---

## Stack tecnológico

| Área | Tecnología |
|---|---|
| IA local | Ollama |
| Modelos principales | qwen3:8b, qwen3-vl:8b |
| Validación estructurada | Pydantic |
| Voz sintética | Supertonic / TTS local |
| Postprocesado de audio | FFmpeg |
| Scraping web | Selenium + undetected-chromedriver |
| Procesado visual | OpenCV + Pillow |
| Publicación | flujo automatizado de salida y metadata |

---

## Cómo funciona el pipeline

### 1. Selección de noticias
El sistema consulta feeds RSS, deduplica titulares y evalúa qué historias tienen más valor para el programa.

### 2. Resumen y control editorial
Se extrae el contenido de cada artículo y se genera un resumen. Un agente comprueba si la noticia es útil, clara, relevante y adecuada para el tono del programa.

### 3. Redacción del episodio
Con las historias aprobadas, el sistema genera un guion con una estructura narrativa y una voz editorial consistente.

### 4. Búsqueda visual
Cada sección del episodio puede incorporar imágenes contextualmente adecuadas para reforzar la información.

### 5. Producción audiovisual
Se genera la narración, se mezcla con música y voz, y se compone el vídeo final con un presentador visual.

### 6. Shorts y SEO
Además del video principal, el proyecto genera versiones cortas y metadatos para optimizar la distribución en plataformas como YouTube.

---

## Requisitos previos

Antes de ejecutar el proyecto, asegúrate de tener instalado:

- Python 3.10+
- Ollama funcionando localmente
- modelos descargados en Ollama
- Chrome o Chromium disponible para scraping visual
- FFmpeg instalado y accesible desde el PATH

---

## Instalación

```bash
cd /ruta/al/proyecto
pip install -r requirements.txt
```

Si aún no tienes los modelos necesarios, descárgalos:

```bash
ollama pull qwen3:8b
ollama pull qwen3-vl:8b
```

> Los nombres de los modelos se definen en [src/agents.py](src/agents.py). Si cambias tu configuración local, ajusta esos valores ahí.

---

## Ejecución

```bash
python main.py
```

Este comando arranca el pipeline completo y genera el episodio principal, así como archivos auxiliares y metadata relacionados.

---

## Contexto editorial

Los archivos dentro de [context/](context) no son solo documentación; forman parte del comportamiento del sistema. Definen:

- la identidad del programa
- los criterios de selección de noticias
- los estándares de calidad editorial
- la estructura del guion
- el tono y estilo del texto

Esto permite adaptar el producto sin cambiar la lógica central del pipeline.

---

## Consideraciones importantes

- El proyecto está preparado para ejecutarse localmente con modelos y herramientas en el mismo entorno.
- Requiere dependencias de sistema como FFmpeg y Chrome/Chromium.
- Está pensado para automatizar la generación de contenido periodístico y audiovisual de forma reproducible.
- El sistema es extensible: puedes ajustar agentes, prompts, fuentes de noticias y flujo de publicación según tu caso de uso.- La publicación diaria del contenido se realiza en el canal de YouTube: https://www.youtube.com/@MacroDiario
---

## Autor

Iago Rivadulla

- GitHub: https://github.com/iagorivadulla
- LinkedIn: https://linkedin.com/in/iagorivadulla
