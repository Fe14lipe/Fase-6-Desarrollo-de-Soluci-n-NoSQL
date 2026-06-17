import pytest
import os
import sys
import random
from datetime import datetime

# Añadir el directorio padre al path para importar app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app, db_mongo, database_type

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test_mongo_secret_key'
    with app.test_client() as client:
        yield client

# --- 1. VERIFICACIONES DE CONFIGURACIÓN ---
def test_database_is_mongodb():
    """Verifica que la app esté configurada para usar MongoDB"""
    assert database_type == 'mongodb'
    assert db_mongo is not None

def test_mongodb_connection():
    """Verifica que podemos conectarnos a MongoDB y listar colecciones"""
    try:
        collections = db_mongo.list_collection_names()
        assert isinstance(collections, list)
    except Exception as e:
        pytest.fail(f"Fallo de conexión a MongoDB: {e}")

# --- 2. PRUEBAS DE VISTAS (System / Integration) ---
def test_dashboard_loads_mongodb(client):
    """Verifica que el dashboard principal carga sin errores usando MongoDB"""
    response = client.get('/')
    assert response.status_code == 200
    assert b"SOUNDWAVE" in response.data or b"Dashboard" in response.data

def test_admin_route_redirects_unauthorized_mongodb(client):
    """Verifica redirección de seguridad en rutas admin"""
    response = client.get('/discograficas')
    assert response.status_code == 302 # Redirige a index

# --- 3. PRUEBAS CRUD Y CICLO DE VIDA (Discográficas) ---
def test_discografica_crud_lifecycle_mongodb(client):
    """Verifica el flujo CRUD completo de Discográficas en MongoDB"""
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_email'] = 'felipe@soundwave.com'
        
    random_id = random.randint(10000, 99999)
    nombre_test = f"Discografica Mongo {random_id}"
    
    # 1. CREATE
    response = client.post('/create_discografica', data={
        'nombre': nombre_test,
        'pais': 'Ecuador',
        'fechaFundacion': '2026-06-16'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"creada exitosamente" in response.data.lower()
    
    # Verificar inserción
    disc = db_mongo.discograficas.find_one({"nombre": nombre_test})
    assert disc is not None
    assert disc["pais"] == "Ecuador"
    disc_id = disc["discograficaId"]
    
    # 2. EDIT
    nombre_mod = f"Discografica Mod {random_id}"
    response = client.post(f'/edit_discografica/{nombre_test}', data={
        'nombre': nombre_mod,
        'pais': 'Colombia',
        'fechaFundacion': '2026-06-16'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"actualizada exitosamente" in response.data.lower()
    
    # Verificar edición
    disc_mod = db_mongo.discograficas.find_one({"discograficaId": disc_id})
    assert disc_mod["nombre"] == nombre_mod
    assert disc_mod["pais"] == "Colombia"
    
    # 3. SOFT DELETE (Papelera)
    response = client.post(f'/delete_discografica/{nombre_mod}', follow_redirects=True)
    assert response.status_code == 200
    
    disc_del = db_mongo.discograficas.find_one({"discograficaId": disc_id})
    assert disc_del.get("eliminado") is True
    
    # 4. RESTORE (Restaurar)
    response = client.post(f'/restore_discografica/{nombre_mod}', follow_redirects=True)
    assert response.status_code == 200
    
    disc_rest = db_mongo.discograficas.find_one({"discograficaId": disc_id})
    assert disc_rest.get("eliminado") is False
    
    # 5. HARD DELETE (Permanente)
    # Mover a papelera primero
    client.post(f'/delete_discografica/{nombre_mod}')
    response = client.post(f'/delete_permanent_discografica/{nombre_mod}', follow_redirects=True)
    assert response.status_code == 200
    
    disc_phys = db_mongo.discograficas.find_one({"discograficaId": disc_id})
    assert disc_phys is None

# --- 4. PRUEBAS DE API (Registro, Login, Upgrade y Reproducciones) ---
def test_api_user_flows_mongodb(client):
    """Prueba flujo completo de registro, login, upgrade y reproducción vía API en MongoDB"""
    random_id = random.randint(10000, 99999)
    email_test = f"user_{random_id}@soundwave.com"
    phone_test = f"099{random_id:07d}"
    
    # 1. Registro
    response = client.post('/api/register', json={
        'name': 'Usuario Test Mongo',
        'email': email_test,
        'phone': phone_test,
        'password': 'mypassword',
        'accountType': 'normal'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    
    # Verificar en MongoDB
    user = db_mongo.usuarios.find_one({"email": email_test})
    assert user is not None
    assert user["nombre"] == "Usuario"
    assert user["apellido"] == "Test Mongo"
    assert len(user["suscripciones"]) == 1
    assert user["suscripciones"][0]["plan"]["nombre"] == "Gratis"
    usuario_id = user["usuarioId"]
    
    # 2. Login
    response = client.post('/api/login', json={
        'email': email_test,
        'password': 'mypassword'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['user']['name'] == "Usuario Test Mongo"
    
    # 3. Upgrade a Premium
    response = client.post('/api/upgrade', json={
        'email': email_test,
        'plan': 'Individual',
        'price': 5.99
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    
    # Verificar nuevo plan Premium y Pago
    user_up = db_mongo.usuarios.find_one({"usuarioId": usuario_id})
    active_sub = next((s for s in user_up["suscripciones"] if s["estado"] == "Activa"), None)
    assert active_sub is not None
    assert active_sub["plan"]["nombre"] == "Premium"
    assert len(active_sub["pagos"]) == 1
    assert active_sub["pagos"][0]["monto"] == 5.99
    
    # 4. Registrar Reproducción
    response = client.post('/api/reproducir', json={
        'titulo': 'Me Porto Bonito',
        'artista': 'Bad Bunny',
        'usuarioId': usuario_id,
        'dispositivo': 'Web'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    
    # Verificar registro en colección
    rep = db_mongo.reproducciones.find_one({"usuarioId": usuario_id, "cancionId": 1})
    assert rep is not None
    assert rep["cancionTitulo"] == "Me Porto Bonito"
    
    # Limpiar datos de prueba
    db_mongo.reproducciones.delete_many({"usuarioId": usuario_id})
    db_mongo.usuarios.delete_one({"usuarioId": usuario_id})

# --- 5. PRUEBAS DE REPORTES Y DETALLES ---
def test_reports_mongodb(client):
    """Verifica la carga del módulo de reportes y ejecución de agregaciones MongoDB"""
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        
    response = client.post('/reportes', data={
        'fecha_inicio': '2024-01-01',
        'fecha_fin': '2024-12-31',
        'artista_id': '1',
        'playlist_id': '1'
    })
    assert response.status_code == 200
    assert b"Reportes Din" in response.data or b"top" in response.data.lower()
