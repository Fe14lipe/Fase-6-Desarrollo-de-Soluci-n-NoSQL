import json
import os
import pyodbc

# Cargar la configuración de config.json
ruta_config = os.path.join(os.path.dirname(__file__), 'config.json')
try:
    with open(ruta_config, 'r') as archivo_config:
        config = json.load(archivo_config)
    name_server = config['name_server']
    database = config['database']
    driver = config['driver']
    uid = config.get('uid')
    pwd = config.get('pwd')
    
    if uid and pwd:
        connection_string = f'DRIVER={{{driver}}};SERVER={name_server};DATABASE={database};UID={uid};PWD={pwd};'
    else:
        connection_string = f'DRIVER={{{driver}}};SERVER={name_server};DATABASE={database};Trusted_Connection=yes;'
except Exception as e:
    connection_string = None
    print(f"Error al cargar config.json: {e}")
    exit(1)

def run_migration():
    if not connection_string:
        print("Sin cadena de conexión.")
        return
        
    print("Conectando a SQL Server...")
    try:
        conn = pyodbc.connect(connection_string, autocommit=True)
    except Exception as e:
        print(f"Error al conectar con BD original: {e}")
        return
            
    cursor = conn.cursor()
    
    ruta_migracion = os.path.join(os.path.dirname(__file__), 'sql', 'SP_CRUD_Artistas_Canciones_Playlists.sql')
    print(f"Leyendo script de SPs: {ruta_migracion}")
    with open(ruta_migracion, 'r', encoding='utf-8') as f:
        script = f.read()
        
    # El archivo SQL tiene GO como delimitador. Lo dividimos en bloques.
    bloques = script.split('\nGO\n')
    if len(bloques) == 1:
        bloques = script.split('\ngo\n')
    if len(bloques) == 1:
        bloques = script.split('GO')

    print(f"Encontrados {len(bloques)} bloques de comandos.")
    
    for i, bloque in enumerate(bloques):
        cmd = bloque.strip()
        if not cmd:
            continue
            
        print(f"Ejecutando bloque {i+1}...")
        try:
            cursor.execute(cmd)
        except Exception as ex:
            print(f"Error al ejecutar bloque {i+1}: {ex}")
            print(f"Comando conflictivo:\n{cmd[:200]}...")
            
    cursor.close()
    conn.close()
    print("Migración de SPs finalizada con éxito.")

if __name__ == '__main__':
    run_migration()
