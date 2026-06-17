USE master;
GO

-- 1. CREACIÓN DE LA BASE DE DATOS
IF DB_ID('SoundWave') IS NOT NULL
BEGIN
    ALTER DATABASE SoundWave SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE SoundWave;
END
GO

CREATE DATABASE SoundWave;
GO

USE SoundWave;
GO

-- 2. CREACIÓN DEL ESQUEMA
CREATE SCHEMA soundwave;
GO

-- =======================================================================
-- CORRECCIÓN DEL DISEÑO LÓGICO Y FÍSICO (FEEDBACK FASE 2)
-- Se separan los planes y las suscripciones para mantener un historial y
-- mejorar la trazabilidad de los pagos y los cambios de plan.
-- =======================================================================

CREATE TABLE soundwave.PlanSuscripcion (
    planId INT IDENTITY(1,1) PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL CHECK (nombre IN ('Gratis', 'Premium')),
    precioMensual DECIMAL(10,2) NOT NULL,
    descripcion VARCHAR(255)
);

CREATE TABLE soundwave.Usuario (
    usuarioId INT IDENTITY(1,1) PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL,
    apellido VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    contraseña VARCHAR(255) NOT NULL,
    pais VARCHAR(50),
    fechaRegistro DATETIME DEFAULT GETDATE(),
    estado VARCHAR(20) CHECK (estado IN ('Activa', 'Inactiva', 'Suspendida')) DEFAULT 'Activa'
);

-- Tabla de Suscripción mejorada para trazabilidad
CREATE TABLE soundwave.Suscripcion (
    suscripcionId INT IDENTITY(1,1) PRIMARY KEY,
    Usuario_usuarioId INT NOT NULL FOREIGN KEY REFERENCES soundwave.Usuario(usuarioId),
    Plan_planId INT NOT NULL FOREIGN KEY REFERENCES soundwave.PlanSuscripcion(planId),
    fechaInicio DATETIME NOT NULL DEFAULT GETDATE(),
    fechaFin DATETIME,
    estado VARCHAR(20) CHECK (estado IN ('Activa', 'Cancelada', 'Expirada')) DEFAULT 'Activa'
);

CREATE TABLE soundwave.Pago (
    pagoId INT IDENTITY(1,1) PRIMARY KEY,
    monto DECIMAL(10,2) NOT NULL,
    fechaPago DATETIME DEFAULT GETDATE(),
    metodoPago VARCHAR(50) CHECK (metodoPago IN ('Tarjeta', 'Transferencia')),
    estado VARCHAR(20) CHECK (estado IN ('Aprobado', 'Pendiente', 'Rechazado')),
    Suscripcion_suscripcionId INT NOT NULL FOREIGN KEY REFERENCES soundwave.Suscripcion(suscripcionId)
);

CREATE TABLE soundwave.Discografica (
    discograficaId INT IDENTITY(1,1) PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    pais VARCHAR(50),
    fechaFundacion DATE,
    eliminado BIT DEFAULT 0
);

CREATE TABLE soundwave.Artista (
    artistaId INT IDENTITY(1,1) PRIMARY KEY,
    nombreArtistico VARCHAR(100) NOT NULL,
    pais VARCHAR(50),
    fechaInicio DATE,
    Discografica_discograficaId INT FOREIGN KEY REFERENCES soundwave.Discografica(discograficaId)
);

CREATE TABLE soundwave.Album (
    albumId INT IDENTITY(1,1) PRIMARY KEY,
    titulo VARCHAR(100) NOT NULL,
    fechaLanzamiento DATE,
    Artista_artistaId INT NOT NULL FOREIGN KEY REFERENCES soundwave.Artista(artistaId)
);

