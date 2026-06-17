import json
import os
import pyodbc

# Cargar la configuración de base de datos
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

def main():
    if not connection_string:
        print("Error: No se pudo construir la cadena de conexión.")
        return
        
    try:
        conexion = pyodbc.connect(connection_string)
        cursor = conexion.cursor()
        
        # 1. Mostrar recuento actual
        cursor.execute("SELECT COUNT(*) FROM soundwave.Pago")
        count_pagos = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM soundwave.Reproduccion")
        count_repro = cursor.fetchone()[0]
        
        print(f"Estado actual de la base de datos:")
        print(f" - Pagos registrados: {count_pagos}")
        print(f" - Reproducciones registradas: {count_repro}")
        
        # 2. Eliminar registros
        print("\nLimpiando datos quemados de reportes...")
        
        # Primero eliminar pagos
        cursor.execute("DELETE FROM soundwave.Pago")
        print(" - Tabla soundwave.Pago limpiada.")
        
        # Luego eliminar reproducciones
        cursor.execute("DELETE FROM soundwave.Reproduccion")
        print(" - Tabla soundwave.Reproduccion limpiada.")
        
        conexion.commit()
        print("\n¡Limpieza completada con éxito en la base de datos!")
        
        # 3. Mostrar recuento posterior
        cursor.execute("SELECT COUNT(*) FROM soundwave.Pago")
        new_pagos = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM soundwave.Reproduccion")
        new_repro = cursor.fetchone()[0]
        
        print(f"\nNuevo estado:")
        print(f" - Pagos: {new_pagos}")
        print(f" - Reproducciones: {new_repro}")
        
        conexion.close()
    except Exception as e:
        print(f"Error al limpiar la base de datos: {e}")

if __name__ == '__main__':
    main()
