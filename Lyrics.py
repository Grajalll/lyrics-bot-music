import os
import urllib.parse
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from googlesearch import search

app = Flask(__name__)
# Habilita CORS para permitir que tu archivo index.html se conecte de forma remota
CORS(app)

# URL de tu webhook de Discord para el canal de música
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1564450348402348172/IACrtXiL8QwT_AbckPy08kHJS0E7VbMGzlz2AZSL8x06y_VscT40AQimttMah3XQ2R1y"

# Cabecera para simular un navegador real y evitar bloqueos automáticos de Google o APIs de letras
HEADERS_PROXIES = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def normalizar_texto(texto):
    """Limpia el texto eliminando signos de puntuación y dobles espacios para mejor coincidencia"""
    caracteres_limpios = "".join([c.lower() for c in texto if c.isalnum() or c.isspace()])
    return " ".join(caracteres_limpios.split())

def identificar_cancion_por_google(frase):
    """Busca fragmentos de la letra directamente en el motor orgánico de Google"""
    query = f'"{frase}" lyrics'
    try:
        # Extrae de forma limpia los primeros 5 enlaces indexados por Google
        enlaces = search(query, num_results=5, lang="en")
        for link in enlaces:
            link_lower = link.lower()
            if "genius.com" in link_lower:
                # Procesa el formato de URL estándar de Genius para extraer metadatos
                slug = link_lower.split("://genius.com")[-1].replace("-lyrics", "")
                partes = slug.split("-")
                if len(partes) >= 2:
                    artista = partes[0].replace("/", "").strip().title()
                    titulo = " ".join(partes[1:]).strip().title()
                    return artista, titulo
    except Exception as e:
        print(f"Error durante el escaneo en Google: {e}")
    return None, None

def descargar_letra_api(artista, titulo):
    """Descarga los versos estructurados utilizando la API de letras públicas"""
    url_api = f"https://lyrics.ovh{urllib.parse.quote(artista)}/{urllib.parse.quote(titulo)}"
    try:
        respuesta = requests.get(url_api, headers=HEADERS_PROXIES, timeout=10)
        if respuesta.status_code == 200:
            letra = respuesta.json().get("lyrics", "")
            if letra:
                # Divide el bloque de texto completo en una lista de líneas limpias
                return [linea.strip() for linea in letra.split("\n") if linea.strip()]
    except Exception as e:
        print(f"Error en el servidor de la API de letras: {e}")
    return []

@app.route("/cantar", methods=["POST"])
def procesar_canto():
    datos = request.get_json()
    if not datos or "frase" not in datos:
        return jsonify({"error": "Falta el parametro indispensable 'frase'"}), 400
        
    linea_usuario = datos["frase"]
    artista, titulo = identificar_cancion_por_google(linea_usuario)
    
    if not artista or not titulo:
        return jsonify({"status": "No se pudo identificar la cancion o artista en Google"}), 404
        
    lineas_letra = descargar_letra_api(artista, titulo)
    entrada_limpia = normalizar_texto(linea_usuario)
    
    # Recorre la letra de la canción buscando la línea ingresada por el usuario
    for i, linea_oficial in enumerate(lineas_letra):
        if entrada_limpia in normalizar_texto(linea_oficial):
            if i + 1 < len(lineas_letra):
                verso_siguiente = lineas_letra[i + 1]
                
                # Construye dinámicamente un enlace de búsqueda para YouTube Music
                query_ym = f"{artista} {titulo}"
                url_music = f"https://youtube.com{urllib.parse.quote(query_ym)}"
                
                # Prepara el formato estructurado para Discord
                payload = {
                    "content": f"🎶 **{artista} - {titulo}** \n▶️ Enlace del tema: {url_music}",
                    "embeds": [{
                        "description": f"🎤 *...cantando desde la nube:*\n\n**\"{verso_siguiente.upper()}\"**",
                        "color": 3066993
                    }]
                }
                requests.post(DISCORD_WEBHOOK_URL, json=payload)
                return jsonify({"status": "Exito", "cancion": f"{artista} - {titulo}", "verso": verso_siguiente})
                
    return jsonify({"status": "La linea ingresada no fue localizada dentro de la letra oficial"}), 404

if __name__ == "__main__":
    # Render asigna el puerto dinámicamente mediante variables de entorno
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=puerto)