CREATE TABLE soundwave.Genero (
    generoId INT IDENTITY(1,1) PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE soundwave.Cancion (
    cancionId INT IDENTITY(1,1) PRIMARY KEY,
    titulo VARCHAR(100) NOT NULL,
    duracion INT NOT NULL, -- en segundos
    explicita BIT DEFAULT 0,
    Album_albumId INT NOT NULL FOREIGN KEY REFERENCES soundwave.Album(albumId)
);

CREATE TABLE soundwave.CancionGenero (
    Cancion_cancionId INT NOT NULL FOREIGN KEY REFERENCES soundwave.Cancion(cancionId),
    Genero_generoId INT NOT NULL FOREIGN KEY REFERENCES soundwave.Genero(generoId),
    PRIMARY KEY (Cancion_cancionId, Genero_generoId)
);

CREATE TABLE soundwave.Playlist (
    playlistId INT IDENTITY(1,1) PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    fechaCreacion DATETIME DEFAULT GETDATE(),
    privacidad VARCHAR(20) CHECK (privacidad IN ('Privada', 'Pública')) DEFAULT 'Privada',
    Usuario_usuarioId INT NOT NULL FOREIGN KEY REFERENCES soundwave.Usuario(usuarioId)
);

CREATE TABLE soundwave.PlaylistCancion (
    Playlist_playlistId INT NOT NULL FOREIGN KEY REFERENCES soundwave.Playlist(playlistId),
    Cancion_cancionId INT NOT NULL FOREIGN KEY REFERENCES soundwave.Cancion(cancionId),
    fechaAgregado DATETIME DEFAULT GETDATE(),
    PRIMARY KEY (Playlist_playlistId, Cancion_cancionId)
);

CREATE TABLE soundwave.Reproduccion (
    reproduccionId INT IDENTITY(1,1) PRIMARY KEY,
    fechaHora DATETIME DEFAULT GETDATE(),
    duracionEscuchada INT,
    dispositivo VARCHAR(50),
    Cancion_cancionId INT NOT NULL FOREIGN KEY REFERENCES soundwave.Cancion(cancionId),
    Usuario_usuarioId INT NOT NULL FOREIGN KEY REFERENCES soundwave.Usuario(usuarioId)
);

CREATE TABLE soundwave.Regalia (
    regaliaId INT IDENTITY(1,1) PRIMARY KEY,
    montoRegalia DECIMAL(10,4),
    fechaCalculo DATE,
    Cancion_cancionId INT NOT NULL FOREIGN KEY REFERENCES soundwave.Cancion(cancionId)
);

CREATE TABLE soundwave.UsuarioArtista (
    Usuario_usuarioId INT NOT NULL FOREIGN KEY REFERENCES soundwave.Usuario(usuarioId),
    Artista_artistaId INT NOT NULL FOREIGN KEY REFERENCES soundwave.Artista(artistaId),
    fechaSeguimiento DATETIME DEFAULT GETDATE(),
    PRIMARY KEY (Usuario_usuarioId, Artista_artistaId)
);

CREATE TABLE soundwave.UsuarioLike (
    Usuario_usuarioId INT NOT NULL FOREIGN KEY REFERENCES soundwave.Usuario(usuarioId),
    Cancion_cancionId INT NOT NULL FOREIGN KEY REFERENCES soundwave.Cancion(cancionId),
    fechaLike DATETIME DEFAULT GETDATE(),
    PRIMARY KEY (Usuario_usuarioId, Cancion_cancionId)
);
GO

-- =======================================================================
-- CREACIÓN DE ÍNDICES PARA MEJORAR RENDIMIENTO
-- =======================================================================
CREATE INDEX IX_Reproduccion_fechaHora ON soundwave.Reproduccion(fechaHora);
CREATE INDEX IX_Cancion_titulo ON soundwave.Cancion(titulo);
CREATE INDEX IX_Suscripcion_Estado ON soundwave.Suscripcion(estado);
CREATE INDEX IX_Usuario_Email ON soundwave.Usuario(email);
CREATE INDEX IX_Playlist_Usuario ON soundwave.Playlist(Usuario_usuarioId);
GO

-- =======================================================================
-- CREACIÓN DE LOGINS Y USUARIOS DE BASE DE DATOS
-- =======================================================================
USE master;
GO
-- Crear Logins de Servidor
IF NOT EXISTS (SELECT * FROM sys.server_principals WHERE name = 'AdminSoundWave')
BEGIN
    CREATE LOGIN AdminSoundWave WITH PASSWORD = 'soundwave12345';
END
IF NOT EXISTS (SELECT * FROM sys.server_principals WHERE name = 'AppUserSoundWave')
BEGIN
    CREATE LOGIN AppUserSoundWave WITH PASSWORD = 'hellouser';
END
GO

USE SoundWave;
GO
-- Crear Usuarios de Base de Datos y asignar roles/permisos
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = 'AdminSoundWave')
BEGIN
    CREATE USER AdminSoundWave FOR LOGIN AdminSoundWave;
    ALTER ROLE db_owner ADD MEMBER AdminSoundWave;
END

IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = 'AppUserSoundWave')
BEGIN
    CREATE USER AppUserSoundWave FOR LOGIN AppUserSoundWave;
    ALTER ROLE db_datareader ADD MEMBER AppUserSoundWave;
    ALTER ROLE db_datawriter ADD MEMBER AppUserSoundWave;
    -- Permiso para ejecutar procedimientos almacenados en el esquema soundwave
    GRANT EXECUTE ON SCHEMA::soundwave TO AppUserSoundWave;
