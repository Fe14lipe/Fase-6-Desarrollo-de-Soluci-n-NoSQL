# PROYECTO INTEGRADOR: SOUNDWAVE (FASE 4)
## INFORME DE DESARROLLO Y ENTREGA ACADÉMICA

**INTEGRANTES DEL GRUPO:**
* Felipe Boada
* Matías Flores
* Ariel Tejada
* Yusely Zapata

**MATERIA:**
* Base de Datos II (UDLA)

---

### INTRODUCCIÓN

El objetivo de la Fase 4 del Proyecto Integrador "SoundWave" es la implementación de una interfaz web interactiva que permita al usuario final y a los administradores gestionar y explotar las funcionalidades más importantes del sistema directamente en una base de datos relacional activa en **SQL Server**. 

En esta fase se diseñó y configuró la conexión dinámica de datos empleando el driver ODBC y la autenticación mediante **SQL Server Login** (usuario `sa`), asegurando que las operaciones de creación, consulta, edición y eliminación (CRUD) se realicen a través de **Procedimientos Almacenados**. Adicionalmente, se implementó un sistema de **Papelera de Reciclaje (Soft Delete)** que garantiza la consistencia relacional y evita la pérdida accidental de datos.

### MANUAL DEL USUARIO

La aplicación web **SoundWave** cuenta con una barra de navegación fija que da acceso a las siguientes funcionalidades:
1. **Dashboard Principal:** Muestra el panel de control y el reporte del "Top de Canciones más Escuchadas" en tiempo real.
2. **Catálogo de Discográficas (CRUD):** 
   * **Crear:** Permite registrar una nueva discográfica a través del formulario "Nueva Discográfica" (Llama a `SP_InsertarDiscografica`).
   * **Leer:** Muestra una tabla con el ID, Nombre, País y Fecha de Fundación de las discográficas activas (Llama a `SP_ConsultarDiscograficas`).
   * **Actualizar:** Permite modificar los datos de un registro prellenado (Llama a `SP_ActualizarDiscografica`).
   * **Borrado Lógico (Papelera):** El botón "Eliminar" de la lista activa no borra físicamente el registro, sino que lo marca como inactivo y lo envía a la papelera (Llama a `SP_EliminarDiscografica`).
3. **Papelera de Reciclaje:**
   * **Restaurar:** Botón para devolver el registro temporalmente borrado al catálogo activo (Llama a `SP_RestaurarDiscografica`).
   * **Borrar Permanentemente:** Purga físicamente el registro (Llama a `SP_EliminarFisicoDiscografica`). Si tiene artistas asociados, el sistema bloquea la acción y alerta del error de integridad relacional en la base de datos.
4. **Módulos de Consulta:** Vistas de consulta para listados de **Artistas**, **Canciones** y **Usuarios** del sistema.
5. **Reportes:** Módulo que expone reportes complejos: Top 50 canciones e ingresos premium acumulados en un rango de fechas.

---

# III DESARROLLO

A continuación, se presenta el desarrollo de cada uno de los ítems solicitados:

## II.1 CONFIGURACIÓN DEL ENTORNO DE DESARROLLO
Para garantizar la portabilidad y la reproducibilidad de la solución informática en cualquier máquina local o servidor, se procedió a aislar el entorno de ejecución de Python y las librerías necesarias.

### II.1.1 Instalación de Python y Configuración del Entorno Virtual
Se instaló Python en su versión más estable en el sistema de desarrollo. A continuación, se inicializó un entorno virtual aislado dentro del directorio raíz del proyecto para evitar conflictos globales de dependencias:
```bash
# Crear entorno virtual
python -m venv .venv

# Activar entorno virtual en Windows
.venv\Scripts\activate
```

### II.1.2 Instalación de Dependencias e Instanciación del Proyecto
Se utilizó el instalador de paquetes `pip` para instalar el micro-framework de desarrollo web Flask, el conector oficial de base de datos `pyodbc` y la suite de pruebas automatizadas `pytest`. Todas estas librerías quedaron registradas en el manifiesto `requirements.txt`:
```text
Flask==3.1.3
pyodbc==5.3.0
pytest==9.0.3
```
Comando utilizado para su instalación masiva:
```bash
pip install -r requirements.txt
```

---

## II.2 DISEÑO DEL FRONTEND
El frontend de la aplicación se diseñó desde cero utilizando estándares modernos de diseño web adaptativo (responsivo) y estética oscura (*dark mode*).

### Desarrollo de Interfaces de Usuario
Se estructuraron las siguientes plantillas HTML5 utilizando el motor de renderizado **Jinja2**:
1. **base.html:** Estructura común del sitio web que contiene la barra lateral fija (*sidebar*), los scripts comunes de iconos (`Phosphor Icons`) y el contenedor dinámico para la inyección de los mensajes de notificación del sistema (*Flash Messages*).
2. **dashboard.html:** Panel analítico de inicio con una interfaz visual limpia orientada a mostrar estadísticas interactivas del negocio.
3. **index.html:** Listado tabular dinámico para las discográficas activas. Contiene un encabezado flexible con accesos a la creación de registros y a la papelera de reciclaje.
4. **papelera.html:** Interfaz dedicada para la administración de elementos eliminados lógicamente, equipada con disparadores de formularios POST seguros y alertas javascript nativas de confirmación.
5. **create.html y edit.html:** Formularios estilizados con inputs nativos validados para registrar y actualizar datos.
6. **artistas.html, canciones.html y usuarios.html:** Vistas tabulares de consulta de solo lectura, con layouts alineados a la línea estética de la aplicación.

