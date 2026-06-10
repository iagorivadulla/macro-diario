# 📰 Macro Diario

[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)](https://www.python.org/)
[![Ollama](https://img.shields.io/badge/Ollama-local%20LLM-black?style=flat-square)](https://ollama.com/)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2-red?style=flat-square)](https://docs.pydantic.dev/)
[![Kokoro](https://img.shields.io/badge/Kokoro-TTS-purple?style=flat-square)](https://github.com/hexgrad/kokoro)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-audio%20post-green?style=flat-square&logo=ffmpeg)](https://ffmpeg.org/)
[![Selenium](https://img.shields.io/badge/Selenium-scraping-43B02A?style=flat-square&logo=selenium)](https://www.selenium.dev/)
[![OpenCV](https://img.shields.io/badge/OpenCV-video-5C3EE8?style=flat-square&logo=opencv)](https://opencv.org/)
[![PIL](https://img.shields.io/badge/PIL-pixel--art-orange?style=flat-square)](https://pillow.readthedocs.io/)

Pipeline completamente automatizado que genera un podcast y vídeo diario de análisis macroeconómico en español, desde la ingesta de noticias hasta la publicación final — sin intervención humana.

---

## ¿Qué hace?

Cada día, el pipeline ejecuta el ciclo completo de forma autónoma:

1. **Scraping de noticias** — recopila artículos financieros de fuentes relevantes
2. **Generación del guión** — un sistema multi-agente con LLMs locales redacta el episodio con contexto editorial propio
3. **Síntesis de voz** — TTS neuronal con Kokoro/Supertonic convierte el guión en audio
4. **Post-procesado de audio** — cadena FFmpeg con EQ paramétrica y normalización EBU R128
5. **Generación de imágenes** — agente visual busca y selecciona imágenes contextualmente relevantes para cada sección
6. **Composición de vídeo** — las imágenes se integran en un panel junto a un presentador pixel-art animado (estados de boca mapeados a RMS de audio, parpadeos aleatorios)
7. **Publicación RSS** — genera el feed para distribución como podcast

---

## Arquitectura

```
main.py
├── rss.py               ← Scraping de titulares y enlaces
├── scraper.py           ← Extracción de texto de artículos
├── agents.py            ← Sistema multi-agente (guión, imágenes, corrección)
│   ├── script_agent     ← Redacción del episodio (qwen2.5:7b)
│   ├── critic_agent     ← Revisión y mejora del guión (gemma3:12b)
│   └── image_agent      ← Generación de queries visuales + scraping Bing
├── produccion.py        ← TTS, composición de vídeo, animación presentador
└── context/             ← Archivos .md con directrices editoriales inyectadas como system prompt
```

---

## Stack técnico

| Capa | Tecnología |
|---|---|
| LLM inference | Ollama (local) — qwen2.5:7b, gemma3:12b |
| Structured output | Pydantic |
| TTS | Kokoro ONNX + Supertonic |
| Audio post | FFmpeg — `anequalizer`, EBU R128, normalización SR |
| Scraping imágenes | Selenium + undetected-chromedriver |
| Composición vídeo | OpenCV + PIL |
| Presentador animado | PIL (pixel-art, mouth states → RMS, blinks aleatorios) |
| Scraping noticias | newspaper3k |
| Distribución | RSS feed |

---

## Estructura del proyecto

```
macro-diario/
├── agents.py            # Agentes LLM: guión, crítico, imágenes
├── main.py              # Orquestador principal del pipeline
├── produccion.py        # TTS + composición audiovisual
├── rss.py               # Scraping de fuentes de noticias
├── scraper.py           # Extracción de texto de artículos
├── requirements.txt
├── assets/              # Sprites del presentador pixel-art
└── context/             # Contexto editorial (inyectado en system prompts)
    ├── editorial.md
    ├── structure.md
    ├── style.md
    ├── standards.md
    └── filter_criteria.md
```

---

## Ejecutar

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ollama debe estar corriendo con los modelos descargados
ollama pull qwen2.5:7b
ollama pull gemma3:12b

# Ejecutar el pipeline completo
python main.py
```

> El pipeline requiere Chrome instalado para el scraping de imágenes vía Selenium.

---

## Contexto editorial

Los archivos en `context/` definen la personalidad del podcast: tono, estructura de secciones, criterios de filtrado de noticias y estándares de calidad. Se inyectan directamente en los system prompts de los agentes, lo que permite ajustar el output sin tocar el código.

---

## Autor

**Iago Rivadulla** — Data Scientist  
[linkedin.com/in/iagorivadulla](https://linkedin.com/in/iagorivadulla) · [GitHub](https://github.com/iagorivadulla)