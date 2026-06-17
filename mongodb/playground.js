// =======================================================================
// SCRIPT MONGODB PLAYGROUND (FASE 6 - SOUNDWAVE)
// Ejecutar utilizando MongoDB Playground en VS Code o MongoDB Compass
// =======================================================================

// 1. Selección y Creación de la Base de Datos
use('SoundWave');

// Limpiar base de datos previa para asegurar una ejecución limpia
db.dropDatabase();
use('SoundWave');

// 2. Creación de Colecciones con Validación de Esquema (Opcional - Estilo Académico)
db.createCollection('discograficas', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['nombre', 'pais', 'eliminado'],
      properties: {
        discograficaId: { bsonType: 'int' },
        nombre: { bsonType: 'string' },
        pais: { bsonType: 'string' },
        fechaFundacion: { bsonType: ['date', 'null'] },
        eliminado: { bsonType: 'bool' }
      }
    }
  }
});

db.createCollection('artistas');
db.createCollection('albums');
db.createCollection('playlists');
db.createCollection('usuarios');
db.createCollection('reproducciones');

// 3. Creación de Índices
// Índice único para búsquedas de usuario por correo electrónico
db.usuarios.createIndex({ "email": 1 }, { unique: true });

// Índices simples y compuestos para acelerar reportes e históricos
db.reproducciones.createIndex({ "fechaHora": -1 });
db.playlists.createIndex({ "usuarioId": 1 });
db.albums.createIndex({ "canciones.titulo": 1 });

// 4. Inserción de Datos Iniciales (Mock Data)

// 4.1. Inserción en Discográficas
db.discograficas.insertMany([
  {
    discograficaId: 1,
    nombre: "Rimas Entertainment",
    pais: "Puerto Rico",
    fechaFundacion: ISODate("2014-01-01T00:00:00Z"),
    eliminado: false
  },
  {
    discograficaId: 2,
    nombre: "Warner Records",
    pais: "USA",
    fechaFundacion: ISODate("1958-03-01T00:00:00Z"),
    eliminado: false
  },
  {
    discograficaId: 3,
    nombre: "Independiente",
    pais: "Global",
    fechaFundacion: ISODate("2000-01-01T00:00:00Z"),
    eliminado: false
  }
]);

// 4.2. Inserción en Artistas
db.artistas.insertMany([
  {
    artistaId: 1,
    nombreArtistico: "Bad Bunny",
    pais: "Puerto Rico",
    fechaInicio: ISODate("2016-01-01T00:00:00Z"),
    discograficaId: 1,
    discograficaNombre: "Rimas Entertainment",
    eliminado: false
  },
  {
    artistaId: 2,
    nombreArtistico: "Dua Lipa",
    pais: "Reino Unido",
    fechaInicio: ISODate("2015-01-01T00:00:00Z"),
    discograficaId: 2,
    discograficaNombre: "Warner Records",
    eliminado: false
  },
  {
    artistaId: 3,
    nombreArtistico: "Mora",
    pais: "Puerto Rico",
    fechaInicio: ISODate("2017-01-01T00:00:00Z"),
    discograficaId: 1,
    discograficaNombre: "Rimas Entertainment",
    eliminado: false
  },
  {
    artistaId: 4,
    nombreArtistico: "Banda Local EC",
    pais: "Ecuador",
    fechaInicio: ISODate("2020-01-01T00:00:00Z"),
    discograficaId: 3,
    discograficaNombre: "Independiente",
    eliminado: false
  }
]);

