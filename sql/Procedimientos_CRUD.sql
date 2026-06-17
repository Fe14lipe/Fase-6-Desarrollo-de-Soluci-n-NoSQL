USE SoundWave;
GO

-- =======================================================================
-- PROCEDIMIENTOS ALMACENADOS ACTUALIZADOS PARA LA TABLA Discografica
-- INCLUYE SOPORTE PARA LA PAPELERA DE RECICLAJE (SOFT DELETE) EN EL ESQUEMA soundwave
-- =======================================================================

-- 1. Procedimiento para CREAR (Insertar registro activo)
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

-- 2. Procedimiento para LEER ACTIVOS (Consultar todos los no eliminados)
CREATE OR ALTER PROCEDURE soundwave.SP_ConsultarDiscograficas
AS
BEGIN
    SELECT discograficaId, nombre, pais, fechaFundacion
    FROM soundwave.Discografica
    WHERE eliminado = 0 OR eliminado IS NULL;
END;
GO

-- 3. Procedimiento para ACTUALIZAR
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

-- 4. Procedimiento para BORRADO LÓGICO (Mover a la Papelera - Soft Delete)
CREATE OR ALTER PROCEDURE soundwave.SP_EliminarDiscografica
    @nombre VARCHAR(100)
AS
BEGIN
    UPDATE soundwave.Discografica
    SET eliminado = 1
    WHERE LOWER(nombre) = LOWER(@nombre);
END;
GO

-- 5. Procedimiento para LISTAR PAPELERA (Consultar eliminados lógicos)
CREATE OR ALTER PROCEDURE soundwave.SP_ConsultarDiscograficasEliminadas
AS
BEGIN
    SELECT discograficaId, nombre, pais, fechaFundacion
    FROM soundwave.Discografica
    WHERE eliminado = 1;
END;
GO

-- 6. Procedimiento para RESTAURAR REGISTRO (Sacar de la papelera)
CREATE OR ALTER PROCEDURE soundwave.SP_RestaurarDiscografica
    @nombre VARCHAR(100)
AS
BEGIN
    UPDATE soundwave.Discografica
    SET eliminado = 0
    WHERE LOWER(nombre) = LOWER(@nombre);
END;
GO

-- 7. Procedimiento para BORRADO FÍSICO PERMANENTE (Hard Delete)
CREATE OR ALTER PROCEDURE soundwave.SP_EliminarFisicoDiscografica
    @nombre VARCHAR(100)
AS
BEGIN
    DELETE FROM soundwave.Discografica
    WHERE LOWER(nombre) = LOWER(@nombre) AND eliminado = 1;
END;
GO
