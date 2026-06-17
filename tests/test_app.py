import pytest
import os
import sys

# Añadir el directorio padre al path para poder importar app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app, get_db_connection

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test_secret_key'
    with app.test_client() as client:
        yield client

# --- 1. PRUEBAS UNITARIAS (Unit Tests) ---
def test_app_is_testing(client):
    """Verifica que la app entra correctamente en modo Testing"""
    assert app.config['TESTING'] is True

# --- 2. PRUEBAS DE INTEGRACIÓN (Integration Tests) ---
def test_db_connection():
    """Verifica que la app puede conectar exitosamente a SQL Server usando config.json"""
    try:
        conexion = get_db_connection()
        cursor = conexion.cursor()
        cursor.execute("SELECT 1")
        resultado = cursor.fetchone()
        assert resultado[0] == 1
        conexion.close()
    except Exception as e:
        pytest.fail(f"La prueba de integración de BD falló: {e}")

# --- 3. PRUEBAS DE SISTEMA (System / End-to-End Tests) ---
def test_index_page_loads(client):
    """Verifica que la página principal (Index/Dashboard) responde con HTTP 200 OK"""
    response = client.get('/')
    assert response.status_code == 200
    assert b"SOUNDWAVE" in response.data

def test_admin_route_redirects_when_unauthorized(client):
    """Verifica que las rutas administrativas redirigen a index (302) si no hay sesión activa"""
    response = client.get('/discograficas')
    assert response.status_code == 302
    
    response = client.get('/create')
    assert response.status_code == 302
    
    response = client.get('/reportes')
    assert response.status_code == 302

def test_admin_login_success(client):
    """Verifica que se puede iniciar sesión con credenciales válidas"""
    response = client.post('/admin/login', data={
        'email': 'felipe@soundwave.com',
        'password': '1234'
    }, follow_redirects=True)
    assert response.status_code == 200
    # Al entrar como admin exitoso redirige a /discograficas
    assert b"Cat" in response.data or b"Discogr" in response.data

def test_admin_login_failure(client):
    """Verifica que el login falla con credenciales incorrectas y redirige"""
    response = client.post('/admin/login', data={
        'email': 'baduser@soundwave.com',
        'password': 'wrongpassword'
    })
    # Redirige a index
    assert response.status_code == 302


# --- 4. NUEVOS CASOS DE PRUEBA CRUD Y PAPELERA (Artistas, Canciones, Playlists) ---