// 4.3. Inserción en Albums (con Canciones Embebidas y Géneros)
db.albums.insertMany([
  {
    albumId: 1,
    titulo: "Un Verano Sin Ti",
    fechaLanzamiento: ISODate("2022-05-06T00:00:00Z"),
    artistaId: 1,
    artistaNombre: "Bad Bunny",
    canciones: [
      {
        cancionId: 1,
        titulo: "Me Porto Bonito",
        duracion: 178,
        explicita: true,
        eliminado: false,
        generos: ["Reggaeton", "Urbano"]
      },
      {
        cancionId: 2,
        titulo: "Tití Me Preguntó",
        duracion: 243,
        explicita: true,
        eliminado: false,
        generos: ["Reggaeton"]
      }
    ]
  },
  {
    albumId: 2,
    titulo: "Future Nostalgia",
    fechaLanzamiento: ISODate("2020-03-27T00:00:00Z"),
    artistaId: 2,
    artistaNombre: "Dua Lipa",
    canciones: [
      {
        cancionId: 3,
        titulo: "Levitating",
        duracion: 203,
        explicita: false,
        eliminado: false,
        generos: ["Pop", "Dance"]
      },
      {
        cancionId: 4,
        titulo: "Don't Start Now",
        duracion: 183,
        explicita: false,
        eliminado: false,
        generos: ["Pop"]
      }
    ]
  },
  {
    albumId: 3,
    titulo: "Microdosis",
    fechaLanzamiento: ISODate("2022-04-01T00:00:00Z"),
    artistaId: 3,
    artistaNombre: "Mora",
    canciones: [
      {
        cancionId: 5,
        titulo: "La Inocente",
        duracion: 200,
        explicita: true,
        eliminado: false,
        generos: ["Reggaeton", "Urbano"]
      }
    ]
  }
]);

// 4.4. Inserción en Usuarios (con Suscripciones y Pagos Embebidos)
db.usuarios.insertMany([
  {
    usuarioId: 1,
    nombre: "Benjamin",
    apellido: "Perez",
    email: "benjamin@udla.edu.ec",
    contraseña: "hash_pass_1",
    pais: "Ecuador",
    fechaRegistro: ISODate("2024-01-01T00:00:00Z"),
    estado: "Activa",
    telefono: "0960786020",
    eliminado: false,
    suscripciones: [
      {
        suscripcionId: 1,
        fechaInicio: ISODate("2024-01-01T00:00:00Z"),
        fechaFin: null,
        estado: "Activa",
        plan: {
          planId: 2,
          nombre: "Premium",
          precioMensual: 5.99,
          descripcion: "Música sin anuncios, descargas offline, audio HQ"
        },
        pagos: [
          {
            pagoId: 1,
            monto: 5.99,
            fechaPago: ISODate("2024-01-01T00:00:00Z"),
            metodoPago: "Tarjeta",
            estado: "Aprobado"
          }
        ]
      }
    ]
  },
  {
    usuarioId: 2,
    nombre: "Maria",
    apellido: "Gomez",
    email: "maria.gomez@gmail.com",
    contraseña: "hash_pass_2",
    pais: "Colombia",
    fechaRegistro: ISODate("2024-01-15T00:00:00Z"),
    estado: "Activa",
    telefono: "0999999998",
    eliminado: false,
    suscripciones: [
      {
        suscripcionId: 2,
        fechaInicio: ISODate("2024-01-15T00:00:00Z"),
        fechaFin: null,
        estado: "Activa",
        plan: {
          planId: 1,
          nombre: "Gratis",
          precioMensual: 0.00,
          descripcion: "Música con anuncios, saltos limitados"
        },
        pagos: []
      }
    ]
  }
]);

// 4.5. Inserción en Playlists
db.playlists.insertMany([
  {
    playlistId: 1,
    nombre: "Perreo Intenso 2024",
    fechaCreacion: ISODate("2024-01-01T00:00:00Z"),
    privacidad: "Pública",
    usuarioId: 1,
    usuarioNombre: "Benjamin Perez",
    eliminado: false,
    canciones: [
      {
        cancionId: 1,
        titulo: "Me Porto Bonito",
        duracion: 178,
        albumId: 1,
        albumTitulo: "Un Verano Sin Ti",
        artistaNombre: "Bad Bunny",
        fechaAgregado: ISODate("2024-01-01T12:00:00Z")
      },
      {
        cancionId: 2,
        titulo: "Tití Me Preguntó",
        duracion: 243,
        albumId: 1,
        albumTitulo: "Un Verano Sin Ti",
        artistaNombre: "Bad Bunny",
        fechaAgregado: ISODate("2024-01-01T12:05:00Z")
      }
    ]
  }
]);

// 4.6. Inserción en Reproducciones
db.reproducciones.insertMany([
  {
    reproduccionId: 1,
    fechaHora: ISODate("2026-06-16T19:00:00Z"),
    duracionEscuchada: 178,
    dispositivo: "iPhone",
    usuarioId: 1,
    cancionId: 1,
    cancionTitulo: "Me Porto Bonito",
    artistaNombre: "Bad Bunny"
  },
  {
    reproduccionId: 2,
    fechaHora: ISODate("2026-06-16T19:05:00Z"),
    duracionEscuchada: 203,
    dispositivo: "Android",
    usuarioId: 2,
    cancionId: 3,
    cancionTitulo: "Levitating",
    artistaNombre: "Dua Lipa"
  }
]);

