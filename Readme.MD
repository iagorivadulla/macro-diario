# Macro Diario

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Ollama](https://img.shields.io/badge/Ollama-LLM-black)](https://ollama.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-CUDA%2012.1-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![OmniVoice](https://img.shields.io/badge/OmniVoice-TTS-5B8C5A)](https://github.com/k2-fsa/OmniVoice)
[![Selenium](https://img.shields.io/badge/Selenium-Web%20automation-43B02A?logo=selenium&logoColor=white)](https://www.selenium.dev/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-Audio%20%26%20video-007808?logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-Image%20processing-5C3EE8?logo=opencv&logoColor=white)](https://opencv.org/)
[![Pillow](https://img.shields.io/badge/Pillow-Image%20processing-3776AB)](https://pillow.readthedocs.io/)
[![Pydantic](https://img.shields.io/badge/Pydantic-Data%20validation-E92063?logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)



Macro Diario es un pipeline de producción audiovisual para un informativo económico en español. Reúne noticias, las resume y valida con modelos de lenguaje, genera un guion y una locución, crea el vídeo principal y sus Shorts, prepara metadatos y puede subir el contenido a YouTube.

Canal: [youtube.com/@MacroDiario](https://www.youtube.com/@MacroDiario)

## Flujo de producción

Al ejecutar `python main.py`, el programa realiza estas etapas:

1. Obtiene noticias de Expansión y elEconomista y selecciona siete titulares con Ollama.
2. Extrae los artículos, genera resúmenes y los somete a un control factual; intenta corregir los rechazados hasta cinco veces.
3. Redacta la apertura, los bloques de noticias y un guion breve para cada Short. La revisión adicional del guion está desactivada actualmente en `main.py`.
4. Busca imágenes para las secciones y genera la locución en español con OmniVoice.
5. Produce el episodio y los Shorts, crea metadatos SEO y renderiza la miniatura.
6. Elimina imágenes y audios temporales e inicia la publicación del vídeo y de los Shorts en YouTube.

La lectura del feed de Yahoo está definida en el código, pero no se utiliza en la ejecución actual. El proyecto no publica en TikTok.

## Estructura

```text
.
├── main.py                   # Orquesta el pipeline completo
├── src/
│   ├── agents.py              # Agentes de selección, resumen, guion, voz, imágenes y SEO
│   ├── rss.py                 # Obtención de titulares
│   ├── scraper.py             # Extracción del contenido de los artículos
│   ├── produccion.py          # Vídeo horizontal
│   ├── produccion_shorts.py   # Vídeos verticales
│   ├── miniatures.py         # Render de la miniatura
│   └── youtube.py             # Subida y programación en YouTube
├── context/                   # Instrucciones editoriales usadas por los agentes
├── assets/
│   ├── audio/                  # Voz de referencia, música y ejecutable de FFmpeg
│   ├── background/             # Fondos y sprites del presentador
│   ├── fonts/                  # Tipografías
│   └── miniature/              # Plantilla y miniatura renderizada
├── requirements.txt
└── seo_dict.json              # Metadatos de salida (generados)
```

## Requisitos

- Python y las dependencias indicadas en `requirements.txt`.
- Ollama instalado y en ejecución, con los modelos `qwen3.5:9b`, `qwen3:8b` y `qwen3-vl:8b` disponibles.
- Una GPU NVIDIA compatible con la configuración CUDA de PyTorch y OmniVoice usada por el código.
- Chrome y ChromeDriver compatibles para la extracción web y la subida a YouTube.
- Los recursos locales de `assets/`: en particular, `audio/omnivoice_voice.pt`, `audio/ffmpeg.exe`, la música, los fondos, los sprites, la plantilla de miniatura y la tipografía referenciada por los módulos.
- Los directorios de trabajo `assets/news_images/` y `video/shorts/` (este último debe existir antes del primer arranque).

La configuración de audio y publicación contiene rutas absolutas de Windows y una ruta de perfil de Chrome (`C:\ChromeSelenium`). Antes de ejecutar el pipeline en otra máquina, adapta esas rutas en `src/agents.py`, `src/youtube.py` y, si corresponde, los valores de FFmpeg en `main.py` y los módulos de producción. `requirements.txt` fija, entre otras dependencias, una versión de PyTorch con CUDA 12.1; la instalación debe ser compatible con el sistema operativo y la GPU disponibles.

## Instalación

Desde la raíz del repositorio, crea y activa un entorno virtual. En Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

En Windows, activa el entorno con:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Descarga los modelos de Ollama:

```bash
ollama pull qwen3.5:9b
ollama pull qwen3:8b
ollama pull qwen3-vl:8b
```

Los nombres y parámetros de los modelos se configuran en [src/agents.py](src/agents.py). La primera carga de OmniVoice también puede descargar sus pesos desde Hugging Face.

## Ejecución

```bash
python main.py
```

Este comando ejecuta el pipeline completo y, al final, intenta publicar en YouTube. No es un modo de prueba: revisa las rutas, los recursos, la sesión de Chrome y los datos generados antes de lanzarlo. El punto de entrada actual llama directamente a `flow()`.

Los principales archivos de salida son:

- `script_dict.json`: guion y datos de las secciones.
- `seo_dict.json`: títulos, descripciones y hashtags.
- `video/episode.mp4`: episodio horizontal.
- `video/shorts/`: Shorts generados.
- `assets/miniature/miniature_out.jpg`: miniatura del episodio.

El flujo borra al inicio los vídeos y la miniatura anteriores y, antes de publicar, elimina las imágenes y los audios temporales. Conserva los archivos de salida indicados.

## Contexto editorial

Los archivos de [context/](context/) se incorporan a las instrucciones de los agentes y afectan a la selección y redacción:

- `editorial.md`: identidad, audiencia y misión.
- `filter_criteria.md`: prioridades y exclusiones de noticias.
- `standards.md`: validación factual de los resúmenes.
- `structure.md`: estructura prevista para el episodio.
- `style.md`: tono y registro.

## Autor

Iago Rivadulla

- [GitHub](https://github.com/iagorivadulla)
- [LinkedIn](https://linkedin.com/in/iagorivadulla)
