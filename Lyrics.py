import os
import urllib.parse
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
# Habilita CORS para autorizar las conexiones entrantes desde tu index.html local
CORS(app)

# URL de tu Webhook de Discord
DISCORD_WEBHOOK_URL = "https://discord.com"

HEADERS_PROXIES = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

def normalizar_texto(texto):
    """Limpia cadenas para hacer emparejamientos de versos mucho más precisos"""
    caracteres_limpios = "".join([c.lower() for c in texto if c.isalnum() or c.isspace()])
    return " ".join(caracteres_limpios.split())

def identificar_cancion_ddg(frase):
    """Busca la canción usando la web de DuckDuckGo evitando bloqueos de captcha"""
    query = f'"{frase}" lyrics genius'
    url_busqueda = f"https://duckduckgo.com"
    payload = {"q": query}
    
    try:
        respuesta = requests.post(url_busqueda, headers=HEADERS_PROXIES, data=payload, timeout=10)
        if respuesta.status_code == 200:
            texto_html = respuesta.text.lower()
            
            # Si Genius está en los resultados de búsqueda, extraemos el slug de la URL
            if "://genius.com" in texto_html:
                bloques = texto_html.split("://genius.com")
                for bloque in bloques[1:]:
                    slug = bloque.split('"')[0].split("'")[0].split("&")[0].split(")")[0].strip()
                    if "-lyrics" in slug or len(slug) > 5:
                        slug_limpio = slug.replace("-lyrics", "")
                        partes = slug_limpio.split("-")
                        if len(partes) >= 2:
                            artista = partes[0].replace("/", "").strip().title()
                            titulo = " ".join(partes[1:]).strip().title()
                            return artista, titulo
    except Exception as e:
        print(f"Error en buscador secundario: {e}")
    return None, None

def descargar_letra_api(artista, titulo):
    """Conecta con la base de datos de letras públicas de forma de lista"""
    url_api = f"https://lyrics.ovh{urllib.parse.quote(artista)}/{urllib.parse.quote(titulo)}"
    try:
        respuesta = requests.get(url_api, headers=HEADERS_PROXIES, timeout=10)
        if respuesta.status_code == 200:
            letra = respuesta.json().get("lyrics", "")
            if letra:
                return [linea.strip() for linea in letra.split("\n") if linea.strip()]
    except Exception as e:
        print(f"Error en el servidor de letras: {e}")
    return []

@app.route("/cantar", methods=["POST"])
def procesar_canto():
    datos = request.get_json()
    if not datos or "frase" not in datos:
        return jsonify({"error": "Falta el parametro indispensable 'frase'"}), 400
        
    linea_usuario = datos["frase"]
    artista, titulo = identificar_cancion_ddg(linea_usuario)
    
    # Intento de respaldo secundario sin comillas si la búsqueda exacta falla
    if not artista or not titulo:
        artista, titulo = identificar_cancion_ddg(linea_usuario.replace('"', ''))
        
    if not artista or not titulo:
        return jsonify({"status": "No se pudo identificar el artista o cancion en internet"}), 404
        
    lineas_letra = descargar_letra_api(artista, titulo)
    entrada_limpia = normalizar_texto(linea_usuario)
    
    # Escaneo del arreglo de versos para encontrar el siguiente índice de canto
    for i, linea_oficial in enumerate(lineas_letra):
        if entrada_limpia in normalizar_texto(linea_oficial) or normalizar_texto(linea_oficial) in entrada_limpia:
            if i + 1 < len(lineas_letra):
                verso_siguiente = lineas_letra[i + 1]
                
                query_ym = f"{artista} {titulo}"
                url_music = f"https://youtube.com{urllib.parse.quote(query_ym)}"
                
                payload = {
                    "content": f"🎶 **{artista} - {titulo}** \n▶️ Enlace del tema: {url_music}",
                    "embeds": [{
                        "description": f"🎤 *...cantando desde la nube:*\n\n**\"{verso_siguiente.upper()}\"**",
                        "color": 3066993
                    }]
                }
                requests.post(DISCORD_WEBHOOK_URL, json=payload)
                return jsonify({"status": "Exito", "cancion": f"{artista} - {titulo}", "verso": verso_siguiente})
                
    return jsonify({"status": "La linea fue encontrada en internet pero no mapeada en el texto"}), 404

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=puerto)
