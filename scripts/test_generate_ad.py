import os
import json
import re
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

# Try to find uploaded file or upload fresh
files = list(client.files.list())
pajarillo_file = None
for f in files:
    if 'pajarillo' in (f.display_name or '').lower() or '8smu3gum78ee' in f.name:
        pajarillo_file = f
        break

if not pajarillo_file:
    print('Uploading video...')
    pajarillo_file = client.files.upload(file='DOCUMENTAL EL PAJARILLO_demo.mp4')
    import time
    while pajarillo_file.state.name == 'PROCESSING':
        time.sleep(2)
        pajarillo_file = client.files.get(name=pajarillo_file.name)

print(f'Using file: {pajarillo_file.name}')

prompt = """Eres un especialista de referencia en Audiodescripción (AD) según la norma UNE 153020 para personas con discapacidad visual en museos y centros de interpretación.
Tienes ante ti el vídeo del documental 'DOCUMENTAL EL PAJARILLO_demo.mp4' (duración total 1 minuto 55 segundos).

Tu labor consiste en audiodescribir todo el metraje:
1. Escucha atentamente la voz en off original (la locución del narrador).
2. Localiza todos los intervalos donde la voz en off NO está hablando (momentos de música o pausas de voz).
3. Para cada intervalo disponible donde haya contenido visual que un invidente deba conocer, redacta una locución descriptiva concisa, objetiva y evocadora en español de España.
   Ejemplos de lo que debes describir:
   - Títulos o rótulos que aparecen en pantalla.
   - Paisajes, entorno geográfico, cerros o vegetación.
   - Reconstrucciones 3D y maquetas virtuales del santuario o elementos arquitectónicos.
   - Las esculturas íberas: el león ibérico, el guerrero, detalles del rostro, el caballo, etc.
   - Fotografías históricas de las excavaciones o arqueólogos.
4. Calcula con precisión el segundo de inicio y de fin. Procura que la frase no sea más larga de lo que dura la pausa para no pisar la voz original (una regla orientativa es de 2.5 a 3 palabras por segundo).

Devuelve ÚNICAMENTE un array JSON válido con esta estructura:
[
  {
    "id": 1,
    "start": "00:03",
    "end": "00:09",
    "start_seconds": 3.0,
    "end_seconds": 9.0,
    "text": "Descripción clara y precisa."
  }
]
"""

response = client.models.generate_content(
    model='gemini-3.5-flash',
    contents=[pajarillo_file, prompt]
)

raw = response.text
match = re.search(r'\[.*\]', raw, re.DOTALL)
if match:
    data = json.loads(match.group(0))
    print(f'Successfully parsed {len(data)} audio description cues:')
    for item in data:
        dur = item.get("end_seconds", 0) - item.get("start_seconds", 0)
        print(f'[{item.get("start")} -> {item.get("end")}] ({dur:.1f}s): {item.get("text")}')
    with open('demo_audiodescripcion.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print('Saved to demo_audiodescripcion.json')
else:
    print('Raw response:\n', raw)