// =======================================================================
// 5. OPERACIONES CRUD (Demostración)
// =======================================================================

// --- CREATE (Insertar) ---
// Insertar una nueva discográfica
db.discograficas.insertOne({
  discograficaId: 4,
  nombre: "Sony Music Latin",
  pais: "USA",
  fechaFundacion: ISODate("1980-06-01T00:00:00Z"),
  eliminado: false
});

// --- READ (Leer) ---
// Obtener todos los usuarios que tienen una cuenta Activa y viven en Ecuador
db.usuarios.find({ estado: "Activa", pais: "Ecuador" });

// --- UPDATE (Actualizar) ---
// Modificar el plan de suscripción de un usuario (de Gratis a Premium)
db.usuarios.updateOne(
  { email: "maria.gomez@gmail.com" },
  {
    $set: {
      "suscripciones.$[elem].estado": "Cancelada",
      "suscripciones.$[elem].fechaFin": ISODate("2026-06-16T00:00:00Z")
    }
  },
  { arrayFilters: [{ "elem.estado": "Activa" }] }
);

// Agregar la nueva suscripción Premium activa con su pago
db.usuarios.updateOne(
  { email: "maria.gomez@gmail.com" },
  {
    $push: {
      suscripciones: {
        suscripcionId: 3,
        fechaInicio: ISODate("2026-06-16T19:15:00Z"),
        fechaFin: null,
        estado: "Activa",
        plan: {
          planId: 2,
          nombre: "Premium",
          precioMensual: 5.99,
          descripcion: "Música sin anuncios, descargas offline, audio HQ"
        },
        pagos: [
          {
            pagoId: 2,
            monto: 5.99,
            fechaPago: ISODate("2026-06-16T19:15:00Z"),
            metodoPago: "Tarjeta",
            estado: "Aprobado"
          }
        ]
      }
    }
  }
);

// --- DELETE (Borrado) ---
// Borrado Lógico (Soft Delete) de un artista (para papelera)
db.artistas.updateOne(
  { artistaId: 4 },
  { $set: { eliminado: true } }
);

// Borrado Físico (Hard Delete) de la discográfica de pruebas
db.discograficas.deleteOne({ discograficaId: 4 });


// =======================================================================
// 6. BÚSQUEDAS AVANZADAS Y AGREGACIONES
// =======================================================================

// --- 6.1. Búsqueda de documentos con índices (Hint) ---
// Forzar búsqueda usando el índice único de email para verificar rendimiento
db.usuarios.find({ email: "benjamin@udla.edu.ec" }).hint({ email: 1 });

// --- 6.2. Consultas con lookup (Lookup 1: Artistas con su Discográfica) ---
db.artistas.aggregate([
  {
    $lookup: {
      from: "discograficas",
      localField: "discograficaId",
      foreignField: "discograficaId",
      as: "discografica_detalle"
    }
  },
  {
    $unwind: {
      path: "$discografica_detalle",
      preserveNullAndEmptyArrays: true
    }
  },
  {
    $project: {
      _id: 0,
      artistaId: 1,
      nombreArtistico: 1,
      pais: 1,
      discograficaNombre: "$discografica_detalle.nombre",
      discograficaPais: "$discografica_detalle.pais"
    }
  }
]);

// --- 6.3. Consultas con lookup (Lookup 2: Playlists detallando la duración e info de sus canciones) ---
db.playlists.aggregate([
  {
    $lookup: {
      from: "albums",
      let: { canciones_ids: "$canciones.cancionId" },
      pipeline: [
        { $unwind: "$canciones" },
        {
          $match: {
            $expr: { $in: ["$canciones.cancionId", "$$canciones_ids"] }
          }
        },
        {
          $project: {
            _id: 0,
            cancionId: "$canciones.cancionId",
            titulo: "$canciones.titulo",
            duracion: "$canciones.duracion",
            artista: "$artistaNombre",
            album: "$titulo"
          }
        }
      ],
      as: "detalles_canciones"
    }
  },
  {
    $project: {
      _id: 0,
      playlistId: 1,
      nombre: 1,
      creador: "$usuarioNombre",
      privacidad: 1,
      canciones: "$detalles_canciones"
    }
  }
]);