END
GO

-- =======================================================================
-- IMPLEMENTACIÓN DE REGLAS DE NEGOCIO (TRIGGERS Y LOGS)
-- =======================================================================

-- Tabla para simular el envío de correos / notificaciones
CREATE TABLE soundwave.NotificacionLog (
    notificacionId INT IDENTITY(1,1) PRIMARY KEY,
    usuarioId INT,
    asunto VARCHAR(100),
    mensaje VARCHAR(255),
    fechaEnvio DATETIME DEFAULT GETDATE()
);
GO

-- Regla de Negocio: Un usuario solo puede tener un plan de suscripción activo a la vez
CREATE TRIGGER TRG_CheckActiveSubscription
ON soundwave.Suscripcion
AFTER INSERT, UPDATE
AS
BEGIN
    IF EXISTS (
        SELECT Usuario_usuarioId
        FROM soundwave.Suscripcion
        WHERE estado = 'Activa'
        GROUP BY Usuario_usuarioId
        HAVING COUNT(*) > 1
    )
    BEGIN
        RAISERROR('El usuario ya tiene una suscripción activa. No puede tener múltiples suscripciones activas al mismo tiempo.', 16, 1);
        ROLLBACK TRANSACTION;
        RETURN;
    END
END;
GO

-- Requerimiento de notificación: Enviar correo al pasar a Premium (simulado)
CREATE TRIGGER TRG_NotificarPremium
ON soundwave.Suscripcion
AFTER INSERT, UPDATE
AS
BEGIN
    DECLARE @usuarioId INT, @planId INT, @estado VARCHAR(20), @insertedPlanNombre VARCHAR(50);
    
    SELECT @usuarioId = i.Usuario_usuarioId, @planId = i.Plan_planId, @estado = i.estado
    FROM inserted i;

    SELECT @insertedPlanNombre = nombre FROM soundwave.PlanSuscripcion WHERE planId = @planId;

    IF @estado = 'Activa' AND @insertedPlanNombre = 'Premium'
    BEGIN
        INSERT INTO soundwave.NotificacionLog (usuarioId, asunto, mensaje)
        VALUES (@usuarioId, 'Bienvenido a Premium', '¡Bienvenido a SoundWave Premium! Su pago ha sido confirmado. Disfrute de música sin anuncios.');
    END
END;
GO

-- Regla de Negocio: No se puede eliminar el registro de un artista si este tiene canciones vinculadas
CREATE TRIGGER TRG_PreventArtistDelete
ON soundwave.Artista
INSTEAD OF DELETE
AS
BEGIN
    IF EXISTS (
        SELECT 1
        FROM deleted d
        JOIN soundwave.Album a ON d.artistaId = a.Artista_artistaId
        JOIN soundwave.Cancion c ON a.albumId = c.Album_albumId
    )
    BEGIN
        RAISERROR('No se puede eliminar el artista porque tiene canciones y álbumes vinculados en la plataforma.', 16, 1);
        ROLLBACK TRANSACTION;
        RETURN;
    END

    -- Si no tiene canciones ni álbumes, se permite eliminar
    DELETE FROM soundwave.Artista WHERE artistaId IN (SELECT artistaId FROM deleted);
END;
GO

-- =======================================================================
-- CARGA DE DATOS (MOCK DATA - PROMPT IA)
-- =======================================================================

-- 1. Planes
INSERT INTO soundwave.PlanSuscripcion (nombre, precioMensual, descripcion) VALUES 
('Gratis', 0.00, 'Música con anuncios, saltos limitados'),
('Premium', 5.99, 'Música sin anuncios, descargas offline, audio HQ');

-- 2. Usuarios
INSERT INTO soundwave.Usuario (nombre, apellido, email, contraseña, pais) VALUES 
('Benjamin', 'Perez', 'benjamin@udla.edu.ec', 'hash_pass_1', 'Ecuador'),
('Maria', 'Gomez', 'maria.gomez@gmail.com', 'hash_pass_2', 'Colombia'),
('Carlos', 'Santana', 'carlos.sant@yahoo.com', 'hash_pass_3', 'Mexico'),
('Admin', 'SoundWave', 'admin@soundwave.com', 'admin_hash', 'Ecuador');

