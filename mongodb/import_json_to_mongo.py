import os
import json
from datetime import datetime
from pymongo import MongoClient

# Claves que representan fechas en nuestro esquema y que deben convertirse a BSON Date
DATE_KEYS = {
    "fechaFundacion", 
    "fechaInicio", 
    "fechaRegistro", 
    "fechaFin", 
    "fechaPago", 
    "fechaLanzamiento", 
    "fechaCreacion", 
    "fechaAgregado", 
    "fechaHora"
}

def parse_dates(data):
    """
    Recorre recursivamente el diccionario/lista para convertir cadenas de texto de fecha
    en objetos datetime de Python (BSON Dates en MongoDB).
    """
    if isinstance(data, dict):
        for key, value in list(data.items()):
            if key in DATE_KEYS and isinstance(value, str):
                try:
                    # Formato de fecha de SQL Server: YYYY-MM-DD o con hora YYYY-MM-DDTHH:MM:SS.fff
                    if len(value) == 10:
                        data[key] = datetime.strptime(value, "%Y-%m-%d")
                    else:
                        # Limpiar microsegundos o indicadores de zona horaria si los hay
                        clean_val = value.split(".")[0].replace("Z", "")
                        data[key] = datetime.fromisoformat(clean_val)
                except Exception as e:
                    print(f"Advertencia: No se pudo convertir fecha '{value}' para la clave '{key}': {e}")
            else:
                parse_dates(value)
    elif isinstance(data, list):
        for item in data:
            parse_dates(item)

def run_import():
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    ruta_config = os.path.join(os.path.dirname(directorio_actual), 'config.json')
    
    print(f"Cargando configuración desde: {ruta_config}")
    with open(ruta_config, 'r') as file:
        config = json.load(file)
        
    mongodb_uri = config.get("mongodb_uri", "mongodb://localhost:27017/")
    mongodb_db = config.get("mongodb_db", "SoundWave")
    
    print(f"Conectando a MongoDB en {mongodb_uri}...")
    client = MongoClient(mongodb_uri)
    db = client[mongodb_db]
    
    data_dir = os.path.join(directorio_actual, 'data')
    if not os.path.exists(data_dir):
        print(f"Error: La carpeta de datos {data_dir} no existe. Ejecuta primero export_sql_to_json.py.")
        return
        
    colecciones = ["discograficas", "artistas", "usuarios", "albums", "playlists", "reproducciones"]
    
    for coll_name in colecciones:
        file_path = os.path.join(data_dir, f"{coll_name}.json")
        if not os.path.exists(file_path):
            print(f"Advertencia: Archivo {file_path} no encontrado, saltando...")
            continue
            
        print(f"Leyendo archivo {file_path}...")
        with open(file_path, 'r', encoding='utf-8') as f:
            documents = json.load(f)
            
        # Convertir cadenas ISO a objetos datetime nativos de Python
        parse_dates(documents)
        
        # Limpiar la colección existente
        print(f"Limpiando colección existente '{coll_name}'...")
        db[coll_name].delete_many({})
        
        if documents:
            print(f"Insertando {len(documents)} documentos en '{coll_name}'...")
            db[coll_name].insert_many(documents)
            print(f"Colección '{coll_name}' importada exitosamente.")
        else:
            print(f"Colección '{coll_name}' sin datos para insertar.")
            
    # Crear Índices recomendados para rendimiento
    print("Creando índices en MongoDB...")
    db.usuarios.create_index("email", unique=True)
    db.reproducciones.create_index("fechaHora")
    db.playlists.create_index("usuarioId")
    
    # Índice de texto para búsqueda de canciones si se anidan o de manera externa
    # Si tenemos canciones como colección separada o en álbumes, creamos índices según corresponda.
    # En nuestro esquema actual de canciones externas o embebidas:
    db.albums.create_index("canciones.titulo")
    
    print("Índices creados exitosamente.")
    client.close()
    print("Importación a MongoDB completada con éxito.")

if __name__ == "__main__":
    run_import()