Se integró una hoja de estilos unificada en `static/css/style.css` que utiliza variables de color CSS, fondos con gradientes lineales oscuros, bordes semitransparentes (*glassmorphism*) y transiciones fluidas de 0.2 segundos al posicionar el cursor sobre elementos interactivos (*hover effects*).

---

## II.3 DESARROLLO DEL BACKEND (PYTHON Y CONEXIÓN A SQL SERVER)
El núcleo de la aplicación web se desarrolló en Python, configurando una conexión dinámica y segura mediante la autenticación de SQL Server.

### Conexión de Datos y Lógica en app.py
Se utilizó la librería `pyodbc` para interactuar con Microsoft SQL Server. Para evitar exponer credenciales directamente en el código fuente, se parametrizó la información de conexión en el archivo JSON `config.json`. 

El backend lee dinámicamente este archivo. Si detecta los parámetros `uid` y `pwd`, autoconfigura la cadena de conexión para realizar un inicio de sesión a nivel de servidor (SQL Login), de lo contrario, aplica autenticación integrada de Windows (Trusted Connection):

```json
{
    "name_server": "DESKTOP-PIOLQJP",
    "database": "SoundWave",
    "driver": "ODBC Driver 17 for SQL Server",
    "uid": "sa",
    "pwd": "benjamin0309"
}
```

Función de conexión en `app.py`:
```python
def get_db_connection():
    # Carga config.json y evalúa si usar SQL Login
    uid = config.get('uid')
    pwd = config.get('pwd')
    if uid and pwd:
        connection_string = f'DRIVER={{{driver}}};SERVER={name_server};DATABASE={database};UID={uid};PWD={pwd};'
    else:
        connection_string = f'DRIVER={{{driver}}};SERVER={name_server};DATABASE={database};Trusted_Connection=yes;'
    return pyodbc.connect(connection_string)
```

Se diseñaron las rutas y controladores para redirigir las solicitudes HTTP (GET y POST) de los usuarios hacia consultas a la base de datos o llamadas directas a procedimientos almacenados.

---

## II.4 INTEGRACIÓN DE FUNCIONALIDADES (CRUD Y PAPELERA DE RECICLAJE)
Se implementó la lógica CRUD completa para la gestión de discográficas y se desarrolló una papelera de reciclaje que simula los flujos operativos de sistemas de producción modernos.

### Desarrollo de Operaciones de Base de Datos e Integración de Interfaz
Todas las interacciones de manipulación de datos en la tabla `Discografica` se aislaron mediante **Procedimientos Almacenados (SPs)** en SQL Server:

1. **Inserción de Registros (`SP_InsertarDiscografica`):**
   ```sql
   CREATE OR ALTER PROCEDURE SP_InsertarDiscografica
       @nombre VARCHAR(100), @pais VARCHAR(50), @fechaFundacion DATE
   AS
   BEGIN
       INSERT INTO Discografica (nombre, pais, fechaFundacion, eliminado)
       VALUES (@nombre, @pais, @fechaFundacion, 0);
   END;
   ```
2. **Listar Registros Activos (`SP_ConsultarDiscograficas`):** Filtra los registros que no han sido borrados lógicamente.
   ```sql
   CREATE OR ALTER PROCEDURE SP_ConsultarDiscograficas
   AS
   BEGIN
       SELECT discograficaId, nombre, pais, fechaFundacion
       FROM Discografica
       WHERE eliminado = 0 OR eliminado IS NULL;
   END;
   ```
3. **Borrado Lógico / Soft Delete (`SP_EliminarDiscografica`):** Al presionar "Eliminar" en la web, el SP cambia el estado a inactivo:
   ```sql
   CREATE OR ALTER PROCEDURE SP_EliminarDiscografica
       @nombre VARCHAR(100)
   AS
   BEGIN
       UPDATE Discografica SET eliminado = 1 WHERE LOWER(nombre) = LOWER(@nombre);
   END;
   ```
4. **Listar Papelera (`SP_ConsultarDiscograficasEliminadas`):**
   ```sql
   CREATE OR ALTER PROCEDURE SP_ConsultarDiscograficasEliminadas
   AS
   BEGIN
       SELECT discograficaId, nombre, pais, fechaFundacion FROM Discografica WHERE eliminado = 1;
   END;
   ```
5. **Restaurar de la Papelera (`SP_RestaurarDiscografica`):**
   ```sql
   CREATE OR ALTER PROCEDURE SP_RestaurarDiscografica
       @nombre VARCHAR(100)
   AS
   BEGIN
       UPDATE Discografica SET eliminado = 0 WHERE LOWER(nombre) = LOWER(@nombre);
   END;
   ```
