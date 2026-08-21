import json
from agents import run_agent

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


    return miniatures




if __name__ == '__main__':

    script_dict = r'C:\Users\usuario\Desktop\Python\Macro News\script_dict.json'
    seo_dict = r'C:\Users\usuario\Desktop\Python\Macro News\seo_dict.json'

    with open(script_dict, 'r', encoding='utf-8') as f:
        script_dict = json.load(f)

    with open(seo_dict, 'r', encoding='utf-8') as f:
        seo_dict = json.load(f)

    print(miniatures_title(seo_dict))