def test_artista_crud_lifecycle(client):
    """Verifica el flujo CRUD completo con papelera para Artista"""
    # Forzar sesión de administrador
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_email'] = 'felipe@soundwave.com'
        
    # 1. CREAR
    response = client.post('/create_artista', data={
        'nombreArtistico': 'Artista Prueba Inteligente',
        'pais': 'Ecuador',
        'fechaInicio': '2020-05-15',
        'discograficaId': ''  # Independiente
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Artista creado exitosamente" in response.data or b"exito" in response.data.lower()
    
    # Obtener ID del artista insertado
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT artistaId FROM soundwave.Artista WHERE nombreArtistico = ?", ('Artista Prueba Inteligente',))
    row = cursor.fetchone()
    assert row is not None
    artista_id = row[0]
    conn.close()
    
    # 2. EDITAR
    response = client.post(f'/edit_artista/{artista_id}', data={
        'nombreArtistico': 'Artista Prueba Modificado',
        'pais': 'Colombia',
        'fechaInicio': '2020-05-15',
        'discograficaId': ''
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Artista actualizado exitosamente" in response.data or b"exito" in response.data.lower()
    
    # Verificar edición
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nombreArtistico, pais FROM soundwave.Artista WHERE artistaId = ?", (artista_id,))
    row = cursor.fetchone()
    assert row[0] == 'Artista Prueba Modificado'
    assert row[1] == 'Colombia'
    conn.close()
    
    # 3. SOFT DELETE (Mover a la papelera)
    response = client.post(f'/delete_artista/{artista_id}', follow_redirects=True)
    assert response.status_code == 200
    assert b"papelera" in response.data.lower()
    
    # Verificar en BD que está eliminado lógico
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT eliminado FROM soundwave.Artista WHERE artistaId = ?", (artista_id,))
    row = cursor.fetchone()
    assert row[0] == 1 or row[0] is True
    conn.close()
    
    # 4. RESTAURAR
    response = client.post(f'/restore_artista/{artista_id}', follow_redirects=True)
    assert response.status_code == 200
    
    # Verificar en BD restaurado
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT eliminado FROM soundwave.Artista WHERE artistaId = ?", (artista_id,))
    row = cursor.fetchone()
    assert row[0] == 0 or row[0] is False
    conn.close()
    
    # 5. ELIMINACIÓN PERMANENTE
    # Primero volvemos a mover a la papelera
    client.post(f'/delete_artista/{artista_id}')
    
    response = client.post(f'/delete_permanent_artista/{artista_id}', follow_redirects=True)
    assert response.status_code == 200
    assert b"eliminado permanentemente" in response.data.lower()
    
    # Verificar que ya no existe físicamente
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM soundwave.Artista WHERE artistaId = ?", (artista_id,))
    row = cursor.fetchone()
    assert row[0] == 0
    conn.close()


def test_cancion_crud_lifecycle(client):
    """Verifica el flujo CRUD completo con papelera para Canción"""
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        
    # 1. CREAR
    response = client.post('/create_cancion', data={
        'titulo': 'Cancion Magnetica',
        'duracion': '210',
        'albumId': '1',  # ID existente de Mock Data (Un Verano Sin Ti)
        'explicita': '1',
        'generos': ['1']  # Reggaeton
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Cancion creada exitosamente" in response.data or b"exito" in response.data.lower()
    
    # Obtener ID
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT cancionId FROM soundwave.Cancion WHERE titulo = ?", ('Cancion Magnetica',))
    row = cursor.fetchone()
    assert row is not None
    cancion_id = row[0]
    conn.close()
    
    # 2. EDITAR
    response = client.post(f'/edit_cancion/{cancion_id}', data={
        'titulo': 'Cancion Magnetica Remix',
        'duracion': '225',
        'albumId': '1',
        # explicita se deja sin enviar para simular desmarcado
        'generos': ['1', '2']
    }, follow_redirects=True)
    assert response.status_code == 200
    
    # Verificar en BD
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT titulo, duracion, explicita FROM soundwave.Cancion WHERE cancionId = ?", (cancion_id,))
    row = cursor.fetchone()
    assert row[0] == 'Cancion Magnetica Remix'
    assert row[1] == 225
    assert row[2] == 0 or row[2] is False
    conn.close()
    
    # 3. SOFT DELETE
    response = client.post(f'/delete_cancion/{cancion_id}', follow_redirects=True)
    assert response.status_code == 200
    
    # Verificar en BD
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT eliminado FROM soundwave.Cancion WHERE cancionId = ?", (cancion_id,))
    row = cursor.fetchone()
    assert row[0] == 1 or row[0] is True
    conn.close()
    
    # 4. RESTAURAR
    response = client.post(f'/restore_cancion/{cancion_id}', follow_redirects=True)
    assert response.status_code == 200
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT eliminado FROM soundwave.Cancion WHERE cancionId = ?", (cancion_id,))
    row = cursor.fetchone()
    assert row[0] == 0 or row[0] is False
    conn.close()
    
    # 5. ELIMINACIÓN PERMANENTE
    client.post(f'/delete_cancion/{cancion_id}')
    response = client.post(f'/delete_permanent_cancion/{cancion_id}', follow_redirects=True)
    assert response.status_code == 200
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM soundwave.Cancion WHERE cancionId = ?", (cancion_id,))
    row = cursor.fetchone()
    assert row[0] == 0
    conn.close()


def test_playlist_crud_lifecycle(client):
    """Verifica el flujo CRUD completo con papelera para Playlist"""
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        
    # 1. CREAR
    response = client.post('/create_playlist', data={
        'nombre': 'Playlist Electronica 2026',
        'privacidad': 'Pública',
        'usuarioId': '1'  # Benjamin
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Playlist creada exitosamente" in response.data or b"exito" in response.data.lower()
    
    # Obtener ID
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT playlistId FROM soundwave.Playlist WHERE nombre = ?", ('Playlist Electronica 2026',))
    row = cursor.fetchone()
    assert row is not None
    playlist_id = row[0]
    conn.close()
    
    # 2. EDITAR
    response = client.post(f'/edit_playlist/{playlist_id}', data={
        'nombre': 'Playlist Techno Club',
        'privacidad': 'Privada',
        'usuarioId': '1',
        'canciones': ['1', '2']  # Asociar canciones 1 y 2
    }, follow_redirects=True)
    assert response.status_code == 200
    
    # Verificar en BD
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nombre, privacidad FROM soundwave.Playlist WHERE playlistId = ?", (playlist_id,))
    row = cursor.fetchone()
    assert row[0] == 'Playlist Techno Club'
    assert row[1] == 'Privada'
    
    # Verificar canciones asociadas en PlaylistCancion
    cursor.execute("SELECT COUNT(*) FROM soundwave.PlaylistCancion WHERE Playlist_playlistId = ?", (playlist_id,))
    count_row = cursor.fetchone()
    assert count_row[0] == 2
    conn.close()
    
    # 3. SOFT DELETE
    response = client.post(f'/delete_playlist/{playlist_id}', follow_redirects=True)
    assert response.status_code == 200
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT eliminado FROM soundwave.Playlist WHERE playlistId = ?", (playlist_id,))
    row = cursor.fetchone()
    assert row[0] == 1 or row[0] is True
    conn.close()
    
    # 4. RESTAURAR
    response = client.post(f'/restore_playlist/{playlist_id}', follow_redirects=True)
    assert response.status_code == 200
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT eliminado FROM soundwave.Playlist WHERE playlistId = ?", (playlist_id,))
    row = cursor.fetchone()
    assert row[0] == 0 or row[0] is False
    conn.close()
    
    # 5. ELIMINACIÓN PERMANENTE
    client.post(f'/delete_playlist/{playlist_id}')
    response = client.post(f'/delete_permanent_playlist/{playlist_id}', follow_redirects=True)
    assert response.status_code == 200
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM soundwave.Playlist WHERE playlistId = ?", (playlist_id,))
    row = cursor.fetchone()
    assert row[0] == 0
    conn.close()


def test_user_api_registration_and_premium_payment(client):
    """Verifica el flujo de registro de usuario por API, incluyendo la creación de suscripción y pago si es Premium"""
    import random
    unique_email = f"user_test_{random.randint(1000, 9999)}@gmail.com"
    
    # 1. Registrar usuario Premium
    response = client.post('/api/register', json={
        'name': 'Juan Test Premium',
        'email': unique_email,
        'phone': '0999999999',
        'password': 'password123',
        'accountType': 'premium'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    
    # 2. Verificar en la base de datos
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Buscar usuario
    cursor.execute("SELECT usuarioId, nombre FROM soundwave.Usuario WHERE email = ?", (unique_email,))
    user_row = cursor.fetchone()
    assert user_row is not None
    user_id = user_row[0]
    
    # Buscar suscripción activa Premium
    cursor.execute("""
        SELECT s.suscripcionId, ps.nombre 
        FROM soundwave.Suscripcion s
        JOIN soundwave.PlanSuscripcion ps ON s.Plan_planId = ps.planId
        WHERE s.Usuario_usuarioId = ? AND s.estado = 'Activa'
    """, (user_id,))
    sub_row = cursor.fetchone()
    assert sub_row is not None
    assert sub_row[1] == 'Premium'
    sub_id = sub_row[0]
    
    # Buscar pago registrado de $3.00
    cursor.execute("""
        SELECT monto, estado FROM soundwave.Pago 
        WHERE Suscripcion_suscripcionId = ?
    """, (sub_id,))
    pago_row = cursor.fetchone()
    assert pago_row is not None
    assert float(pago_row[0]) == 3.00
    assert pago_row[1] == 'Aprobado'
    
    # Limpiar datos de prueba
    cursor.execute("DELETE FROM soundwave.Pago WHERE Suscripcion_suscripcionId = ?", (sub_id,))
    cursor.execute("DELETE FROM soundwave.Suscripcion WHERE Usuario_usuarioId = ?", (user_id,))
    cursor.execute("DELETE FROM soundwave.Usuario WHERE usuarioId = ?", (user_id,))
    conn.commit()
    conn.close()


def test_api_reproducir(client):
    """Verifica el registro de reproducción en la API"""
    response = client.post('/api/reproducir', json={
        'titulo': 'Me Porto Bonito',
        'artista': 'Bad Bunny',
        'usuarioId': '1',
        'dispositivo': 'Web'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    
    # Verificar inserción en base de datos
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM soundwave.Reproduccion 
        WHERE Cancion_cancionId = 1 AND Usuario_usuarioId = 1
    """)
    count = cursor.fetchone()[0]
    assert count > 0
    
    # Limpiar reproducción de prueba
    cursor.execute("DELETE FROM soundwave.Reproduccion WHERE Cancion_cancionId = 1 AND Usuario_usuarioId = 1")
    conn.commit()
    conn.close()


def test_usuario_detalle_route(client):
    """Verifica que la ruta de detalle de usuario cargue correctamente para un administrador"""
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        
    response = client.get('/usuarios/detalle/1')
    assert response.status_code == 200
    assert b"Detalles del Cliente" in response.data
    assert b"Benjamin" in response.data or b"Perez" in response.data


def test_user_api_registration_duplicate_email_or_phone(client):
    """Verifica que la API impida registrar correos o celulares duplicados"""
    # Limpieza inicial preventiva
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT usuarioId FROM soundwave.Usuario WHERE email = ?", ('base_pruebas_dup@gmail.com',))
    row = cursor.fetchone()
    if row:
        user_id = row[0]
        cursor.execute("DELETE FROM soundwave.Suscripcion WHERE Usuario_usuarioId = ?", (user_id,))
        cursor.execute("DELETE FROM soundwave.Usuario WHERE usuarioId = ?", (user_id,))
        conn.commit()
    conn.close()

    try:
        # 1. Registrar usuario base
        response = client.post('/api/register', json={
            'name': 'Usuario Base Pruebas',
            'email': 'base_pruebas_dup@gmail.com',
            'phone': '0987654321',
            'password': 'password123',
            'accountType': 'normal'
        })
        assert response.status_code == 200
        
        # 2. Intentar registrar mismo correo, diferente celular
        response = client.post('/api/register', json={
            'name': 'Otro Usuario',
            'email': 'base_pruebas_dup@gmail.com',
            'phone': '0987654322',
            'password': 'password123',
            'accountType': 'normal'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'correo electrónico ya está registrado' in data['message']
        
        # 3. Intentar registrar diferente correo, mismo celular
        response = client.post('/api/register', json={
            'name': 'Tercer Usuario',
            'email': 'otro_correo_dup@gmail.com',
            'phone': '0987654321',
            'password': 'password123',
            'accountType': 'normal'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'número de celular ya está registrado' in data['message']
    finally:
        # Limpieza final
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT usuarioId FROM soundwave.Usuario WHERE email = ?", ('base_pruebas_dup@gmail.com',))
        row = cursor.fetchone()
        if row:
            user_id = row[0]
            cursor.execute("DELETE FROM soundwave.Suscripcion WHERE Usuario_usuarioId = ?", (user_id,))
            cursor.execute("DELETE FROM soundwave.Usuario WHERE usuarioId = ?", (user_id,))
            conn.commit()
        conn.close()


def test_usuario_soft_and_hard_delete_lifecycle(client):
    """Verifica el ciclo de vida completo de soft delete, restauración y hard delete de un usuario"""
    # 1. Crear un usuario de prueba directamente
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO soundwave.Usuario (nombre, apellido, email, contraseña, pais, estado, telefono, eliminado)
        VALUES ('TestDelete', 'User', 'test_delete_life@gmail.com', 'pass123', 'Ecuador', 'Activa', '0990990990', 0)
    """)
    cursor.execute("SELECT usuarioId FROM soundwave.Usuario WHERE email = ?", ('test_delete_life@gmail.com',))
    row = cursor.fetchone()
    assert row is not None
    user_id = row[0]
    conn.commit()
    conn.close()

    # Forzar sesión de administrador
    with client.session_transaction() as sess:
        sess['is_admin'] = True

    try:
        # 2. Soft delete por POST
        response = client.post(f'/usuarios/delete/{user_id}', follow_redirects=True)
        assert response.status_code == 200
        assert b"enviado a la papelera" in response.data or b"papelera" in response.data.lower()
        
        # Verificar en base de datos
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT eliminado FROM soundwave.Usuario WHERE usuarioId = ?", (user_id,))
        assert cursor.fetchone()[0] == 1
        conn.close()
        
        # 3. Restaurar por POST
        response = client.post(f'/usuarios/restore/{user_id}', follow_redirects=True)
        assert response.status_code == 200
        assert b"restaurado" in response.data or b"exito" in response.data.lower()
        
        # Verificar en base de datos
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT eliminado FROM soundwave.Usuario WHERE usuarioId = ?", (user_id,))
        res = cursor.fetchone()[0]
        assert res == 0 or res is False
        conn.close()
        
        # 4. Soft delete de nuevo para poder hacer hard delete
        client.post(f'/usuarios/delete/{user_id}')
        
        # 5. Hard delete (Eliminar Permanentemente)
        response = client.post(f'/usuarios/delete_permanent/{user_id}', follow_redirects=True)
        assert response.status_code == 200
        assert b"eliminado permanentemente" in response.data.lower()
        
        # Verificar que ya no existe en la base de datos
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM soundwave.Usuario WHERE usuarioId = ?", (user_id,))
        assert cursor.fetchone()[0] == 0
        conn.close()
        
    finally:
        # Limpieza de seguridad
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT usuarioId FROM soundwave.Usuario WHERE email = ?", ('test_delete_life@gmail.com',))
        row = cursor.fetchone()
        if row:
            uid = row[0]
            cursor.execute("DELETE FROM soundwave.Suscripcion WHERE Usuario_usuarioId = ?", (uid,))
            cursor.execute("DELETE FROM soundwave.Usuario WHERE usuarioId = ?", (uid,))
            conn.commit()
        conn.close()


def test_create_playlist_with_new_creator(client):
    """Verifica la creación de una playlist indicando un nuevo creador/usuario"""
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_email'] = 'felipe@soundwave.com'
        
    nombre_playlist = 'Test Playlist New User'
    nuevo_creador = 'Juan CreadorTest'
    
    # 1. Crear playlist
    response = client.post('/create_playlist', data={
        'nombre': nombre_playlist,
        'privacidad': 'Pública',
        'usuarioId': '',
        'nuevoCreador': nuevo_creador
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Playlist creada exitosamente" in response.data or b"exito" in response.data.lower()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Verificar que el usuario fue registrado
        cursor.execute("SELECT usuarioId, email FROM soundwave.Usuario WHERE nombre = ? AND apellido = ?", ('Juan', 'CreadorTest'))
        user_row = cursor.fetchone()
        assert user_row is not None
        user_id = user_row[0]
        email = user_row[1]
        assert email.endswith('@soundwave.com')
        
        # Verificar suscripción
        cursor.execute("SELECT COUNT(*) FROM soundwave.Suscripcion WHERE Usuario_usuarioId = ?", (user_id,))
        assert cursor.fetchone()[0] == 1
        
        # Verificar playlist
        cursor.execute("SELECT playlistId FROM soundwave.Playlist WHERE nombre = ? AND Usuario_usuarioId = ?", (nombre_playlist, user_id))
        playlist_row = cursor.fetchone()
        assert playlist_row is not None
        playlist_id = playlist_row[0]
        
    finally:
        # Limpieza de los registros de prueba creados
        cursor.execute("SELECT usuarioId FROM soundwave.Usuario WHERE nombre = ? AND apellido = ?", ('Juan', 'CreadorTest'))
        rows = cursor.fetchall()
        for row in rows:
            uid = row[0]
            cursor.execute("DELETE FROM soundwave.PlaylistCancion WHERE Playlist_playlistId IN (SELECT playlistId FROM soundwave.Playlist WHERE Usuario_usuarioId = ?)", (uid,))
            cursor.execute("DELETE FROM soundwave.Playlist WHERE Usuario_usuarioId = ?", (uid,))
            cursor.execute("DELETE FROM soundwave.Suscripcion WHERE Usuario_usuarioId = ?", (uid,))
            cursor.execute("DELETE FROM soundwave.Usuario WHERE usuarioId = ?", (uid,))
        conn.commit()
        conn.close()


def test_whatsapp_phone_number_formatting(monkeypatch):
    """Verifica que la función enviar_mensaje_whatsapp formatea correctamente varios formatos de números celular de Ecuador"""
    from app import enviar_mensaje_whatsapp
    
    captured_payloads = []
    
    # Mockear urllib.request.urlopen para capturar qué datos se envían
    class MockResponse:
        def __init__(self):
            pass
        def read(self):
            return b'{"success": true}'
        def decode(self, encoding):
            return '{"success": true}'
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
            
    def mock_urlopen(req, timeout=None):
        # El cuerpo de la petición está en req.data
        if req.data:
            payload = json.loads(req.data.decode('utf-8'))
            captured_payloads.append(payload)
        return MockResponse()
        
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    
    # Probar diferentes formatos de números
    test_cases = [
        ("0960786020", "593960786020@c.us"),      # Formato local clásico
        ("+593960786020", "593960786020@c.us"),   # Formato con código país
        ("+5930960786020", "593960786020@c.us"),  # Formato con código país y cero erróneo
        ("960786020", "593960786020@c.us"),       # Sin cero ni código país
    ]
    
    import json
    for input_phone, expected_chat_id in test_cases:
        captured_payloads.clear()
        enviar_mensaje_whatsapp(input_phone, "Usuario Prueba", "premium")
        assert len(captured_payloads) == 1
        assert captured_payloads[0]["chatId"] == expected_chat_id


def test_api_login_success(client):
    """Verifica el inicio de sesión exitoso mediante la API para un usuario registrado"""
    # 1. Crear un usuario temporal
    conn = get_db_connection()
    cursor = conn.cursor()
    # Limpiar si existía antes
    cursor.execute("DELETE FROM soundwave.Usuario WHERE email = ?", ('test_api_login@udla.edu.ec',))
    cursor.execute("""
        INSERT INTO soundwave.Usuario (nombre, apellido, email, contraseña, pais, estado, telefono)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ('Test', 'ApiLogin', 'test_api_login@udla.edu.ec', 'test_pass_123', 'Ecuador', 'Activa', '0999999991'))
    conn.commit()
    conn.close()

    try:
        # 2. Hacer login
        response = client.post('/api/login', json={
            'email': 'test_api_login@udla.edu.ec',
            'password': 'test_pass_123'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['user']['email'] == 'test_api_login@udla.edu.ec'
        assert data['user']['name'] == 'Test ApiLogin'
    finally:
        # Limpieza
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM soundwave.Usuario WHERE email = ?", ('test_api_login@udla.edu.ec',))
        conn.commit()
        conn.close()


def test_api_login_invalid_password(client):
    """Verifica que el login por API falle si la contraseña es incorrecta"""
    # 1. Crear un usuario temporal
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM soundwave.Usuario WHERE email = ?", ('test_api_login_fail@udla.edu.ec',))
    cursor.execute("""
        INSERT INTO soundwave.Usuario (nombre, apellido, email, contraseña, pais, estado, telefono)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ('Test', 'ApiLoginFail', 'test_api_login_fail@udla.edu.ec', 'good_pass', 'Ecuador', 'Activa', '0999999994'))
    conn.commit()
    conn.close()

    try:
        response = client.post('/api/login', json={
            'email': 'test_api_login_fail@udla.edu.ec',
            'password': 'incorrect_password'
        })
        assert response.status_code == 401
        data = response.get_json()
        assert data['success'] is False
    finally:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM soundwave.Usuario WHERE email = ?", ('test_api_login_fail@udla.edu.ec',))
        conn.commit()
        conn.close()


def test_api_forgot_password_success(client):
    """Verifica que el endpoint de recuperación retorne la contraseña correcta"""
    # 1. Crear un usuario temporal
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM soundwave.Usuario WHERE email = ?", ('test_api_forgot@udla.edu.ec',))
    cursor.execute("""
        INSERT INTO soundwave.Usuario (nombre, apellido, email, contraseña, pais, estado, telefono)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ('Test', 'ApiForgot', 'test_api_forgot@udla.edu.ec', 'secret_forgot_pass', 'Ecuador', 'Activa', '0999999992'))
    conn.commit()
    conn.close()

    try:
        # 2. Consultar recuperación
        response = client.post('/api/forgot-password', json={
            'email': 'test_api_forgot@udla.edu.ec'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['password'] == 'secret_forgot_pass'
    finally:
        # Limpieza
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM soundwave.Usuario WHERE email = ?", ('test_api_forgot@udla.edu.ec',))
        conn.commit()
        conn.close()


def test_api_forgot_password_not_found(client):
    """Verifica que retorne 404 si el correo no está registrado"""
    response = client.post('/api/forgot-password', json={
        'email': 'nonexistent_user@udla.edu.ec'
    })
    assert response.status_code == 404
    data = response.get_json()
    assert data['success'] is False









