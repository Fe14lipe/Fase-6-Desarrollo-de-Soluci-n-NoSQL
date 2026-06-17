import os
import json
import pyodbc

# Consultas SQL para exportar cada colección en formato JSON
QUERIES = {
    "discograficas": """
        SELECT discograficaId, nombre, pais, fechaFundacion, eliminado
        FROM soundwave.Discografica
        FOR JSON PATH;
    """,
    "artistas": """
        SELECT 
            a.artistaId, 
            a.nombreArtistico, 
            a.pais, 
            a.fechaInicio,
            a.Discografica_discograficaId AS discograficaId,
            d.nombre AS discograficaNombre,
            a.eliminado
        FROM soundwave.Artista a
        LEFT JOIN soundwave.Discografica d ON a.Discografica_discograficaId = d.discograficaId
        FOR JSON PATH;
    """,
    "usuarios": """
        SELECT 
            u.usuarioId,
            u.nombre,
            u.apellido,
            u.email,
            u.contraseña,
            u.pais,
            u.fechaRegistro,
            u.estado,
            u.telefono,
            u.eliminado,
            JSON_QUERY((
                SELECT 
                    s.suscripcionId,
                    s.fechaInicio,
                    s.fechaFin,
                    s.estado,
                    JSON_QUERY((
                        SELECT 
                            planId,
                            nombre,
                            precioMensual,
                            descripcion
                        FROM soundwave.PlanSuscripcion p
                        WHERE p.planId = s.Plan_planId
                        FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
                    )) AS [plan],
                    JSON_QUERY((
                        SELECT 
                            pagoId,
                            monto,
                            fechaPago,
                            metodoPago,
                            estado
                        FROM soundwave.Pago pg
                        WHERE pg.Suscripcion_suscripcionId = s.suscripcionId
                        FOR JSON PATH
                    )) AS pagos
                FROM soundwave.Suscripcion s
                WHERE s.Usuario_usuarioId = u.usuarioId
                FOR JSON PATH
            )) AS suscripciones
        FROM soundwave.Usuario u
        FOR JSON PATH;
    """,
    "albums": """
        SELECT 
            al.albumId,
            al.titulo,
            al.fechaLanzamiento,
            al.Artista_artistaId AS artistaId,
            ar.nombreArtistico AS artistaNombre,
            JSON_QUERY((
                SELECT 
                    c.cancionId,
                    c.titulo,
                    c.duracion,
                    c.explicita,
                    c.eliminado,
                    JSON_QUERY((
                        SELECT g.nombre
                        FROM soundwave.CancionGenero cg
                        JOIN soundwave.Genero g ON cg.Genero_generoId = g.generoId
                        WHERE cg.Cancion_cancionId = c.cancionId
                        FOR JSON PATH
                    )) AS generos
                FROM soundwave.Cancion c
                WHERE c.Album_albumId = al.albumId
                FOR JSON PATH
            )) AS canciones
        FROM soundwave.Album al
        JOIN soundwave.Artista ar ON al.Artista_artistaId = ar.artistaId
        FOR JSON PATH;
    """,
    "playlists": """
        SELECT 
            p.playlistId,
            p.nombre,
            p.fechaCreacion,
            p.privacidad,
            p.Usuario_usuarioId AS usuarioId,
            (u.nombre + ' ' + u.apellido) AS usuarioNombre,
            p.eliminado,
            JSON_QUERY((
                SELECT 
                    c.cancionId,
                    c.titulo,
                    c.duracion,
                    al.albumId,
                    al.titulo AS albumTitulo,
                    ar.nombreArtistico AS artistaNombre,
                    pc.fechaAgregado
                FROM soundwave.PlaylistCancion pc
                JOIN soundwave.Cancion c ON pc.Cancion_cancionId = c.cancionId
                JOIN soundwave.Album al ON c.Album_albumId = al.albumId
                JOIN soundwave.Artista ar ON al.Artista_artistaId = ar.artistaId
                WHERE pc.Playlist_playlistId = p.playlistId
                FOR JSON PATH
            )) AS canciones
        FROM soundwave.Playlist p
        JOIN soundwave.Usuario u ON p.Usuario_usuarioId = u.usuarioId
        FOR JSON PATH;
    """,
    "reproducciones": """
        SELECT 
            r.reproduccionId,
            r.fechaHora,
            r.duracionEscuchada,
            r.dispositivo,
            r.Usuario_usuarioId AS usuarioId,
            r.Cancion_cancionId AS cancionId,
            c.titulo AS cancionTitulo,
            ar.nombreArtistico AS artistaNombre
        FROM soundwave.Reproduccion r
        JOIN soundwave.Cancion c ON r.Cancion_cancionId = c.cancionId
        JOIN soundwave.Album al ON c.Album_albumId = al.albumId
        JOIN soundwave.Artista ar ON al.Artista_artistaId = ar.artistaId
        FOR JSON PATH;
    """
}

def clean_genres(data):
    """
    Las consultas FOR JSON PATH de géneros retornan una lista de objetos: [{"nombre": "Pop"}].
    Esta función los simplifica a un arreglo plano de strings: ["Pop"].
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "generos" and isinstance(value, list):
                data[key] = [item["nombre"] for item in value if "nombre" in item]
            else:
                clean_genres(value)
    elif isinstance(data, list):
        for item in data:
            clean_genres(item)

def run_export():
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    ruta_config = os.path.join(os.path.dirname(directorio_actual), 'config.json')
    
    print(f"Cargando configuración desde: {ruta_config}")
    with open(ruta_config, 'r') as file:
        config = json.load(file)
        
    name_server = config['name_server']
    database = config['database']
    driver = config['driver']
    uid = config.get('uid')
    pwd = config.get('pwd')
    
    if uid and pwd:
        conn_str = f'DRIVER={{{driver}}};SERVER={name_server};DATABASE={database};UID={uid};PWD={pwd};'
    else:
        conn_str = f'DRIVER={{{driver}}};SERVER={name_server};DATABASE={database};Trusted_Connection=yes;'
        
    print("Conectando a SQL Server...")
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    
    # Crear carpeta de datos si no existe
    data_dir = os.path.join(directorio_actual, 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    for collection, query in QUERIES.items():
        print(f"Exportando colección '{collection}'...")
        cursor.execute(query)
        
        # SQL Server retorna los resultados JSON fragmentados en múltiples filas/columnas
        json_chunks = []
        for row in cursor.fetchall():
            if row[0]:
                json_chunks.append(row[0])
                
        json_str = "".join(json_chunks) if json_chunks else "[]"
        data = json.loads(json_str)
        
        # Limpieza específica para pasar géneros a lista plana de strings
        if collection == "albums":
            clean_genres(data)
            
        file_path = os.path.join(data_dir, f"{collection}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        print(f"Guardado exitosamente en {file_path} (Total registros: {len(data)})")
        
    cursor.close()
    conn.close()
    print("Migración de exportación a JSON completada con éxito.")

if __name__ == "__main__":
    run_export()
