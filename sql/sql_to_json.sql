-- =======================================================================
-- SCRIPT SQL DE CONSULTAS PARA GENERAR ARCHIVOS JSON (MIGRACIÓN A NOSQL)
-- Proyecto: SoundWave - Fase 6 (Versión Corregida)
-- =======================================================================
USE SoundWave;
GO

-- 1. Colección: discograficas
-- Exportación directa de la tabla soundwave.Discografica
SELECT 
    discograficaId, 
    nombre, 
    pais, 
    fechaFundacion, 
    eliminado
FROM soundwave.Discografica
FOR JSON PATH;
GO

-- 2. Colección: artistas
-- Exportación de soundwave.Artista, incluyendo el nombre de su discográfica desnormalizado
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
GO

-- 3. Colección: usuarios (Modelo Embebido con JSON_QUERY)
-- Anidamiento de suscripciones y pagos dentro de cada documento de usuario
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
GO

-- 4. Colección: albums (Modelo Embebido de Canciones con JSON_QUERY)
-- Anidamiento de canciones y sus géneros (como arreglo de strings) dentro de cada álbum
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
GO

-- 5. Colección: playlists (Modelo de Canciones Embebidas con Referencia y JSON_QUERY)
-- Anidamiento de canciones asociadas a la playlist con datos desnormalizados
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
GO

-- 6. Colección: reproducciones
-- Registro plano de reproducciones (Time-series / Audits) con títulos y nombres desnormalizados
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
GO
