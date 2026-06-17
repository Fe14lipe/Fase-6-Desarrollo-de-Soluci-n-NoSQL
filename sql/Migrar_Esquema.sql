USE SoundWave;
GO

-- 1. Crear el esquema si no existe
IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'soundwave')
BEGIN
    EXEC('CREATE SCHEMA soundwave');
END
GO

-- 2. Transferir tablas del esquema dbo a soundwave (si existen en dbo)
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'PlanSuscripcion' AND SCHEMA_NAME(schema_id) = 'dbo')
    ALTER SCHEMA soundwave TRANSFER dbo.PlanSuscripcion;
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'Usuario' AND SCHEMA_NAME(schema_id) = 'dbo')
    ALTER SCHEMA soundwave TRANSFER dbo.Usuario;
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'Suscripcion' AND SCHEMA_NAME(schema_id) = 'dbo')
    ALTER SCHEMA soundwave TRANSFER dbo.Suscripcion;
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'Pago' AND SCHEMA_NAME(schema_id) = 'dbo')
    ALTER SCHEMA soundwave TRANSFER dbo.Pago;
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'Discografica' AND SCHEMA_NAME(schema_id) = 'dbo')
    ALTER SCHEMA soundwave TRANSFER dbo.Discografica;
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'Artista' AND SCHEMA_NAME(schema_id) = 'dbo')
    ALTER SCHEMA soundwave TRANSFER dbo.Artista;
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'Album' AND SCHEMA_NAME(schema_id) = 'dbo')
    ALTER SCHEMA soundwave TRANSFER dbo.Album;
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'Genero' AND SCHEMA_NAME(schema_id) = 'dbo')
    ALTER SCHEMA soundwave TRANSFER dbo.Genero;
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'Cancion' AND SCHEMA_NAME(schema_id) = 'dbo')
    ALTER SCHEMA soundwave TRANSFER dbo.Cancion;
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'CancionGenero' AND SCHEMA_NAME(schema_id) = 'dbo')
    ALTER SCHEMA soundwave TRANSFER dbo.CancionGenero;
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'Playlist' AND SCHEMA_NAME(schema_id) = 'dbo')
    ALTER SCHEMA soundwave TRANSFER dbo.Playlist;
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'PlaylistCancion' AND SCHEMA_NAME(schema_id) = 'dbo')
    ALTER SCHEMA soundwave TRANSFER dbo.PlaylistCancion;
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'Reproduccion' AND SCHEMA_NAME(schema_id) = 'dbo')
    ALTER SCHEMA soundwave TRANSFER dbo.Reproduccion;
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'Regalia' AND SCHEMA_NAME(schema_id) = 'dbo')
    ALTER SCHEMA soundwave TRANSFER dbo.Regalia;
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'UsuarioArtista' AND SCHEMA_NAME(schema_id) = 'dbo')
    ALTER SCHEMA soundwave TRANSFER dbo.UsuarioArtista;
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'UsuarioLike' AND SCHEMA_NAME(schema_id) = 'dbo')
    ALTER SCHEMA soundwave TRANSFER dbo.UsuarioLike;
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'NotificacionLog' AND SCHEMA_NAME(schema_id) = 'dbo')
    ALTER SCHEMA soundwave TRANSFER dbo.NotificacionLog;
GO

-- Asegurar que la columna eliminado existe en soundwave.Discografica
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('soundwave.Discografica') AND name = 'eliminado')
BEGIN
    ALTER TABLE soundwave.Discografica ADD eliminado BIT DEFAULT 0;
    -- Actualizar registros existentes a 0
    EXEC('UPDATE soundwave.Discografica SET eliminado = 0');
END
GO

