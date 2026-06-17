USE SoundWave;
GO

-- =======================================================================
-- DDL: AGREGAR COLUMNA 'eliminado' PARA BORRADO LÓGICO
-- =======================================================================

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('soundwave.Artista') AND name = 'eliminado')
BEGIN
    ALTER TABLE soundwave.Artista ADD eliminado BIT DEFAULT 0;
    EXEC('UPDATE soundwave.Artista SET eliminado = 0');
END;
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('soundwave.Cancion') AND name = 'eliminado')
BEGIN
    ALTER TABLE soundwave.Cancion ADD eliminado BIT DEFAULT 0;
    EXEC('UPDATE soundwave.Cancion SET eliminado = 0');
END;
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('soundwave.Playlist') AND name = 'eliminado')
BEGIN
    ALTER TABLE soundwave.Playlist ADD eliminado BIT DEFAULT 0;
    EXEC('UPDATE soundwave.Playlist SET eliminado = 0');
END;
GO


-- =======================================================================
-- PROCEDIMIENTOS ALMACENADOS PARA LA TABLA: Artista
-- =======================================================================

-- 1. Insertar Artista
CREATE OR ALTER PROCEDURE soundwave.SP_InsertarArtista
    @nombreArtistico VARCHAR(100),
    @pais VARCHAR(50),
    @fechaInicio DATE,
    @discograficaId INT
AS
BEGIN
    INSERT INTO soundwave.Artista (nombreArtistico, pais, fechaInicio, Discografica_discograficaId, eliminado)
    VALUES (@nombreArtistico, @pais, @fechaInicio, @discograficaId, 0);
END;
GO

-- 2. Consultar Artistas Activos
CREATE OR ALTER PROCEDURE soundwave.SP_ConsultarArtistas
AS
BEGIN
    SELECT a.artistaId, a.nombreArtistico, a.pais, a.fechaInicio, d.nombre, a.Discografica_discograficaId AS discograficaId
    FROM soundwave.Artista a
    LEFT JOIN soundwave.Discografica d ON a.Discografica_discograficaId = d.discograficaId
    WHERE a.eliminado = 0 OR a.eliminado IS NULL;
END;
GO

-- 3. Actualizar Artista
CREATE OR ALTER PROCEDURE soundwave.SP_ActualizarArtista
    @artistaId INT,
    @nombreArtistico VARCHAR(100),
    @pais VARCHAR(50),
    @fechaInicio DATE,
    @discograficaId INT
AS
BEGIN
    UPDATE soundwave.Artista
    SET nombreArtistico = @nombreArtistico,
        pais = @pais,
        fechaInicio = @fechaInicio,
        Discografica_discograficaId = @discograficaId
    WHERE artistaId = @artistaId;
END;
GO

-- 4. Borrado Lógico Artista (Mover a la papelera)
CREATE OR ALTER PROCEDURE soundwave.SP_EliminarArtista
    @artistaId INT
AS
BEGIN
    UPDATE soundwave.Artista
    SET eliminado = 1
    WHERE artistaId = @artistaId;
END;
GO

-- 5. Consultar Artistas Eliminados (Papelera)
CREATE OR ALTER PROCEDURE soundwave.SP_ConsultarArtistasEliminados
AS
BEGIN
    SELECT a.artistaId, a.nombreArtistico, a.pais, a.fechaInicio, d.nombre, a.Discografica_discograficaId AS discograficaId
    FROM soundwave.Artista a
    LEFT JOIN soundwave.Discografica d ON a.Discografica_discograficaId = d.discograficaId
    WHERE a.eliminado = 1;
END;
GO

-- 6. Restaurar Artista
CREATE OR ALTER PROCEDURE soundwave.SP_RestaurarArtista
    @artistaId INT
AS
BEGIN
    UPDATE soundwave.Artista
    SET eliminado = 0
    WHERE artistaId = @artistaId;
END;
GO

-- 7. Borrado Físico Permanente Artista (Hard Delete)
CREATE OR ALTER PROCEDURE soundwave.SP_EliminarFisicoArtista
    @artistaId INT
AS
BEGIN
    -- Nota: El trigger TRG_PreventArtistDelete validará si tiene canciones y álbumes vinculados.
    DELETE FROM soundwave.Artista
    WHERE artistaId = @artistaId AND eliminado = 1;
END;
GO


-- =======================================================================
-- PROCEDIMIENTOS ALMACENADOS PARA LA TABLA: Cancion
-- =======================================================================

-- 1. Insertar Canción
CREATE OR ALTER PROCEDURE soundwave.SP_InsertarCancion
    @titulo VARCHAR(100),
    @duracion INT,
    @explicita BIT,
    @albumId INT
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO soundwave.Cancion (titulo, duracion, explicita, Album_albumId, eliminado)
    VALUES (@titulo, @duracion, @explicita, @albumId, 0);
    SELECT SCOPE_IDENTITY() AS cancionId;
END;
GO

-- 2. Consultar Canciones Activas
CREATE OR ALTER PROCEDURE soundwave.SP_ConsultarCanciones
AS
BEGIN
    SELECT c.cancionId, c.titulo, c.duracion, c.explicita, al.titulo AS album, c.Album_albumId AS albumId
    FROM soundwave.Cancion c
    JOIN soundwave.Album al ON c.Album_albumId = al.albumId
    WHERE c.eliminado = 0 OR c.eliminado IS NULL;
END;
GO

-- 3. Actualizar Canción
CREATE OR ALTER PROCEDURE soundwave.SP_ActualizarCancion
    @cancionId INT,
    @titulo VARCHAR(100),
    @duracion INT,
    @explicita BIT,
    @albumId INT