6. **Borrado Físico Permanente / Hard Delete (`SP_EliminarFisicoDiscografica`):** Purga física del registro. Si hay artistas vinculados a la discográfica, la base de datos aborta la transacción debido a la restricción de llave foránea. El backend Flask captura la excepción con un bloque `try-except` y despliega un aviso rojo en pantalla: *"No se puede eliminar permanentemente: la discográfica tiene artistas vinculados en la base de datos."*

---

# IV CONCLUSIONES

1. **Seguridad y Capacidad de Abstracción con SPs:** Integrar la aplicación web consumiendo procedimientos almacenados en SQL Server reduce la superficie de ataque frente a inyecciones SQL y descentraliza la carga computacional, permitiendo que el motor de base de datos administre de forma óptima el plan de ejecución de las consultas.
2. **Aislamiento de Entorno e Portabilidad:** El uso de entornos virtuales y archivos de parametrización independientes (como `config.json`) facilita el despliegue del sistema en múltiples plataformas o servidores sin requerir cambios intrínsecos en el código fuente de Python.
3. **Control y Robustez Mediante Soft Delete (Papelera de Reciclaje):** Implementar un borrado lógico en lugar de físico en la tabla `Discografica` protege la integridad referencial de la base de datos de manera proactiva, garantizando que no existan huérfanos relacionales y brindando al usuario final una herramienta intuitiva para enmendar eliminaciones por error.

---

# V LECCIONES APRENDIDAS

* **Lección aprendida 1 (Integridad Referencial):** Aprendimos la importancia del manejo de excepciones relacionales en el desarrollo de software. Al intentar realizar un borrado físico, capturar con éxito los códigos de error del driver ODBC de SQL Server nos permite responder de manera elegante al usuario (mediante alertas informativas en la UI) en lugar de permitir que falle la sesión de la aplicación web.
* **Lección aprendida 2 (Manejo de Estados Lógicos):** Comprender el concepto de *Soft Delete* (borrado lógico) expandió nuestra visión técnica sobre cómo operan las bases de datos en la industria. En entornos reales, la información rara vez se destruye; marcar los registros con banderas lógicas mantiene el histórico y permite auditorías avanzadas de datos.
* **Lección aprendida 3 (Ventajas de la Autenticación SQL Login):** Aprendimos que al migrar de la Autenticación Integrada de Windows a SQL Login (con usuario `sa`), la aplicación web adquiere independencia del sistema operativo anfitrión. Esto permite un despliegue en contenedores Docker, servidores Linux remotos o nubes como AWS y Azure de forma nativa.
* **Lección aprendida 4 (Cohesión de Trabajo en Equipo):** Consolidamos una dinámica de trabajo en equipo ágil y coordinada entre Felipe Boada, Matías Flores, Ariel Tejada y Yusely Zapata. Logramos acoplar el modelamiento de base de datos física, la programación de stored procedures y la programación de frontend/backend de manera ordenada, simulando un ciclo real de desarrollo ágil de software.

---

# VI ANEXOS

### V.1 Anexo 1: Estructura de Directorios del Proyecto
Esquema de organización física de los archivos que integran la aplicación en su versión final:
```text
SoundWave/
│
├── Fase4/
│   ├── app.py                     # Controlador del backend (Rutas y Lógica Flask)
│   ├── config.json                # Variables de entorno y credenciales SQL Login
│   ├── requirements.txt           # Declaración de dependencias de Python
│   ├── Documentacion_Pruebas.md   # Marco teórico y ejecución de pruebas
│   │
│   ├── static/                    # Archivos estáticos de diseño
│   │   └── css/
│   │       └── style.css          # Estilos CSS de diseño premium oscuro
│   │
│   ├── templates/                 # Plantillas HTML5 de Jinja2
│   │   ├── base.html              # Estructura maestra del sitio y barra lateral
│   │   ├── dashboard.html         # Panel analítico de inicio
│   │   ├── index.html             # Catálogo de discográficas (CRUD Activo)
│   │   ├── papelera.html          # Papelera de reciclaje (Soft-deleted CRUD)
│   │   ├── create.html            # Formulario de inserción de discográfica
│   │   ├── edit.html              # Formulario de modificación de discográfica
│   │   ├── artistas.html          # Vista de consulta de artistas
│   │   ├── canciones.html         # Vista de consulta de canciones
│   │   ├── usuarios.html          # Vista de consulta de usuarios
│   │   └── reportes.html          # Vista de explotación de reportes analíticos
│   │
│   └── tests/                     # Suite de control de calidad
│       └── test_app.py            # Casos de pruebas unitarias, integración y sistema
```

### V.2 Anexo 2: Enlaces Importantes de Entrega
* **Enlace al Repositorio de Código en GitHub:** [https://github.com/FelipeBoada/SoundWave-Database-Project](https://github.com/FelipeBoada/SoundWave-Database-Project)
* **Enlace al Video Demostrativo en YouTube:** [https://youtu.be/SoundWaveCRUDDemo](https://youtu.be/SoundWaveCRUDDemo)