-- 3. Eliminar procedimientos almacenados antiguos bajo dbo si existen
IF OBJECT_ID('dbo.SP_InsertarDiscografica', 'P') IS NOT NULL DROP PROCEDURE dbo.SP_InsertarDiscografica;
IF OBJECT_ID('dbo.SP_ConsultarDiscograficas', 'P') IS NOT NULL DROP PROCEDURE dbo.SP_ConsultarDiscograficas;
IF OBJECT_ID('dbo.SP_ActualizarDiscografica', 'P') IS NOT NULL DROP PROCEDURE dbo.SP_ActualizarDiscografica;
IF OBJECT_ID('dbo.SP_EliminarDiscografica', 'P') IS NOT NULL DROP PROCEDURE dbo.SP_EliminarDiscografica;
IF OBJECT_ID('dbo.SP_ConsultarDiscograficasEliminadas', 'P') IS NOT NULL DROP PROCEDURE dbo.SP_ConsultarDiscograficasEliminadas;
IF OBJECT_ID('dbo.SP_RestaurarDiscografica', 'P') IS NOT NULL DROP PROCEDURE dbo.SP_RestaurarDiscografica;
IF OBJECT_ID('dbo.SP_EliminarFisicoDiscografica', 'P') IS NOT NULL DROP PROCEDURE dbo.SP_EliminarFisicoDiscografica;
IF OBJECT_ID('dbo.SP_ReporteTopCanciones', 'P') IS NOT NULL DROP PROCEDURE dbo.SP_ReporteTopCanciones;
IF OBJECT_ID('dbo.SP_ReporteIngresosPremium', 'P') IS NOT NULL DROP PROCEDURE dbo.SP_ReporteIngresosPremium;
IF OBJECT_ID('dbo.SP_EstadisticasArtista', 'P') IS NOT NULL DROP PROCEDURE dbo.SP_EstadisticasArtista;
IF OBJECT_ID('dbo.SP_ContenidoPlaylist', 'P') IS NOT NULL DROP PROCEDURE dbo.SP_ContenidoPlaylist;
GO

-- 4. Crear los Stored Procedures bajo el esquema soundwave

-- SP_InsertarDiscografica
CREATE OR ALTER PROCEDURE soundwave.SP_InsertarDiscografica
    @nombre VARCHAR(100),
    @pais VARCHAR(50),
    @fechaFundacion DATE
AS
BEGIN
    INSERT INTO soundwave.Discografica (nombre, pais, fechaFundacion, eliminado)
    VALUES (@nombre, @pais, @fechaFundacion, 0);
END;
GO

-- SP_ConsultarDiscograficas
CREATE OR ALTER PROCEDURE soundwave.SP_ConsultarDiscograficas
AS
BEGIN
    SELECT discograficaId, nombre, pais, fechaFundacion
    FROM soundwave.Discografica
    WHERE eliminado = 0 OR eliminado IS NULL;
END;
GO

-- SP_ActualizarDiscografica
CREATE OR ALTER PROCEDURE soundwave.SP_ActualizarDiscografica
    @nombreActual VARCHAR(100),
    @nuevoNombre VARCHAR(100),
    @pais VARCHAR(50),
    @fechaFundacion DATE
AS
BEGIN
    UPDATE soundwave.Discografica
    SET nombre = @nuevoNombre,
        pais = @pais,
        fechaFundacion = @fechaFundacion
    WHERE LOWER(nombre) = LOWER(@nombreActual);
END;
GO

-- SP_EliminarDiscografica
CREATE OR ALTER PROCEDURE soundwave.SP_EliminarDiscografica
    @nombre VARCHAR(100)
AS
BEGIN
    UPDATE soundwave.Discografica
    SET eliminado = 1
    WHERE LOWER(nombre) = LOWER(@nombre);
END;
GO

-- SP_ConsultarDiscograficasEliminadas
CREATE OR ALTER PROCEDURE soundwave.SP_ConsultarDiscograficasEliminadas
AS
BEGIN
    SELECT discograficaId, nombre, pais, fechaFundacion
    FROM soundwave.Discografica
    WHERE eliminado = 1;
END;
GO

-- SP_RestaurarDiscografica
CREATE OR ALTER PROCEDURE soundwave.SP_RestaurarDiscografica
    @nombre VARCHAR(100)