AS
BEGIN
    UPDATE soundwave.Cancion
    SET titulo = @titulo,
        duracion = @duracion,
        explicita = @explicita,
        Album_albumId = @albumId
    WHERE cancionId = @cancionId;
END;
GO

-- 4. Borrado Lógico Canción (Mover a la papelera)
CREATE OR ALTER PROCEDURE soundwave.SP_EliminarCancion
    @cancionId INT
AS
BEGIN
    UPDATE soundwave.Cancion
    SET eliminado = 1
    WHERE cancionId = @cancionId;
END;
GO

-- 5. Consultar Canciones Eliminadas (Papelera)
CREATE OR ALTER PROCEDURE soundwave.SP_ConsultarCancionesEliminadas
AS
BEGIN
    SELECT c.cancionId, c.titulo, c.duracion, c.explicita, al.titulo AS album, c.Album_albumId AS albumId
    FROM soundwave.Cancion c
    JOIN soundwave.Album al ON c.Album_albumId = al.albumId
    WHERE c.eliminado = 1;
END;
GO

-- 6. Restaurar Canción
CREATE OR ALTER PROCEDURE soundwave.SP_RestaurarCancion
    @cancionId INT
AS
BEGIN
    UPDATE soundwave.Cancion
    SET eliminado = 0
    WHERE cancionId = @cancionId;
END;
GO

-- 7. Borrado Físico Permanente Canción
CREATE OR ALTER PROCEDURE soundwave.SP_EliminarFisicoCancion
    @cancionId INT
AS
BEGIN
    -- Limpieza previa de tablas hijas para evitar fallos de clave foránea
    DELETE FROM soundwave.CancionGenero WHERE Cancion_cancionId = @cancionId;
    DELETE FROM soundwave.PlaylistCancion WHERE Cancion_cancionId = @cancionId;
    DELETE FROM soundwave.Reproduccion WHERE Cancion_cancionId = @cancionId;
    DELETE FROM soundwave.Regalia WHERE Cancion_cancionId = @cancionId;
    DELETE FROM soundwave.UsuarioLike WHERE Cancion_cancionId = @cancionId;

    DELETE FROM soundwave.Cancion
    WHERE cancionId = @cancionId AND eliminado = 1;
END;
GO


-- =======================================================================
-- PROCEDIMIENTOS ALMACENADOS PARA LA TABLA: Playlist
-- =======================================================================

-- 1. Insertar Playlist
CREATE OR ALTER PROCEDURE soundwave.SP_InsertarPlaylist
    @nombre VARCHAR(100),
    @privacidad VARCHAR(20),
    @usuarioId INT
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO soundwave.Playlist (nombre, privacidad, Usuario_usuarioId, fechaCreacion, eliminado)
    VALUES (@nombre, @privacidad, @usuarioId, GETDATE(), 0);
    SELECT SCOPE_IDENTITY() AS playlistId;
END;
GO

-- 2. Consultar Playlists Activas
CREATE OR ALTER PROCEDURE soundwave.SP_ConsultarPlaylists
AS
BEGIN
    SELECT p.playlistId, p.nombre, p.privacidad, u.nombre + ' ' + u.apellido AS creador, p.Usuario_usuarioId AS usuarioId
    FROM soundwave.Playlist p
    JOIN soundwave.Usuario u ON p.Usuario_usuarioId = u.usuarioId
    WHERE p.eliminado = 0 OR p.eliminado IS NULL;
END;
GO

-- 3. Actualizar Playlist
CREATE OR ALTER PROCEDURE soundwave.SP_ActualizarPlaylist
    @playlistId INT,
    @nombre VARCHAR(100),
    @privacidad VARCHAR(20),
    @usuarioId INT
AS
BEGIN
    UPDATE soundwave.Playlist
    SET nombre = @nombre,
        privacidad = @privacidad,
        Usuario_usuarioId = @usuarioId
    WHERE playlistId = @playlistId;
END;
GO

-- 4. Borrado Lógico Playlist (Mover a la papelera)
CREATE OR ALTER PROCEDURE soundwave.SP_EliminarPlaylist
    @playlistId INT
AS
BEGIN
    UPDATE soundwave.Playlist
    SET eliminado = 1
    WHERE playlistId = @playlistId;
END;
GO

-- 5. Consultar Playlists Eliminadas (Papelera)
CREATE OR ALTER PROCEDURE soundwave.SP_ConsultarPlaylistsEliminadas
AS
BEGIN
    SELECT p.playlistId, p.nombre, p.privacidad, u.nombre + ' ' + u.apellido AS creador, p.Usuario_usuarioId AS usuarioId
    FROM soundwave.Playlist p
    JOIN soundwave.Usuario u ON p.Usuario_usuarioId = u.usuarioId
    WHERE p.eliminado = 1;
END;
GO

-- 6. Restaurar Playlist
CREATE OR ALTER PROCEDURE soundwave.SP_RestaurarPlaylist
    @playlistId INT
AS
BEGIN
    UPDATE soundwave.Playlist
    SET eliminado = 0
    WHERE playlistId = @playlistId;
END;
GO

-- 7. Borrado Físico Permanente Playlist
CREATE OR ALTER PROCEDURE soundwave.SP_EliminarFisicoPlaylist
    @playlistId INT
AS
BEGIN
    -- Limpieza previa de canciones asociadas a la playlist
    DELETE FROM soundwave.PlaylistCancion WHERE Playlist_playlistId = @playlistId;

    DELETE FROM soundwave.Playlist
    WHERE playlistId = @playlistId AND eliminado = 1;
END;
GO