-- 3. Suscripciones (Benja Premium, Maria Gratis, Carlos Premium)
INSERT INTO soundwave.Suscripcion (Usuario_usuarioId, Plan_planId, fechaInicio, estado) VALUES 
(1, 2, '2024-01-01', 'Activa'),
(2, 1, '2024-01-15', 'Activa'),
(3, 2, '2024-02-01', 'Activa');

-- 4. Pagos
INSERT INTO soundwave.Pago (monto, fechaPago, metodoPago, estado, Suscripcion_suscripcionId) VALUES 
(5.99, '2024-01-01', 'Tarjeta', 'Aprobado', 1),
(5.99, '2024-02-01', 'Transferencia', 'Aprobado', 3);

-- 5. Discográficas
INSERT INTO soundwave.Discografica (nombre, pais, fechaFundacion) VALUES 
('Rimas Entertainment', 'Puerto Rico', '2014-01-01'),
('Warner Records', 'USA', '1958-03-01'),
('Independiente', 'Global', '2000-01-01');

-- 6. Artistas
INSERT INTO soundwave.Artista (nombreArtistico, pais, fechaInicio, Discografica_discograficaId) VALUES 
('Bad Bunny', 'Puerto Rico', '2016-01-01', 1),
('Dua Lipa', 'Reino Unido', '2015-01-01', 2),
('Mora', 'Puerto Rico', '2017-01-01', 1),
('Banda Local EC', 'Ecuador', '2020-01-01', 3);

-- 7. Álbumes
INSERT INTO soundwave.Album (titulo, fechaLanzamiento, Artista_artistaId) VALUES 
('Un Verano Sin Ti', '2022-05-06', 1),
('Future Nostalgia', '2020-03-27', 2),
('Microdosis', '2022-04-01', 3),
('Sencillos EC', '2023-01-01', 4);

-- 8. Géneros
INSERT INTO soundwave.Genero (nombre) VALUES 
('Reggaeton'), ('Pop'), ('Urbano'), ('Indie'), ('Dance');

-- 9. Canciones
INSERT INTO soundwave.Cancion (titulo, duracion, explicita, Album_albumId) VALUES 
('Me Porto Bonito', 178, 1, 1),
('Tití Me Preguntó', 243, 1, 1),
('Levitating', 203, 0, 2),
('Don''t Start Now', 183, 0, 2),
('La Inocente', 200, 1, 3),
('Volando', 215, 0, 4);

-- 10. CancionGenero
INSERT INTO soundwave.CancionGenero (Cancion_cancionId, Genero_generoId) VALUES 
(1, 1), (1, 3), (2, 1), (3, 2), (3, 5), (4, 2), (5, 1), (6, 4);

-- 11. Playlists
INSERT INTO soundwave.Playlist (nombre, privacidad, Usuario_usuarioId) VALUES 
('Perreo Intenso 2024', 'Pública', 1),
('Pop Vibes', 'Pública', 2),
('Mis Favoritas', 'Privada', 3);

-- 12. PlaylistCancion
INSERT INTO soundwave.PlaylistCancion (Playlist_playlistId, Cancion_cancionId) VALUES 
(1, 1), (1, 2), (1, 5),
(2, 3), (2, 4),
(3, 1), (3, 6);

-- 13. Reproducciones (Data mockeada para los reportes)
DECLARE @i INT = 0;
WHILE @i < 10
BEGIN
    INSERT INTO soundwave.Reproduccion (fechaHora, duracionEscuchada, dispositivo, Cancion_cancionId, Usuario_usuarioId)
    VALUES (GETDATE(), 178, 'iPhone', 1, 1),
           (GETDATE(), 203, 'Android', 3, 2),
           (GETDATE(), 243, 'Web', 2, 3);
    SET @i = @i + 1;
END;
GO

-- =======================================================================
-- PROCEDIMIENTOS ALMACENADOS Y CONSULTAS PARA REPORTES
-- =======================================================================

-- 1. Top Canciones: Lista de las 50 canciones más reproducidas en el mes actual
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
    JOIN soundwave.Reproduccion r ON c.cancionId = r.Cancion_cancionId
    WHERE MONTH(r.fechaHora) = MONTH(GETDATE()) 
      AND YEAR(r.fechaHora) = YEAR(GETDATE())
    GROUP BY c.titulo, a.nombreArtistico
    ORDER BY TotalReproducciones DESC;
END;
GO

-- 2. Reporte de Ingresos Premium: Total recaudado en un periodo
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

-- 3. Estadísticas de Artista: Reproducciones totales
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

-- 4. Contenido de Playlist
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