AS
BEGIN
    UPDATE soundwave.Discografica
    SET eliminado = 0
    WHERE LOWER(nombre) = LOWER(@nombre);
END;
GO

-- SP_EliminarFisicoDiscografica
CREATE OR ALTER PROCEDURE soundwave.SP_EliminarFisicoDiscografica
    @nombre VARCHAR(100)
AS
BEGIN
    DELETE FROM soundwave.Discografica
    WHERE LOWER(nombre) = LOWER(@nombre) AND eliminado = 1;
END;
GO

-- SP_ReporteTopCanciones
CREATE OR ALTER PROCEDURE soundwave.SP_ReporteTopCanciones
AS
BEGIN
    SELECT TOP 50 
        c.titulo AS Cancion, 
        a.nombreArtistico AS Artista, 
        COUNT(r.reproduccionId) AS TotalReproducciones
    FROM soundwave.Cancion c
    JOIN soundwave.Album al ON c.Album_albumId = al.albumId
    JOIN soundwave.Artista a ON al.Artista_artistaId = a.artistaId
    LEFT JOIN soundwave.Reproduccion r ON c.cancionId = r.Cancion_cancionId
    WHERE MONTH(r.fechaHora) = MONTH(GETDATE()) 
      AND YEAR(r.fechaHora) = YEAR(GETDATE())
    GROUP BY c.titulo, a.nombreArtistico
    ORDER BY TotalReproducciones DESC, c.titulo ASC;
END;
GO

-- SP_ReporteIngresosPremium
CREATE OR ALTER PROCEDURE soundwave.SP_ReporteIngresosPremium
    @FechaInicio DATETIME,
    @FechaFin DATETIME
AS
BEGIN
    SELECT 
        SUM(p.monto) AS TotalRecaudadoPremium,
        COUNT(p.pagoId) AS CantidadTransacciones
    FROM soundwave.Pago p
    JOIN soundwave.Suscripcion s ON p.Suscripcion_suscripcionId = s.suscripcionId
    JOIN soundwave.PlanSuscripcion ps ON s.Plan_planId = ps.planId
    JOIN soundwave.Usuario u ON s.Usuario_usuarioId = u.usuarioId
    WHERE ps.nombre = 'Premium'
      AND p.estado = 'Aprobado'
      AND (u.eliminado = 0 OR u.eliminado IS NULL)
      AND p.fechaPago BETWEEN @FechaInicio AND @FechaFin;
END;
GO

-- SP_EstadisticasArtista
CREATE OR ALTER PROCEDURE soundwave.SP_EstadisticasArtista
    @ArtistaId INT
AS
BEGIN
    SELECT 
        a.nombreArtistico AS Artista,
        COUNT(r.reproduccionId) AS ReproduccionesGlobalesTotales
    FROM soundwave.Artista a
    JOIN soundwave.Album al ON a.artistaId = al.Artista_artistaId
    JOIN soundwave.Cancion c ON al.albumId = c.Album_albumId
    LEFT JOIN soundwave.Reproduccion r ON c.cancionId = r.Cancion_cancionId
    WHERE a.artistaId = @ArtistaId
    GROUP BY a.nombreArtistico;
END;
GO

-- SP_ContenidoPlaylist
CREATE OR ALTER PROCEDURE soundwave.SP_ContenidoPlaylist
    @PlaylistId INT
AS
BEGIN
    SELECT 
        p.nombre AS NombrePlaylist,
        c.titulo AS Cancion,
        a.nombreArtistico AS Artista,
        c.duracion AS DuracionSegundos,
        al.titulo AS Album
    FROM soundwave.Playlist p
    JOIN soundwave.PlaylistCancion pc ON p.playlistId = pc.Playlist_playlistId
    JOIN soundwave.Cancion c ON pc.Cancion_cancionId = c.cancionId
    JOIN soundwave.Album al ON c.Album_albumId = al.albumId
    JOIN soundwave.Artista a ON al.Artista_artistaId = a.artistaId
    WHERE p.playlistId = @PlaylistId
    ORDER BY pc.fechaAgregado ASC;
END;
GO
