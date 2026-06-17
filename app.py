import json
import os
import pyodbc
import urllib.request
import urllib.error
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Genera una clave aleatoria más segura para la sesión

# Valores por defecto para la integración de WhatsApp (Open-WA)
whatsapp_url = 'http://localhost:2785/api/sessions/my-bot/messages/send-text'
whatsapp_api_key = 'my-secret-key'

# Cargar la configuración una sola vez en memoria al iniciar la aplicación (Optimización de I/O)
ruta_config = os.path.join(os.path.dirname(__file__), 'config.json')

client_mongo = None
db_mongo = None
database_type = 'mssql'
connection_string = None

try:
    with open(ruta_config, 'r') as archivo_config:
        config = json.load(archivo_config)
    name_server = config.get('name_server')
    database = config.get('database')
    driver = config.get('driver')
    uid = config.get('uid')
    pwd = config.get('pwd')
    database_type = config.get('database_type', 'mssql')
    
    # Cargar URLs y API keys opcionales para WhatsApp
    whatsapp_url = config.get('whatsapp_url', whatsapp_url)
    whatsapp_api_key = config.get('whatsapp_api_key', whatsapp_api_key)
    
    if name_server and driver and database:
        if uid and pwd:
            connection_string = f'DRIVER={{{driver}}};SERVER={name_server};DATABASE={database};UID={uid};PWD={pwd};'
        else:
            connection_string = f'DRIVER={{{driver}}};SERVER={name_server};DATABASE={database};Trusted_Connection=yes;'
            
    if database_type == 'mongodb':
        from pymongo import MongoClient
        mongodb_uri = config.get('mongodb_uri', 'mongodb://localhost:27017/')
        mongodb_db = config.get('mongodb_db', 'SoundWave')
        client_mongo = MongoClient(mongodb_uri)
        db_mongo = client_mongo[mongodb_db]
        print(f"[MongoDB] Conectado exitosamente a la base de datos '{mongodb_db}'.")
except Exception as e:
    connection_string = None
    print(f"Error al cargar config.json o inicializar base de datos: {e}")

def get_db_connection():
    if not connection_string:
        raise Exception("La cadena de conexión no está configurada correctamente.")
    return pyodbc.connect(connection_string)

class MongoRow:
    """
    Clase adaptadora para convertir diccionarios de MongoDB en objetos que soportan 
    el acceso a atributos estilo objeto, idéntico a las filas retornadas por pyodbc.
    """
    def __init__(self, data):
        if data is None:
            data = {}
        self.__dict__.update(data)
        
        # Mapeo de IDs clave para que no rompa el acceso de atributos
        if 'discograficaId' in data:
            self.discograficaId = data['discograficaId']
        if 'artistaId' in data:
            self.artistaId = data['artistaId']
        if 'cancionId' in data:
            self.cancionId = data['cancionId']
        if 'playlistId' in data:
            self.playlistId = data['playlistId']
        if 'usuarioId' in data:
            self.usuarioId = data['usuarioId']
        if 'planId' in data:
            self.planId = data['planId']
        if 'suscripcionId' in data:
            self.suscripcionId = data['suscripcionId']
        if 'reproduccionId' in data:
            self.reproduccionId = data['reproduccionId']
            
    def __getattr__(self, name):
        # Retorna None por defecto en vez de AttributeError
        return self.__dict__.get(name, None)

# Decorador para restringir el acceso a rutas administrativas
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Acceso denegado: Se requiere perfil de Administrador.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    top_canciones = []
    if database_type == 'mongodb':
        try:
            # Obtener todas las canciones con sus reproducciones (LEFT JOIN equivalente)
            pipeline = [
                {"$unwind": "$canciones"},
                {"$lookup": {
                    "from": "reproducciones",
                    "localField": "canciones.cancionId",
                    "foreignField": "cancionId",
                    "as": "plays"
                }},
                {"$project": {
                    "Cancion": "$canciones.titulo",
                    "Artista": "$artistaNombre",
                    "TotalReproducciones": {"$size": "$plays"}
                }},
                {"$sort": {"TotalReproducciones": -1, "Cancion": 1}}
            ]
            results = list(db_mongo.albums.aggregate(pipeline))
            top_canciones = [MongoRow(r) for r in results]
        except Exception as e:
            print(f"Error en dashboard MongoDB: {e}")
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            query = """
                SELECT 
                    c.titulo AS Cancion, 
                    a.nombreArtistico AS Artista, 
                    COUNT(r.reproduccionId) AS TotalReproducciones
                FROM soundwave.Cancion c
                JOIN soundwave.Album al ON c.Album_albumId = al.albumId
                JOIN soundwave.Artista a ON al.Artista_artistaId = a.artistaId
                LEFT JOIN soundwave.Reproduccion r ON c.cancionId = r.Cancion_cancionId
                GROUP BY c.titulo, a.nombreArtistico
                ORDER BY TotalReproducciones DESC, c.titulo ASC;
            """
            cursor.execute(query)
            top_canciones = cursor.fetchall()
        except Exception as e:
            print(f"Error en el dashboard: {e}")
        finally:
            if conexion:
                conexion.close()
    return render_template('dashboard.html', top_canciones=top_canciones)

# --- RUTAS DE AUTENTICACIÓN ---
@app.route('/admin/login', methods=['POST'])
def admin_login():
    datos = request.get_json(silent=True) or request.form
    email = datos.get('email')
    password = datos.get('password')
    
    if email == 'felipe@soundwave.com' and password == '1234':
        session['is_admin'] = True
        session['admin_email'] = email
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'redirect': url_for('discograficas')})
        flash('Sesión iniciada como Administrador.', 'success')
        return redirect(url_for('discograficas'))
    else:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Credenciales incorrectas.'})
        flash('Credenciales de administrador incorrectas.', 'error')
        return redirect(url_for('index'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    session.pop('admin_email', None)
    flash('Sesión de administrador cerrada.', 'success')
    return redirect(url_for('index'))

def enviar_mensaje_whatsapp(phone, name, account_type):
    cleaned = ''.join(c for c in phone if c.isdigit())
    if not cleaned:
        print("[WhatsApp] Número inválido.")
        return
        
    if cleaned.startswith('593'):
        cleaned = cleaned[3:]
        
    if cleaned.startswith('0'):
        cleaned = cleaned[1:]
        
    cleaned = '593' + cleaned
    chat_id = f"{cleaned}@c.us"
    
    plan_str = "Gratuito 🎵"
    if 'premium' in account_type.lower():
        if 'individual' in account_type.lower():
            plan_str = "Premium Individual ⭐"
        elif 'estudiantes' in account_type.lower():
            plan_str = "Premium Estudiantes ⭐"
        elif 'duo' in account_type.lower():
            plan_str = "Premium Duo ⭐"
        else:
            plan_str = "Premium ⭐"

    is_upgrade = "upgrade" in account_type.lower() or "plan" in account_type.lower()
    
    if is_upgrade:
        mensaje = (
            f"¡Hola {name}! 🎧\n\n"
            f"Tu cuenta en *SoundWave* se ha actualizado con éxito al plan *{plan_str}*. 🚀\n\n"
            f"¡Siente el ritmo en cada onda sin límites y con la mejor calidad! 🎶"
        )
    else:
        mensaje = (
            f"¡Hola {name}! 🎧\n\n"
            f"Te damos la bienvenida oficial a *SoundWave* 🚀\n"
            f"Tu registro se ha completado con éxito en el plan *{plan_str}*.\n\n"
            f"¡Siente el ritmo en cada onda! Que disfrutes de tu música favorita. 🎶"
        )
    
    url = whatsapp_url
    payload = {
        "chatId": chat_id,
        "text": mensaje
    }
    
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                'Content-Type': 'application/json',
                'X-API-Key': whatsapp_api_key
            },
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=2.0) as response:
            res_data = response.read().decode('utf-8')
            print(f"[WhatsApp] Mensaje enviado con éxito: {res_data}")
    except urllib.error.URLError as e:
        print(f"[WhatsApp Integration] No se pudo enviar el mensaje por WhatsApp. Detalle: {e}.")
    except Exception as e:
        print(f"[WhatsApp Integration] Error al procesar el envío: {e}")

@app.route('/api/register', methods=['POST'])
def api_register():
    datos = request.get_json(silent=True) or request.form
    nombre_completo = datos.get('name', '').strip()
    email = datos.get('email', '').strip()
    phone = datos.get('phone', '').strip()
    password = datos.get('password', '')
    account_type = datos.get('accountType', 'normal')
    
    if not nombre_completo or not email or not password:
        return jsonify({'success': False, 'message': 'Faltan campos requeridos.'}), 400
    
    partes = nombre_completo.split(' ', 1)
    nombre = partes[0]
    apellido = partes[1] if len(partes) > 1 else ''
    
    if database_type == 'mongodb':
        try:
            # 1. Validaciones
            if db_mongo.usuarios.find_one({"email": email, "$or": [{"eliminado": False}, {"eliminado": {"$exists": False}}]}):
                return jsonify({'success': False, 'message': 'El correo electrónico ya está registrado.'}), 400
            
            if phone and db_mongo.usuarios.find_one({"telefono": phone, "$or": [{"eliminado": False}, {"eliminado": {"$exists": False}}]}):
                return jsonify({'success': False, 'message': 'El número de celular ya está registrado.'}), 400
                
            # 2. Generar usuarioId autoincremental
            max_u = db_mongo.usuarios.find_one(sort=[("usuarioId", -1)])
            usuario_id = (max_u["usuarioId"] + 1) if max_u else 1
            
            # 3. Datos del plan
            plan_nombre = 'Premium' if account_type == 'premium' else 'Gratis'
            plan_precio = 5.99 if plan_nombre == 'Premium' else 0.00
            plan_desc = 'Música sin anuncios, descargas offline, audio HQ' if plan_nombre == 'Premium' else 'Música con anuncios, saltos limitados'
            
            # Obtener máximo suscripcionId y pagoId
            max_sub_id = 0
            max_pago_id = 0
            for u in db_mongo.usuarios.find():
                for s in u.get('suscripciones', []):
                    if s.get('suscripcionId', 0) > max_sub_id:
                        max_sub_id = s['suscripcionId']
                    for p in s.get('pagos', []):
                        if p.get('pagoId', 0) > max_pago_id:
                            max_pago_id = p['pagoId']
            
            suscripcion_id = max_sub_id + 1
            
            suscripcion = {
                "suscripcionId": suscripcion_id,
                "fechaInicio": datetime.now(),
                "fechaFin": None,
                "estado": "Activa",
                "plan": {
                    "planId": 2 if plan_nombre == 'Premium' else 1,
                    "nombre": plan_nombre,
                    "precioMensual": plan_precio,
                    "descripcion": plan_desc
                },
                "pagos": []
            }
            
            if account_type == 'premium':
                pago_id = max_pago_id + 1
                suscripcion["pagos"].append({
                    "pagoId": pago_id,
                    "monto": 3.00,
                    "fechaPago": datetime.now(),
                    "metodoPago": "Tarjeta",
                    "estado": "Aprobado"
                })
                
            user_doc = {
                "usuarioId": usuario_id,
                "nombre": nombre,
                "apellido": apellido,
                "email": email,
                "contraseña": password,
                "pais": "Ecuador",
                "fechaRegistro": datetime.now(),
                "estado": "Activa",
                "telefono": phone,
                "eliminado": False,
                "suscripciones": [suscripcion]
            }
            
            db_mongo.usuarios.insert_one(user_doc)
            
            try:
                enviar_mensaje_whatsapp(phone, nombre_completo, account_type)
            except Exception as wa_err:
                print(f"[WhatsApp] Error: {wa_err}")
                
            return jsonify({'success': True, 'message': 'Usuario registrado exitosamente.'})
        except Exception as e:
            print(f"Error registrando en MongoDB: {e}")
            return jsonify({'success': False, 'message': f'Error en MongoDB: {str(e)}'}), 500
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM soundwave.Usuario WHERE email = ?", (email,))
            if cursor.fetchone()[0] > 0:
                return jsonify({'success': False, 'message': 'El correo electrónico ya está registrado.'}), 400
                
            if phone:
                cursor.execute("SELECT COUNT(*) FROM soundwave.Usuario WHERE telefono = ?", (phone,))
                if cursor.fetchone()[0] > 0:
                    return jsonify({'success': False, 'message': 'El número de celular ya está registrado.'}), 400
                
            cursor.execute("""
                INSERT INTO soundwave.Usuario (nombre, apellido, email, contraseña, pais, estado, telefono)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (nombre, apellido, email, password, 'Ecuador', 'Activa', phone))
            
            cursor.execute("SELECT usuarioId FROM soundwave.Usuario WHERE email = ?", (email,))
            usuario_id = int(cursor.fetchone()[0])
            
            plan_nombre = 'Premium' if account_type == 'premium' else 'Gratis'
            cursor.execute("SELECT planId FROM soundwave.PlanSuscripcion WHERE nombre = ?", (plan_nombre,))
            fila_plan = cursor.fetchone()
            plan_id = fila_plan[0] if fila_plan else (2 if account_type == 'premium' else 1)
            
            cursor.execute("""
                INSERT INTO soundwave.Suscripcion (Usuario_usuarioId, Plan_planId, fechaInicio, estado)
                VALUES (?, ?, GETDATE(), 'Activa')
            """, (usuario_id, plan_id))
            
            cursor.execute("SELECT suscripcionId FROM soundwave.Suscripcion WHERE Usuario_usuarioId = ? AND estado = 'Activa'", (usuario_id,))
            suscripcion_id = int(cursor.fetchone()[0])
            
            if account_type == 'premium':
                cursor.execute("""
                    INSERT INTO soundwave.Pago (monto, fechaPago, metodoPago, estado, Suscripcion_suscripcionId)
                    VALUES (?, GETDATE(), ?, ?, ?)
                """, (3.00, 'Tarjeta', 'Aprobado', suscripcion_id))
                
            conexion.commit()
            
            try:
                enviar_mensaje_whatsapp(phone, nombre_completo, account_type)
            except Exception as wa_err:
                print(f"[WhatsApp Integration] Error inesperado en el envío: {wa_err}")
                
            return jsonify({'success': True, 'message': 'Usuario registrado exitosamente.'})
        except Exception as e:
            if conexion:
                conexion.rollback()
            print(f"Error al registrar usuario: {e}")
            return jsonify({'success': False, 'message': f'Error en la base de datos: {str(e)}'}), 500
        finally:
            if conexion:
                conexion.close()

@app.route('/api/upgrade', methods=['POST'])
def api_upgrade():
    datos = request.get_json(silent=True) or request.form
    email = datos.get('email', '').strip()
    plan_nombre = datos.get('plan', '').strip()  # e.g., 'Individual', 'Estudiantes', 'Duo'
    price = datos.get('price', 0.0)
    
    if not email or not plan_nombre:
        return jsonify({'success': False, 'message': 'Faltan campos requeridos.'}), 400
        
    if database_type == 'mongodb':
        try:
            usuario = db_mongo.usuarios.find_one({"email": email, "$or": [{"eliminado": False}, {"eliminado": {"$exists": False}}]})
            if not usuario:
                return jsonify({'success': False, 'message': 'Usuario no encontrado.'}), 404
                
            usuario_id = usuario["usuarioId"]
            nombre_completo = f"{usuario['nombre']} {usuario['apellido']}".strip()
            phone = usuario.get('telefono')
            
            # Cancelar la suscripción activa actual
            db_mongo.usuarios.update_one(
                {"usuarioId": usuario_id, "suscripciones.estado": "Activa"},
                {"$set": {
                    "suscripciones.$[elem].estado": "Cancelada",
                    "suscripciones.$[elem].fechaFin": datetime.now()
                }},
                array_filters=[{"elem.estado": "Activa"}]
            )
            
            # Obtener ids máximos para suscripciones y pagos
            max_sub_id = 0
            max_pago_id = 0
            for u in db_mongo.usuarios.find():
                for s in u.get('suscripciones', []):
                    if s.get('suscripcionId', 0) > max_sub_id:
                        max_sub_id = s['suscripcionId']
                    for p in s.get('pagos', []):
                        if p.get('pagoId', 0) > max_pago_id:
                            max_pago_id = p['pagoId']
            
            new_sub_id = max_sub_id + 1
            new_pago_id = max_pago_id + 1
            
            # Insertar nueva suscripción premium activa con su pago
            nueva_sub = {
                "suscripcionId": new_sub_id,
                "fechaInicio": datetime.now(),
                "fechaFin": None,
                "estado": "Activa",
                "plan": {
                    "planId": 2,
                    "nombre": "Premium",
                    "precioMensual": 5.99,
                    "descripcion": "Música sin anuncios, descargas offline, audio HQ"
                },
                "pagos": [{
                    "pagoId": new_pago_id,
                    "monto": float(price),
                    "fechaPago": datetime.now(),
                    "metodoPago": f"Tarjeta (Premium {plan_nombre})",
                    "estado": "Aprobado"
                }]
            }
            
            db_mongo.usuarios.update_one(
                {"usuarioId": usuario_id},
                {"$push": {"suscripciones": nueva_sub}}
            )
            
            if phone:
                try:
                    enviar_mensaje_whatsapp(phone, nombre_completo, f"premium (Plan {plan_nombre})")
                except Exception as wa_err:
                    print(f"[WhatsApp] Error upgrade: {wa_err}")
                    
            return jsonify({'success': True, 'message': 'Suscripción actualizada a Premium exitosamente.'})
        except Exception as e:
            print(f"Error al actualizar suscripción en MongoDB: {e}")
            return jsonify({'success': False, 'message': f'Error en MongoDB: {str(e)}'}), 500
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            
            cursor.execute("SELECT usuarioId, nombre, apellido, telefono FROM soundwave.Usuario WHERE email = ? AND (eliminado = 0 OR eliminado IS NULL)", (email,))
            usuario_fila = cursor.fetchone()
            if not usuario_fila:
                return jsonify({'success': False, 'message': 'Usuario no encontrado.'}), 404
                
            usuario_id = int(usuario_fila.usuarioId)
            nombre_completo = f"{usuario_fila.nombre} {usuario_fila.apellido}".strip()
            phone = usuario_fila.telefono
            
            cursor.execute("SELECT planId FROM soundwave.PlanSuscripcion WHERE nombre = 'Premium'")
            fila_plan = cursor.fetchone()
            plan_id = fila_plan[0] if fila_plan else 2
            
            cursor.execute("SELECT suscripcionId, Plan_planId FROM soundwave.Suscripcion WHERE Usuario_usuarioId = ? AND estado = 'Activa'", (usuario_id,))
            fila_suscripcion = cursor.fetchone()
            
            if fila_suscripcion:
                suscripcion_id = int(fila_suscripcion[0])
                cursor.execute("UPDATE soundwave.Suscripcion SET Plan_planId = ?, fechaInicio = GETDATE() WHERE suscripcionId = ?", (plan_id, suscripcion_id))
            else:
                cursor.execute("""
                    INSERT INTO soundwave.Suscripcion (Usuario_usuarioId, Plan_planId, fechaInicio, estado)
                    VALUES (?, ?, GETDATE(), 'Activa')
                """, (usuario_id, plan_id))
                
                cursor.execute("SELECT suscripcionId FROM soundwave.Suscripcion WHERE Usuario_usuarioId = ? AND estado = 'Activa'", (usuario_id,))
                suscripcion_id = int(cursor.fetchone()[0])
                
            cursor.execute("""
                INSERT INTO soundwave.Pago (monto, fechaPago, metodoPago, estado, Suscripcion_suscripcionId)
                VALUES (?, GETDATE(), ?, ?, ?)
            """, (float(price), f"Tarjeta (Premium {plan_nombre})", 'Aprobado', suscripcion_id))
            
            conexion.commit()
            
            if phone:
                try:
                    enviar_mensaje_whatsapp(phone, nombre_completo, f"premium (Plan {plan_nombre})")
                except Exception as wa_err:
                    print(f"[WhatsApp Integration] Error inesperado en el envío de upgrade: {wa_err}")
                    
            return jsonify({'success': True, 'message': 'Suscripción actualizada a Premium exitosamente.'})
            
        except Exception as e:
            if conexion:
                conexion.rollback()
            print(f"Error al actualizar a premium: {e}")
            return jsonify({'success': False, 'message': f'Error en la base de datos: {str(e)}'}), 500
        finally:
            if conexion:
                conexion.close()

@app.route('/api/login', methods=['POST'])
def api_login():
    datos = request.get_json(silent=True) or request.form
    email = datos.get('email', '').strip()
    password = datos.get('password', '')
    
    if not email or not password:
        return jsonify({'success': False, 'message': 'Faltan campos requeridos.'}), 400
        
    if database_type == 'mongodb':
        try:
            usuario = db_mongo.usuarios.find_one({"email": email, "$or": [{"eliminado": False}, {"eliminado": {"$exists": False}}]})
            if not usuario:
                return jsonify({'success': False, 'message': 'El correo electrónico no está registrado.'}), 404
                
            if usuario["contraseña"] != password:
                return jsonify({'success': False, 'message': 'Contraseña incorrecta.'}), 401
                
            plan_nombre = 'Gratis'
            for s in usuario.get('suscripciones', []):
                if s.get('estado') == 'Activa':
                    plan_nombre = s.get('plan', {}).get('nombre', 'Gratis')
                    break
                    
            user_data = {
                'name': f"{usuario['nombre']} {usuario['apellido']}".strip(),
                'email': usuario['email'],
                'phone': usuario.get('telefono'),
                'accountType': 'premium' if plan_nombre == 'Premium' else 'normal'
            }
            return jsonify({'success': True, 'user': user_data})
        except Exception as e:
            print(f"Error api_login MongoDB: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            cursor.execute("""
                SELECT u.usuarioId, u.nombre, u.apellido, u.email, u.contraseña, u.telefono, ps.nombre AS planNombre
                FROM soundwave.Usuario u
                LEFT JOIN soundwave.Suscripcion s ON u.usuarioId = s.Usuario_usuarioId AND s.estado = 'Activa'
                LEFT JOIN soundwave.PlanSuscripcion ps ON s.Plan_planId = ps.planId
                WHERE u.email = ? AND (u.eliminado = 0 OR u.eliminado IS NULL)
            """, (email,))
            
            usuario = cursor.fetchone()
            if not usuario:
                return jsonify({'success': False, 'message': 'El correo electrónico no está registrado.'}), 404
                
            if usuario.contraseña != password:
                return jsonify({'success': False, 'message': 'Contraseña incorrecta.'}), 401
                
            user_data = {
                'name': f"{usuario.nombre} {usuario.apellido}".strip(),
                'email': usuario.email,
                'phone': usuario.telefono,
                'accountType': 'premium' if usuario.planNombre == 'Premium' else 'normal'
            }
            return jsonify({'success': True, 'user': user_data})
        except Exception as e:
            print(f"Error en api_login: {e}")
            return jsonify({'success': False, 'message': f'Error en la base de datos: {str(e)}'}), 500
        finally:
            if conexion:
                conexion.close()

@app.route('/api/forgot-password', methods=['POST'])
def api_forgot_password():
    datos = request.get_json(silent=True) or request.form
    email = datos.get('email', '').strip()
    
    if not email:
        return jsonify({'success': False, 'message': 'El correo electrónico es requerido.'}), 400
        
    if database_type == 'mongodb':
        try:
            usuario = db_mongo.usuarios.find_one({"email": email, "$or": [{"eliminado": False}, {"eliminado": {"$exists": False}}]})
            if not usuario:
                return jsonify({'success': False, 'message': 'El correo electrónico no está registrado.'}), 404
            return jsonify({'success': True, 'password': usuario['contraseña']})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            cursor.execute("SELECT contraseña FROM soundwave.Usuario WHERE email = ? AND (eliminado = 0 OR eliminado IS NULL)", (email,))
            usuario = cursor.fetchone()
            if not usuario:
                return jsonify({'success': False, 'message': 'El correo electrónico no está registrado.'}), 404
            return jsonify({'success': True, 'password': usuario.contraseña})
        except Exception as e:
            print(f"Error en api_forgot_password: {e}")
            return jsonify({'success': False, 'message': f'Error en la base de datos: {str(e)}'}), 500
        finally:
            if conexion:
                conexion.close()

# --- RUTAS ADMINISTRATIVAS (CRUD DISCOGRÁFICAS) ---
@app.route('/discograficas')
@admin_required
def discograficas():
    discograficas = []
    if database_type == 'mongodb':
        try:
            filas = list(db_mongo.discograficas.find({"$or": [{"eliminado": False}, {"eliminado": {"$exists": False}}]}))
            for fila in filas:
                fecha_str = fila['fechaFundacion'].strftime('%Y-%m-%d') if 'fechaFundacion' in fila and fila['fechaFundacion'] else 'N/A'
                discograficas.append({
                    'id': fila['discograficaId'],
                    'nombre': fila['nombre'],
                    'pais': fila['pais'],
                    'fechaFundacion': fecha_str
                })
        except Exception as e:
            print(f"Error discograficas MongoDB: {e}")
    else:
        conexion = get_db_connection()
        cursor = conexion.cursor()
        cursor.execute("{CALL soundwave.SP_ConsultarDiscograficas}")
        filas = cursor.fetchall()
        for fila in filas:
            fecha_str = fila.fechaFundacion.strftime('%Y-%m-%d') if hasattr(fila.fechaFundacion, 'strftime') else str(fila.fechaFundacion) if fila.fechaFundacion else 'N/A'
            discograficas.append({
                'id': fila.discograficaId,
                'nombre': fila.nombre,
                'pais': fila.pais,
                'fechaFundacion': fecha_str
            })
        conexion.close()
    return render_template('index.html', discograficas=discograficas)

@app.route('/create_discografica', methods=('GET', 'POST'))
@app.route('/create', methods=('GET', 'POST'))
@admin_required
def create():
    if request.method == 'POST':
        nombre = request.form['nombre']
        pais = request.form['pais']
        fecha = request.form['fechaFundacion']
        
        if not nombre or not pais:
            flash('El nombre y el país son obligatorios!', 'error')
        else:
            if database_type == 'mongodb':
                try:
                    max_d = db_mongo.discograficas.find_one(sort=[("discograficaId", -1)])
                    new_id = (max_d["discograficaId"] + 1) if max_d else 1
                    
                    fecha_dt = None
                    if fecha:
                        fecha_dt = datetime.strptime(fecha, '%Y-%m-%d')
                        
                    db_mongo.discograficas.insert_one({
                        "discograficaId": new_id,
                        "nombre": nombre,
                        "pais": pais,
                        "fechaFundacion": fecha_dt,
                        "eliminado": False
                    })
                    flash('Discográfica creada exitosamente!', 'success')
                    return redirect(url_for('discograficas'))
                except Exception as e:
                    flash(f'Error al crear registro en MongoDB: {e}', 'error')
            else:
                try:
                    conexion = get_db_connection()
                    cursor = conexion.cursor()
                    cursor.execute("{CALL soundwave.SP_InsertarDiscografica (?, ?, ?)}", (nombre, pais, fecha))
                    conexion.commit()
                    conexion.close()
                    flash('Discográfica creada exitosamente!', 'success')
                    return redirect(url_for('discograficas'))
                except Exception as e:
                    flash(f'Error al crear registro: {e}', 'error')
                    
    return render_template('create.html')

@app.route('/edit_discografica/<path:nombre_actual>', methods=('GET', 'POST'))
@admin_required
def edit(nombre_actual):
    discografica = None
    fecha_str = ''
    
    if database_type == 'mongodb':
        discografica_dict = db_mongo.discograficas.find_one({"nombre": nombre_actual})
        discografica = MongoRow(discografica_dict) if discografica_dict else None
        
        if request.method == 'POST':
            nombre_nuevo = request.form['nombre']
            pais = request.form['pais']
            fecha = request.form['fechaFundacion']
            
            if not nombre_nuevo.strip():
                nombre_nuevo = nombre_actual
                
            try:
                fecha_dt = None
                if fecha:
                    fecha_dt = datetime.strptime(fecha, '%Y-%m-%d')
                db_mongo.discograficas.update_one(
                    {"nombre": nombre_actual},
                    {"$set": {
                        "nombre": nombre_nuevo,
                        "pais": pais,
                        "fechaFundacion": fecha_dt
                    }}
                )
                
                # Actualizar denormalización en artistas
                db_mongo.artistas.update_many(
                    {"discograficaNombre": nombre_actual},
                    {"$set": {"discograficaNombre": nombre_nuevo}}
                )
                
                flash('Discográfica actualizada exitosamente!', 'success')
                return redirect(url_for('discograficas'))
            except Exception as e:
                flash(f'Error al actualizar registro en MongoDB: {e}', 'error')
        
        if discografica and discografica.fechaFundacion:
            fecha_str = discografica.fechaFundacion.strftime('%Y-%m-%d')
    else:
        conexion = get_db_connection()
        cursor = conexion.cursor()
        
        cursor.execute("{CALL soundwave.SP_ConsultarDiscograficas}")
        filas = cursor.fetchall()
        discografica = next((fila for fila in filas if fila.nombre == nombre_actual), None)
        
        if request.method == 'POST':
            nombre_nuevo = request.form['nombre']
            pais = request.form['pais']
            fecha = request.form['fechaFundacion']
            
            if not nombre_nuevo.strip():
                nombre_nuevo = nombre_actual
                
            try:
                cursor.execute("{CALL soundwave.SP_ActualizarDiscografica (?, ?, ?, ?)}", (nombre_actual, nombre_nuevo, pais, fecha))
                conexion.commit()
                flash('Discográfica actualizada exitosamente!', 'success')
                conexion.close()
                return redirect(url_for('discograficas'))
            except Exception as e:
                flash(f'Error al actualizar registro: {e}', 'error')
        
        if discografica and discografica.fechaFundacion:
            fecha_str = discografica.fechaFundacion.strftime('%Y-%m-%d') if hasattr(discografica.fechaFundacion, 'strftime') else str(discografica.fechaFundacion)
        conexion.close()
        
    return render_template('edit.html', discografica=discografica, nombre_actual=nombre_actual, fecha_str=fecha_str)

@app.route('/delete_discografica/<path:nombre>', methods=('POST',))
@admin_required
def delete(nombre):
    if database_type == 'mongodb':
        try:
            db_mongo.discograficas.update_one({"nombre": nombre}, {"$set": {"eliminado": True}})
            flash('Discográfica enviada a la papelera exitosamente!', 'success')
        except Exception as e:
            flash(f'Error al mover a papelera en MongoDB: {e}', 'error')
    else:
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            cursor.execute("{CALL soundwave.SP_EliminarDiscografica (?)}", (nombre,))
            conexion.commit()
            conexion.close()
            flash('Discográfica enviada a la papelera exitosamente!', 'success')
        except Exception as e:
            flash(f'Error al mover a la papelera: {e}', 'error')
    return redirect(url_for('discograficas'))

@app.route('/papelera')
@admin_required
def papelera():
    discograficas, artistas, canciones, playlists, usuarios = [], [], [], [], []
    if database_type == 'mongodb':
        try:
            # 1. Discográficas
            filas_d = list(db_mongo.discograficas.find({"eliminado": True}))
            for fila in filas_d:
                fecha_str = fila['fechaFundacion'].strftime('%Y-%m-%d') if 'fechaFundacion' in fila and fila['fechaFundacion'] else 'N/A'
                discograficas.append({
                    'id': fila['discograficaId'],
                    'nombre': fila['nombre'],
                    'pais': fila['pais'],
                    'fechaFundacion': fecha_str
                })
                
            # 2. Artistas
            filas_a = list(db_mongo.artistas.find({"eliminado": True}))
            for fila in filas_a:
                fecha_str = fila['fechaInicio'].strftime('%Y-%m-%d') if 'fechaInicio' in fila and fila['fechaInicio'] else 'N/A'
                artistas.append({
                    'artistaId': fila['artistaId'],
                    'nombreArtistico': fila['nombreArtistico'],
                    'pais': fila['pais'],
                    'fechaInicio': fecha_str,
                    'nombre': fila.get('discograficaNombre', 'Independiente')
                })
                
            # 3. Canciones
            pipeline = [
                {"$unwind": "$canciones"},
                {"$match": {"canciones.eliminado": True}},
                {"$project": {
                    "cancionId": "$canciones.cancionId",
                    "titulo": "$canciones.titulo",
                    "duracion": "$canciones.duracion",
                    "explicita": "$canciones.explicita",
                    "album": "$titulo"
                }}
            ]
            filas_c = list(db_mongo.albums.aggregate(pipeline))
            for fila in filas_c:
                canciones.append({
                    'cancionId': fila['cancionId'],
                    'titulo': fila['titulo'],
                    'duracion': fila['duracion'],
                    'explicita': bool(fila['explicita']),
                    'album': fila['album']
                })
                
            # 4. Playlists
            filas_p = list(db_mongo.playlists.find({"eliminado": True}))
            for fila in filas_p:
                playlists.append({
                    'playlistId': fila['playlistId'],
                    'nombre': fila['nombre'],
                    'privacidad': fila['privacidad'],
                    'creador': fila.get('usuarioNombre', 'Usuario')
                })
                
            # 5. Usuarios
            filas_u = list(db_mongo.usuarios.find({"eliminado": True}))
            for fila in filas_u:
                usuarios.append({
                    'usuarioId': fila['usuarioId'],
                    'nombre': fila['nombre'],
                    'apellido': fila['apellido'],
                    'email': fila['email'],
                    'pais': fila['pais'],
                    'estado': fila['estado']
                })
        except Exception as e:
            flash(f"Error al cargar la papelera MongoDB: {e}", "error")
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            
            cursor.execute("{CALL soundwave.SP_ConsultarDiscograficasEliminadas}")
            filas_d = cursor.fetchall()
            for fila in filas_d:
                fecha_str = fila.fechaFundacion.strftime('%Y-%m-%d') if hasattr(fila.fechaFundacion, 'strftime') else str(fila.fechaFundacion) if fila.fechaFundacion else 'N/A'
                discograficas.append({
                    'id': fila.discograficaId,
                    'nombre': fila.nombre,
                    'pais': fila.pais,
                    'fechaFundacion': fecha_str
                })
                
            cursor.execute("{CALL soundwave.SP_ConsultarArtistasEliminados}")
            filas_a = cursor.fetchall()
            for fila in filas_a:
                fecha_str = fila.fechaInicio.strftime('%Y-%m-%d') if hasattr(fila.fechaInicio, 'strftime') else str(fila.fechaInicio) if fila.fechaInicio else 'N/A'
                artistas.append({
                    'artistaId': fila.artistaId,
                    'nombreArtistico': fila.nombreArtistico,
                    'pais': fila.pais,
                    'fechaInicio': fecha_str,
                    'nombre': fila.nombre
                })
                
            cursor.execute("{CALL soundwave.SP_ConsultarCancionesEliminadas}")
            filas_c = cursor.fetchall()
            for fila in filas_c:
                canciones.append({
                    'cancionId': fila.cancionId,
                    'titulo': fila.titulo,
                    'duracion': fila.duracion,
                    'explicita': bool(fila.explicita),
                    'album': fila.album
                })
                
            cursor.execute("{CALL soundwave.SP_ConsultarPlaylistsEliminadas}")
            filas_p = cursor.fetchall()
            for fila in filas_p:
                playlists.append({
                    'playlistId': fila.playlistId,
                    'nombre': fila.nombre,
                    'privacidad': fila.privacidad,
                    'creador': fila.creador
                })
                
            cursor.execute("SELECT usuarioId, nombre, apellido, email, pais, estado FROM soundwave.Usuario WHERE eliminado = 1")
            filas_u = cursor.fetchall()
            for fila in filas_u:
                usuarios.append({
                    'usuarioId': fila.usuarioId,
                    'nombre': fila.nombre,
                    'apellido': fila.apellido,
                    'email': fila.email,
                    'pais': fila.pais,
                    'estado': fila.estado
                })
        except Exception as e:
            flash(f"Error al cargar la papelera: {e}", "error")
        finally:
            if conexion:
                conexion.close()
                
    return render_template(
        'papelera.html', 
        discograficas=discograficas,
        artistas=artistas,
        canciones=canciones,
        playlists=playlists,
        usuarios=usuarios
    )

@app.route('/restore_discografica/<path:nombre>', methods=('POST',))
@admin_required
def restore(nombre):
    if database_type == 'mongodb':
        try:
            db_mongo.discograficas.update_one({"nombre": nombre}, {"$set": {"eliminado": False}})
            flash('Discográfica restaurada exitosamente!', 'success')
        except Exception as e:
            flash(f'Error al restaurar: {e}', 'error')
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            cursor.execute("{CALL soundwave.SP_RestaurarDiscografica (?)}", (nombre,))
            conexion.commit()
            flash('Discográfica restaurada exitosamente!', 'success')
        except Exception as e:
            flash(f'Error al restaurar discográfica: {e}', 'error')
        finally:
            if conexion:
                conexion.close()
    return redirect(url_for('papelera'))

@app.route('/delete_permanent_discografica/<path:nombre>', methods=('POST',))
@admin_required
def delete_permanent(nombre):
    if database_type == 'mongodb':
        try:
            # Validar si tiene artistas vinculados
            disc = db_mongo.discograficas.find_one({"nombre": nombre})
            if disc:
                has_artists = db_mongo.artistas.count_documents({"discograficaId": disc["discograficaId"]}) > 0
                if has_artists:
                    flash('No se puede eliminar permanentemente: la discográfica tiene artistas vinculados en la base de datos.', 'error')
                else:
                    db_mongo.discograficas.delete_one({"nombre": nombre})
                    flash('Discográfica eliminada permanentemente del sistema!', 'success')
        except Exception as e:
            flash(f'Error en MongoDB: {e}', 'error')
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            cursor.execute("{CALL soundwave.SP_EliminarFisicoDiscografica (?)}", (nombre,))
            conexion.commit()
            flash('Discográfica eliminada permanentemente del sistema!', 'success')
        except Exception as e:
            flash('No se puede eliminar permanentemente: la discográfica tiene artistas vinculados en la base de datos.', 'error')
        finally:
            if conexion:
                conexion.close()
    return redirect(url_for('papelera'))

# --- CRUD ARTISTAS ---
@app.route('/create_artista', methods=('GET', 'POST'))
@admin_required
def create_artista():
    discograficas = []
    if database_type == 'mongodb':
        try:
            if request.method == 'POST':
                nombre_artistico = request.form['nombreArtistico']
                pais = request.form['pais']
                fecha_inicio = request.form['fechaInicio']
                discografica_id = request.form['discograficaId']
                
                discografica_id = int(discografica_id) if discografica_id else None
                
                if not nombre_artistico or not pais or not fecha_inicio:
                    flash('¡Todos los campos obligatorios deben estar llenos!', 'error')
                else:
                    max_a = db_mongo.artistas.find_one(sort=[("artistaId", -1)])
                    new_id = (max_a["artistaId"] + 1) if max_a else 1
                    
                    fecha_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
                    
                    disc_nombre = "Independiente"
                    if discografica_id:
                        d_doc = db_mongo.discograficas.find_one({"discograficaId": discografica_id})
                        if d_doc:
                            disc_nombre = d_doc["nombre"]
                            
                    db_mongo.artistas.insert_one({
                        "artistaId": new_id,
                        "nombreArtistico": nombre_artistico,
                        "pais": pais,
                        "fechaInicio": fecha_dt,
                        "discograficaId": discografica_id,
                        "discograficaNombre": disc_nombre,
                        "eliminado": False
                    })
                    flash('¡Artista creado exitosamente!', 'success')
                    return redirect(url_for('artistas'))
                    
            filas_d = list(db_mongo.discograficas.find({"$or": [{"eliminado": False}, {"eliminado": {"$exists": False}}]}))
            discograficas = [MongoRow(d) for d in filas_d]
        except Exception as e:
            flash(f'Error al crear artista en MongoDB: {e}', 'error')
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            
            if request.method == 'POST':
                nombre_artistico = request.form['nombreArtistico']
                pais = request.form['pais']
                fecha_inicio = request.form['fechaInicio']
                discografica_id = request.form['discograficaId']
                
                discografica_id = int(discografica_id) if discografica_id else None
                
                if not nombre_artistico or not pais or not fecha_inicio:
                    flash('¡Todos los campos obligatorios deben estar llenos!', 'error')
                else:
                    cursor.execute("{CALL soundwave.SP_InsertarArtista (?, ?, ?, ?)}", 
                                   (nombre_artistico, pais, fecha_inicio, discografica_id))
                    conexion.commit()
                    flash('¡Artista creado exitosamente!', 'success')
                    return redirect(url_for('artistas'))
                    
            cursor.execute("{CALL soundwave.SP_ConsultarDiscograficas}")
            discograficas = cursor.fetchall()
        except Exception as e:
            flash(f'Error al procesar artista: {e}', 'error')
        finally:
            if conexion:
                conexion.close()
    return render_template('create_artista.html', discograficas=discograficas)

@app.route('/edit_artista/<int:artista_id>', methods=('GET', 'POST'))
@admin_required
def edit_artista(artista_id):
    artista = None
    discograficas = []
    fecha_str = ''
    
    if database_type == 'mongodb':
        try:
            art_dict = db_mongo.artistas.find_one({"artistaId": artista_id})
            artista = MongoRow(art_dict) if art_dict else None
            
            if request.method == 'POST':
                nombre_artistico = request.form['nombreArtistico']
                pais = request.form['pais']
                fecha_inicio = request.form['fechaInicio']
                discografica_id = request.form['discograficaId']
                
                discografica_id = int(discografica_id) if discografica_id else None
                fecha_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
                
                disc_nombre = "Independiente"
                if discografica_id:
                    d_doc = db_mongo.discograficas.find_one({"discograficaId": discografica_id})
                    if d_doc:
                        disc_nombre = d_doc["nombre"]
                        
                db_mongo.artistas.update_one(
                    {"artistaId": artista_id},
                    {"$set": {
                        "nombreArtistico": nombre_artistico,
                        "pais": pais,
                        "fechaInicio": fecha_dt,
                        "discograficaId": discografica_id,
                        "discograficaNombre": disc_nombre
                    }}
                )
                
                # Actualizar denormalización en álbumes
                db_mongo.albums.update_many(
                    {"artistaId": artista_id},
                    {"$set": {"artistaNombre": nombre_artistico}}
                )
                
                flash('¡Artista actualizado exitosamente!', 'success')
                return redirect(url_for('artistas'))
                
            filas_d = list(db_mongo.discograficas.find({"$or": [{"eliminado": False}, {"eliminado": {"$exists": False}}]}))
            discograficas = [MongoRow(d) for d in filas_d]
            if artista and artista.fechaInicio:
                fecha_str = artista.fechaInicio.strftime('%Y-%m-%d')
        except Exception as e:
            flash(f'Error en MongoDB: {e}', 'error')
            return redirect(url_for('artistas'))
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            
            if request.method == 'POST':
                nombre_artistico = request.form['nombreArtistico']
                pais = request.form['pais']
                fecha_inicio = request.form['fechaInicio']
                discografica_id = request.form['discograficaId']
                
                discografica_id = int(discografica_id) if discografica_id else None
                
                cursor.execute("{CALL soundwave.SP_ActualizarArtista (?, ?, ?, ?, ?)}", 
                               (artista_id, nombre_artistico, pais, fecha_inicio, discografica_id))
                conexion.commit()
                flash('¡Artista actualizado exitosamente!', 'success')
                return redirect(url_for('artistas'))
                
            cursor.execute("SELECT artistaId, nombreArtistico, pais, fechaInicio, Discografica_discograficaId FROM soundwave.Artista WHERE artistaId = ?", (artista_id,))
            fila = cursor.fetchone()
            if not fila:
                flash('Artista no encontrado.', 'error')
                return redirect(url_for('artistas'))
                
            artista = {
                'artistaId': fila.artistaId,
                'nombreArtistico': fila.nombreArtistico,
                'pais': fila.pais,
                'fechaInicio': fila.fechaInicio,
                'discograficaId': fila.Discografica_discograficaId
            }
            fecha_str = artista['fechaInicio'].strftime('%Y-%m-%d') if hasattr(artista['fechaInicio'], 'strftime') else str(artista['fechaInicio']) if artista['fechaInicio'] else ''
            
            cursor.execute("{CALL soundwave.SP_ConsultarDiscograficas}")
            discograficas = cursor.fetchall()
        except Exception as e:
            flash(f'Error al editar artista: {e}', 'error')
            return redirect(url_for('artistas'))
        finally:
            if conexion:
                conexion.close()
                
    return render_template('edit_artista.html', artista=artista, discograficas=discograficas, fecha_str=fecha_str)

@app.route('/delete_artista/<int:artista_id>', methods=('POST',))
@admin_required
def delete_artista(artista_id):
    if database_type == 'mongodb':
        try:
            # Regla de negocio: No se puede eliminar si tiene canciones (en álbumes)
            has_songs = db_mongo.albums.count_documents({"artistaId": artista_id, "canciones": {"$exists": True, "$ne": []}}) > 0
            if has_songs:
                flash('No se puede eliminar el artista porque tiene canciones y álbumes vinculados en la plataforma.', 'error')
            else:
                db_mongo.artistas.update_one({"artistaId": artista_id}, {"$set": {"eliminado": True}})
                flash('¡Artista enviado a la papelera exitosamente!', 'success')
        except Exception as e:
            flash(f'Error en MongoDB: {e}', 'error')
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            cursor.execute("{CALL soundwave.SP_EliminarArtista (?)}", (artista_id,))
            conexion.commit()
            flash('¡Artista enviado a la papelera exitosamente!', 'success')
        except Exception as e:
            flash(f'Error al mover artista a la papelera: {e}', 'error')
        finally:
            if conexion:
                conexion.close()
    return redirect(url_for('artistas'))

@app.route('/restore_artista/<int:artista_id>', methods=('POST',))
@admin_required
def restore_artista(artista_id):
    if database_type == 'mongodb':
        try:
            db_mongo.artistas.update_one({"artistaId": artista_id}, {"$set": {"eliminado": False}})
            flash('¡Artista restaurado exitosamente!', 'success')
        except Exception as e:
            flash(f'Error en MongoDB: {e}', 'error')
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            cursor.execute("{CALL soundwave.SP_RestaurarArtista (?)}", (artista_id,))
            conexion.commit()
            flash('¡Artista restaurado exitosamente!', 'success')
        except Exception as e:
            flash(f'Error al restaurar artista: {e}', 'error')
        finally:
            if conexion:
                conexion.close()
    return redirect(url_for('papelera') + '#tab-artistas')

@app.route('/delete_permanent_artista/<int:artista_id>', methods=('POST',))
@admin_required
def delete_permanent_artista(artista_id):
    if database_type == 'mongodb':
        try:
            # Validar si tiene álbumes
            has_albums = db_mongo.albums.count_documents({"artistaId": artista_id}) > 0
            if has_albums:
                flash('No se puede eliminar permanentemente: el artista tiene álbumes o canciones vinculados en la base de datos.', 'error')
            else:
                db_mongo.artistas.delete_one({"artistaId": artista_id})
                flash('¡Artista eliminado permanentemente del sistema!', 'success')
        except Exception as e:
            flash(f'Error en MongoDB: {e}', 'error')
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            cursor.execute("{CALL soundwave.SP_EliminarFisicoArtista (?)}", (artista_id,))
            conexion.commit()
            flash('¡Artista eliminado permanentemente del sistema!', 'success')
        except Exception as e:
            flash('No se puede eliminar permanentemente: el artista tiene álbumes o canciones vinculados en la base de datos.', 'error')
        finally:
            if conexion:
                conexion.close()
    return redirect(url_for('papelera') + '#tab-artistas')

# --- CRUD CANCIONES ---
@app.route('/create_cancion', methods=('GET', 'POST'))
@admin_required
def create_cancion():
    albumes = []
    generos = []
    
    if database_type == 'mongodb':
        try:
            if request.method == 'POST':
                titulo = request.form['titulo']
                duracion = request.form['duracion']
                explicita = True if request.form.get('explicita') else False
                album_id = request.form['albumId']
                generos_seleccionados = request.form.getlist('generos')
                
                if not titulo or not duracion or not album_id:
                    flash('¡Título, duración y álbum son obligatorios!', 'error')
                else:
                    # Encontrar máximo cancionId
                    max_c = 0
                    for al in db_mongo.albums.find():
                        for c in al.get('canciones', []):
                            if c.get('cancionId', 0) > max_c:
                                max_c = c['cancionId']
                    new_cancion_id = max_c + 1
                    
                    # Traducir géneros (en Mongo, guardamos nombres directamente o IDs)
                    # Para simplificar y desnormalizar:
                    gen_names = []
                    # Mapeo hardcoded de IDs de mock de géneros a nombres
                    gen_map = {"1": "Reggaeton", "2": "Pop", "3": "Urbano", "4": "Indie", "5": "Dance"}
                    for gid in generos_seleccionados:
                        if gid in gen_map:
                            gen_names.append(gen_map[gid])
                            
                    nueva_cancion = {
                        "cancionId": new_cancion_id,
                        "titulo": titulo,
                        "duracion": int(duracion),
                        "explicita": explicita,
                        "eliminado": False,
                        "generos": gen_names
                    }
                    
                    db_mongo.albums.update_one(
                        {"albumId": int(album_id)},
                        {"$push": {"canciones": nueva_cancion}}
                    )
                    
                    flash('¡Canción creada exitosamente!', 'success')
                    return redirect(url_for('canciones'))
                    
            filas_al = list(db_mongo.albums.find())
            albumes = [{'id': f['albumId'], 'titulo': f['titulo'], 'artista': f.get('artistaNombre', 'Artista')} for f in filas_al]
            generos = [{'id': 1, 'nombre': 'Reggaeton'}, {'id': 2, 'nombre': 'Pop'}, {'id': 3, 'nombre': 'Urbano'}, {'id': 4, 'nombre': 'Indie'}, {'id': 5, 'nombre': 'Dance'}]
        except Exception as e:
            flash(f'Error en MongoDB: {e}', 'error')
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            
            if request.method == 'POST':
                titulo = request.form['titulo']
                duracion = request.form['duracion']
                explicita = 1 if request.form.get('explicita') else 0
                album_id = request.form['albumId']
                generos_seleccionados = request.form.getlist('generos')
                
                if not titulo or not duracion or not album_id:
                    flash('¡Título, duración y álbum son obligatorios!', 'error')
                else:
                    cursor.execute("{CALL soundwave.SP_InsertarCancion (?, ?, ?, ?)}", 
                                   (titulo, int(duracion), explicita, int(album_id)))
                    fila = cursor.fetchone()
                    cancion_id = fila[0] if fila else None
                    
                    if cancion_id and generos_seleccionados:
                        for gen_id in generos_seleccionados:
                            cursor.execute("INSERT INTO soundwave.CancionGenero (Cancion_cancionId, Genero_generoId) VALUES (?, ?)", 
                                           (cancion_id, int(gen_id)))
                    conexion.commit()
                    flash('¡Canción creada exitosamente!', 'success')
                    return redirect(url_for('canciones'))
                    
            cursor.execute("SELECT al.albumId, al.titulo, ar.nombreArtistico FROM soundwave.Album al JOIN soundwave.Artista ar ON al.Artista_artistaId = ar.artistaId")
            albumes_filas = cursor.fetchall()
            albumes = [{'id': f.albumId, 'titulo': f.titulo, 'artista': f.nombreArtistico} for f in albumes_filas]
            
            cursor.execute("SELECT generoId, nombre FROM soundwave.Genero ORDER BY nombre")
            generos_filas = cursor.fetchall()
            generos = [{'id': f.generoId, 'nombre': f.nombre} for f in generos_filas]
        except Exception as e:
            flash(f'Error al crear canción: {e}', 'error')
        finally:
            if conexion:
                conexion.close()
    return render_template('create_cancion.html', albumes=albumes, generos=generos)

@app.route('/edit_cancion/<int:cancion_id>', methods=('GET', 'POST'))
@admin_required
def edit_cancion(cancion_id):
    cancion = None
    albumes = []
    generos = []
    generos_asociados = []
    
    if database_type == 'mongodb':
        try:
            # Buscar la canción en los álbumes
            album_doc = db_mongo.albums.find_one({"canciones.cancionId": cancion_id})
            if album_doc:
                for c in album_doc.get('canciones', []):
                    if c.get('cancionId') == cancion_id:
                        cancion = MongoRow({
                            'cancionId': c['cancionId'],
                            'titulo': c['titulo'],
                            'duracion': c['duracion'],
                            'explicita': bool(c.get('explicita')),
                            'albumId': album_doc['albumId']
                        })
                        
                        # Mapear géneros asociados a IDs ficticios
                        gen_map_reverse = {"Reggaeton": 1, "Pop": 2, "Urbano": 3, "Indie": 4, "Dance": 5}
                        for gname in c.get('generos', []):
                            if gname in gen_map_reverse:
                                generos_asociados.append(gen_map_reverse[gname])
                        break
                        
            if request.method == 'POST':
                titulo = request.form['titulo']
                duracion = request.form['duracion']
                explicita = True if request.form.get('explicita') else False
                album_id = request.form['albumId']
                generos_seleccionados = request.form.getlist('generos')
                
                # Traducir géneros
                gen_names = []
                gen_map = {"1": "Reggaeton", "2": "Pop", "3": "Urbano", "4": "Indie", "5": "Dance"}
                for gid in generos_seleccionados:
                    if gid in gen_map:
                        gen_names.append(gen_map[gid])
                        
                # 1. Sacarla del álbum anterior si cambió de álbum
                if album_doc and album_doc['albumId'] != int(album_id):
                    # Quitar de viejo
                    db_mongo.albums.update_one(
                        {"albumId": album_doc['albumId']},
                        {"$pull": {"canciones": {"cancionId": cancion_id}}}
                    )
                    # Agregar a nuevo
                    nueva_c = {
                        "cancionId": cancion_id,
                        "titulo": titulo,
                        "duracion": int(duracion),
                        "explicita": explicita,
                        "eliminado": False,
                        "generos": gen_names
                    }
                    db_mongo.albums.update_one(
                        {"albumId": int(album_id)},
                        {"$push": {"canciones": nueva_c}}
                    )
                else:
                    # Actualizar en el mismo álbum
                    db_mongo.albums.update_one(
                        {"canciones.cancionId": cancion_id},
                        {"$set": {
                            "canciones.$.titulo": titulo,
                            "canciones.$.duracion": int(duracion),
                            "canciones.$.explicita": explicita,
                            "canciones.$.generos": gen_names
                        }}
                    )
                    
                flash('¡Canción actualizada exitosamente!', 'success')
                return redirect(url_for('canciones'))
                
            filas_al = list(db_mongo.albums.find())
            albumes = [{'id': f['albumId'], 'titulo': f['titulo'], 'artista': f.get('artistaNombre', 'Artista')} for f in filas_al]
            generos = [{'id': 1, 'nombre': 'Reggaeton'}, {'id': 2, 'nombre': 'Pop'}, {'id': 3, 'nombre': 'Urbano'}, {'id': 4, 'nombre': 'Indie'}, {'id': 5, 'nombre': 'Dance'}]
        except Exception as e:
            flash(f'Error en MongoDB: {e}', 'error')
            return redirect(url_for('canciones'))
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            
            if request.method == 'POST':
                titulo = request.form['titulo']
                duracion = request.form['duracion']
                explicita = 1 if request.form.get('explicita') else 0
                album_id = request.form['albumId']
                generos_seleccionados = request.form.getlist('generos')
                
                cursor.execute("{CALL soundwave.SP_ActualizarCancion (?, ?, ?, ?, ?)}", 
                               (cancion_id, titulo, int(duracion), explicita, int(album_id)))
                
                cursor.execute("DELETE FROM soundwave.CancionGenero WHERE Cancion_cancionId = ?", (cancion_id,))
                if generos_seleccionados:
                    for gen_id in generos_seleccionados:
                        cursor.execute("INSERT INTO soundwave.CancionGenero (Cancion_cancionId, Genero_generoId) VALUES (?, ?)", 
                                       (cancion_id, int(gen_id)))
                conexion.commit()
                flash('¡Canción actualizada exitosamente!', 'success')
                return redirect(url_for('canciones'))
                
            cursor.execute("SELECT cancionId, titulo, duracion, explicita, Album_albumId FROM soundwave.Cancion WHERE cancionId = ?", (cancion_id,))
            fila = cursor.fetchone()
            if not fila:
                flash('Canción no encontrada.', 'error')
                return redirect(url_for('canciones'))
                
            cancion = {
                'cancionId': fila.cancionId,
                'titulo': fila.titulo,
                'duracion': fila.duracion,
                'explicita': bool(fila.explicita),
                'albumId': fila.Album_albumId
            }
            
            cursor.execute("SELECT al.albumId, al.titulo, ar.nombreArtistico FROM soundwave.Album al JOIN soundwave.Artista ar ON al.Artista_artistaId = ar.artistaId")
            albumes_filas = cursor.fetchall()
            albumes = [{'id': f.albumId, 'titulo': f.titulo, 'artista': f.nombreArtistico} for f in albumes_filas]
            
            cursor.execute("SELECT generoId, nombre FROM soundwave.Genero ORDER BY nombre")
            generos_filas = cursor.fetchall()
            generos = [{'id': f.generoId, 'nombre': f.nombre} for f in generos_filas]
            
            cursor.execute("SELECT Genero_generoId FROM soundwave.CancionGenero WHERE Cancion_cancionId = ?", (cancion_id,))
            generos_asociados = [f[0] for f in cursor.fetchall()]
        except Exception as e:
            flash(f'Error al editar canción: {e}', 'error')
            return redirect(url_for('canciones'))
        finally:
            if conexion:
                conexion.close()
    return render_template('edit_cancion.html', cancion=cancion, albumes=albumes, generos=generos, generos_asociados=generos_asociados)

@app.route('/delete_cancion/<int:cancion_id>', methods=('POST',))
@admin_required
def delete_cancion(cancion_id):
    if database_type == 'mongodb':
        try:
            db_mongo.albums.update_one(
                {"canciones.cancionId": cancion_id},
                {"$set": {"canciones.$.eliminado": True}}
            )
            flash('¡Canción enviada a la papelera exitosamente!', 'success')
        except Exception as e:
            flash(f'Error en MongoDB: {e}', 'error')
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            cursor.execute("{CALL soundwave.SP_EliminarCancion (?)}", (cancion_id,))
            conexion.commit()
            flash('¡Canción enviada a la papelera exitosamente!', 'success')
        except Exception as e:
            flash(f'Error al mover canción a la papelera: {e}', 'error')
        finally:
            if conexion:
                conexion.close()
    return redirect(url_for('canciones'))

@app.route('/restore_cancion/<int:cancion_id>', methods=('POST',))
@admin_required
def restore_cancion(cancion_id):
    if database_type == 'mongodb':
        try:
            db_mongo.albums.update_one(
                {"canciones.cancionId": cancion_id},
                {"$set": {"canciones.$.eliminado": False}}
            )
            flash('¡Canción restaurada exitosamente!', 'success')
        except Exception as e:
            flash(f'Error en MongoDB: {e}', 'error')
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            cursor.execute("{CALL soundwave.SP_RestaurarCancion (?)}", (cancion_id,))
            conexion.commit()
            flash('¡Canción restaurada exitosamente!', 'success')
        except Exception as e:
            flash(f'Error al restaurar canción: {e}', 'error')
        finally:
            if conexion:
                conexion.close()
    return redirect(url_for('papelera') + '#tab-canciones')

@app.route('/delete_permanent_cancion/<int:cancion_id>', methods=('POST',))
@admin_required
def delete_permanent_cancion(cancion_id):
    if database_type == 'mongodb':
        try:
            db_mongo.albums.update_one(
                {"canciones.cancionId": cancion_id},
                {"$pull": {"canciones": {"cancionId": cancion_id}}}
            )
            flash('¡Canción eliminada permanentemente del sistema!', 'success')
        except Exception as e:
            flash(f'Error en MongoDB: {e}', 'error')
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            cursor.execute("{CALL soundwave.SP_EliminarFisicoCancion (?)}", (cancion_id,))
            conexion.commit()
            flash('¡Canción eliminada permanentemente del sistema!', 'success')
        except Exception as e:
            flash(f'Error al eliminar permanentemente la canción: {e}', 'error')
        finally:
            if conexion:
                conexion.close()
    return redirect(url_for('papelera') + '#tab-canciones')

# --- CRUD PLAYLISTS ---
@app.route('/create_playlist', methods=('GET', 'POST'))
@admin_required
def create_playlist():
    usuarios = []
    if database_type == 'mongodb':
        try:
            if request.method == 'POST':
                nombre = request.form.get('nombre', '').strip()
                privacidad = request.form.get('privacidad', '').strip()
                usuario_id = request.form.get('usuarioId', '').strip()
                nuevo_creador = request.form.get('nuevoCreador', '').strip()
                
                if not nombre or not privacidad or (not usuario_id and not nuevo_creador):
                    flash('¡El nombre, privacidad y el creador son obligatorios!', 'error')
                else:
                    import random
                    if nuevo_creador:
                        partes = nuevo_creador.split(' ', 1)
                        nombre_nuevo = partes[0]
                        apellido_nuevo = partes[1] if len(partes) > 1 else ''
                        
                        email_safe_nombre = ''.join(c for c in nombre_nuevo if c.isalnum()).lower()
                        email_safe_apellido = ''.join(c for c in apellido_nuevo if c.isalnum()).lower() if apellido_nuevo else 'creador'
                        
                        suffix = random.randint(1000, 9999)
                        dummy_email = f"{email_safe_nombre}.{email_safe_apellido}.{suffix}@soundwave.com"
                        while db_mongo.usuarios.find_one({"email": dummy_email}):
                            suffix = random.randint(1000, 9999)
                            dummy_email = f"{email_safe_nombre}.{email_safe_apellido}.{suffix}@soundwave.com"
                            
                        # Registrar nuevo usuario
                        max_u = db_mongo.usuarios.find_one(sort=[("usuarioId", -1)])
                        usuario_id = (max_u["usuarioId"] + 1) if max_u else 1
                        
                        max_sub_id = 0
                        for u in db_mongo.usuarios.find():
                            for s in u.get('suscripciones', []):
                                if s.get('suscripcionId', 0) > max_sub_id:
                                    max_sub_id = s['suscripcionId']
                        new_sub_id = max_sub_id + 1
                        
                        nuevo_usuario = {
                            "usuarioId": usuario_id,
                            "nombre": nombre_nuevo,
                            "apellido": apellido_nuevo,
                            "email": dummy_email,
                            "contraseña": "1234",
                            "pais": "Ecuador",
                            "estado": "Activa",
                            "telefono": None,
                            "eliminado": False,
                            "suscripciones": [{
                                "suscripcionId": new_sub_id,
                                "fechaInicio": datetime.now(),
                                "fechaFin": None,
                                "estado": "Activa",
                                "plan": {
                                    "planId": 1,
                                    "nombre": "Gratis",
                                    "precioMensual": 0.00,
                                    "descripcion": "Música con anuncios, saltos limitados"
                                },
                                "pagos": []
                            }]
                        }
                        db_mongo.usuarios.insert_one(nuevo_usuario)
                        creador_nombre = f"{nombre_nuevo} {apellido_nuevo}".strip()
                    else:
                        usuario_id = int(usuario_id)
                        u_doc = db_mongo.usuarios.find_one({"usuarioId": usuario_id})
                        creador_nombre = f"{u_doc['nombre']} {u_doc['apellido']}".strip() if u_doc else "Usuario"
                        
                    # Crear Playlist
                    max_p = db_mongo.playlists.find_one(sort=[("playlistId", -1)])
                    playlist_id = (max_p["playlistId"] + 1) if max_p else 1
                    
                    db_mongo.playlists.insert_one({
                        "playlistId": playlist_id,
                        "nombre": nombre,
                        "fechaCreacion": datetime.now(),
                        "privacidad": privacidad,
                        "usuarioId": usuario_id,
                        "usuarioNombre": creador_nombre,
                        "eliminado": False,
                        "canciones": []
                    })
                    
                    flash('¡Playlist creada exitosamente!', 'success')
                    return redirect(url_for('playlists'))
                    
            filas_u = list(db_mongo.usuarios.find({"$or": [{"eliminado": False}, {"eliminado": {"$exists": False}}]}))
            usuarios = [{'usuarioId': u['usuarioId'], 'nombre': u['nombre'], 'apellido': u['apellido'], 'email': u['email']} for u in filas_u]
        except Exception as e:
            flash(f'Error en MongoDB: {e}', 'error')
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            
            if request.method == 'POST':
                nombre = request.form.get('nombre', '').strip()
                privacidad = request.form.get('privacidad', '').strip()
                usuario_id = request.form.get('usuarioId', '').strip()
                nuevo_creador = request.form.get('nuevoCreador', '').strip()
                
                if not nombre or not privacidad or (not usuario_id and not nuevo_creador):
                    flash('¡El nombre, privacidad y el creador son obligatorios!', 'error')
                else:
                    import random
                    if nuevo_creador:
                        partes = nuevo_creador.split(' ', 1)
                        nombre_nuevo = partes[0]
                        apellido_nuevo = partes[1] if len(partes) > 1 else ''
                        
                        email_safe_nombre = ''.join(c for c in nombre_nuevo if c.isalnum()).lower()
                        email_safe_apellido = ''.join(c for c in apellido_nuevo if c.isalnum()).lower() if apellido_nuevo else 'creador'
                        
                        suffix = random.randint(1000, 9999)
                        dummy_email = f"{email_safe_nombre}.{email_safe_apellido}.{suffix}@soundwave.com"
                        while True:
                            cursor.execute("SELECT COUNT(*) FROM soundwave.Usuario WHERE email = ?", (dummy_email,))
                            if cursor.fetchone()[0] == 0:
                                break
                            suffix = random.randint(1000, 9999)
                            dummy_email = f"{email_safe_nombre}.{email_safe_apellido}.{suffix}@soundwave.com"
                            
                        cursor.execute("""
                            INSERT INTO soundwave.Usuario (nombre, apellido, email, contraseña, pais, estado, telefono)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (nombre_nuevo, apellido_nuevo, dummy_email, '1234', 'Ecuador', 'Activa', None))
                        
                        cursor.execute("SELECT usuarioId FROM soundwave.Usuario WHERE email = ?", (dummy_email,))
                        usuario_id = int(cursor.fetchone()[0])
                        
                        cursor.execute("SELECT planId FROM soundwave.PlanSuscripcion WHERE nombre = 'Gratis'")
                        fila_plan = cursor.fetchone()
                        plan_id = fila_plan[0] if fila_plan else 1
                        
                        cursor.execute("""
                            INSERT INTO soundwave.Suscripcion (Usuario_usuarioId, Plan_planId, fechaInicio, estado)
                            VALUES (?, ?, GETDATE(), 'Activa')
                        """, (usuario_id, plan_id))
                    
                    cursor.execute("{CALL soundwave.SP_InsertarPlaylist (?, ?, ?)}", 
                                   (nombre, privacidad, int(usuario_id)))
                    conexion.commit()
                    flash('¡Playlist creada exitosamente!', 'success')
                    return redirect(url_for('playlists'))
                    
            cursor.execute("SELECT usuarioId, nombre, apellido, email FROM soundwave.Usuario WHERE eliminado = 0 OR eliminado IS NULL ORDER BY nombre")
            usuarios = [
                {'usuarioId': f.usuarioId, 'nombre': f.nombre, 'apellido': f.apellido, 'email': f.email}
                for f in cursor.fetchall()
            ]
        except Exception as e:
            if conexion:
                conexion.rollback()
            flash(f'Error al crear playlist: {e}', 'error')
        finally:
            if conexion:
                conexion.close()
    return render_template('create_playlist.html', usuarios=usuarios)

@app.route('/edit_playlist/<int:playlist_id>', methods=('GET', 'POST'))
@admin_required
def edit_playlist(playlist_id):
    playlist = None
    usuarios = []
    todas_canciones = []
    canciones_asociadas = []
    
    if database_type == 'mongodb':
        try:
            play_dict = db_mongo.playlists.find_one({"playlistId": playlist_id})
            playlist = MongoRow(play_dict) if play_dict else None
            
            if request.method == 'POST':
                nombre = request.form['nombre']
                privacidad = request.form['privacidad']
                usuario_id = request.form['usuarioId']
                canciones_seleccionadas = request.form.getlist('canciones')
                
                # Obtener detalles de las canciones seleccionadas para desnormalizar
                selected_ids = [int(cid) for cid in canciones_seleccionadas]
                songs_list = []
                for album in db_mongo.albums.find():
                    for song in album.get('canciones', []):
                        if song['cancionId'] in selected_ids:
                            songs_list.append({
                                "cancionId": song['cancionId'],
                                "titulo": song['titulo'],
                                "duracion": song['duracion'],
                                "albumId": album['albumId'],
                                "albumTitulo": album['titulo'],
                                "artistaNombre": album['artistaNombre'],
                                "fechaAgregado": datetime.now()
                            })
                            
                u_doc = db_mongo.usuarios.find_one({"usuarioId": int(usuario_id)})
                creador_nombre = f"{u_doc['nombre']} {u_doc['apellido']}".strip() if u_doc else "Usuario"
                
                db_mongo.playlists.update_one(
                    {"playlistId": playlist_id},
                    {"$set": {
                        "nombre": nombre,
                        "privacidad": privacidad,
                        "usuarioId": int(usuario_id),
                        "usuarioNombre": creador_nombre,
                        "canciones": songs_list
                    }}
                )
                flash('¡Playlist actualizada exitosamente!', 'success')
                return redirect(url_for('playlists'))
                
            filas_u = list(db_mongo.usuarios.find())
            usuarios = [{'usuarioId': u['usuarioId'], 'nombre': u['nombre'], 'apellido': u['apellido'], 'email': u['email']} for u in filas_u]
            
            # Obtener todas las canciones disponibles
            for album in db_mongo.albums.find():
                for song in album.get('canciones', []):
                    if not song.get('eliminado'):
                        todas_canciones.append({
                            'cancionId': song['cancionId'],
                            'titulo': song['titulo'],
                            'duracion': song['duracion'],
                            'album': album['titulo']
                        })
                        
            if play_dict:
                canciones_asociadas = [c['cancionId'] for c in play_dict.get('canciones', [])]
        except Exception as e:
            flash(f'Error en MongoDB: {e}', 'error')
            return redirect(url_for('playlists'))
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            
            if request.method == 'POST':
                nombre = request.form['nombre']
                privacidad = request.form['privacidad']
                usuario_id = request.form['usuarioId']
                canciones_seleccionadas = request.form.getlist('canciones')
                
                cursor.execute("{CALL soundwave.SP_ActualizarPlaylist (?, ?, ?, ?)}", 
                               (playlist_id, nombre, privacidad, int(usuario_id)))
                
                cursor.execute("DELETE FROM soundwave.PlaylistCancion WHERE Playlist_playlistId = ?", (playlist_id,))
                if canciones_seleccionadas:
                    for can_id in canciones_seleccionadas:
                        cursor.execute("INSERT INTO soundwave.PlaylistCancion (Playlist_playlistId, Cancion_cancionId, fechaAgregado) VALUES (?, ?, GETDATE())", 
                                       (playlist_id, int(can_id)))
                conexion.commit()
                flash('¡Playlist actualizada exitosamente!', 'success')
                return redirect(url_for('playlists'))
                
            cursor.execute("SELECT playlistId, nombre, privacidad, Usuario_usuarioId FROM soundwave.Playlist WHERE playlistId = ?", (playlist_id,))
            fila = cursor.fetchone()
            if not fila:
                flash('Playlist no encontrada.', 'error')
                return redirect(url_for('playlists'))
                
            playlist = {
                'playlistId': fila.playlistId,
                'nombre': fila.nombre,
                'privacidad': fila.privacidad,
                'usuarioId': fila.Usuario_usuarioId
            }
            
            cursor.execute("SELECT usuarioId, nombre, apellido, email FROM soundwave.Usuario ORDER BY nombre")
            usuarios = [
                {'usuarioId': f.usuarioId, 'nombre': f.nombre, 'apellido': f.apellido, 'email': f.email}
                for f in cursor.fetchall()
            ]
            
            cursor.execute("""
                SELECT c.cancionId, c.titulo, c.duracion, al.titulo AS album
                FROM soundwave.Cancion c
                JOIN soundwave.Album al ON c.Album_albumId = al.albumId
                WHERE c.eliminado = 0 OR c.eliminado IS NULL
                ORDER BY c.titulo
            """)
            todas_canciones = [
                {'cancionId': f.cancionId, 'titulo': f.titulo, 'duracion': f.duracion, 'album': f.album}
                for f in cursor.fetchall()
            ]
            
            cursor.execute("SELECT Cancion_cancionId FROM soundwave.PlaylistCancion WHERE Playlist_playlistId = ?", (playlist_id,))
            canciones_asociadas = [f[0] for f in cursor.fetchall()]
        except Exception as e:
            flash(f'Error al editar playlist: {e}', 'error')
            return redirect(url_for('playlists'))
        finally:
            if conexion:
                conexion.close()
    return render_template(
        'edit_playlist.html', 
        playlist=playlist, 
        usuarios=usuarios, 
        todas_canciones=todas_canciones, 
        canciones_asociadas=canciones_asociadas
    )

@app.route('/delete_playlist/<int:playlist_id>', methods=('POST',))
@admin_required
def delete_playlist(playlist_id):
    if database_type == 'mongodb':
        try:
            db_mongo.playlists.update_one({"playlistId": playlist_id}, {"$set": {"eliminado": True}})
            flash('¡Playlist enviada a la papelera exitosamente!', 'success')
        except Exception as e:
            flash(f'Error en MongoDB: {e}', 'error')
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            cursor.execute("{CALL soundwave.SP_EliminarPlaylist (?)}", (playlist_id,))
            conexion.commit()
            flash('¡Playlist enviada a la papelera exitosamente!', 'success')
        except Exception as e:
            flash(f'Error al mover playlist a la papelera: {e}', 'error')
        finally:
            if conexion:
                conexion.close()
    return redirect(url_for('playlists'))

@app.route('/restore_playlist/<int:playlist_id>', methods=('POST',))
@admin_required
def restore_playlist(playlist_id):
    if database_type == 'mongodb':
        try:
            db_mongo.playlists.update_one({"playlistId": playlist_id}, {"$set": {"eliminado": False}})
            flash('¡Playlist restaurada exitosamente!', 'success')
        except Exception as e:
            flash(f'Error en MongoDB: {e}', 'error')
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            cursor.execute("{CALL soundwave.SP_RestaurarPlaylist (?)}", (playlist_id,))
            conexion.commit()
            flash('¡Playlist restaurada exitosamente!', 'success')
        except Exception as e:
            flash(f'Error al restaurar playlist: {e}', 'error')
        finally:
            if conexion:
                conexion.close()
    return redirect(url_for('papelera') + '#tab-playlists')

@app.route('/delete_permanent_playlist/<int:playlist_id>', methods=('POST',))
@admin_required
def delete_permanent_playlist(playlist_id):
    if database_type == 'mongodb':
        try:
            db_mongo.playlists.delete_one({"playlistId": playlist_id})
            flash('¡Playlist eliminada permanentemente del sistema!', 'success')
        except Exception as e:
            flash(f'Error en MongoDB: {e}', 'error')
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            cursor.execute("{CALL soundwave.SP_EliminarFisicoPlaylist (?)}", (playlist_id,))
            conexion.commit()
            flash('¡Playlist eliminada permanentemente del sistema!', 'success')
        except Exception as e:
            flash(f'Error al eliminar permanentemente la playlist: {e}', 'error')
        finally:
            if conexion:
                conexion.close()
    return redirect(url_for('papelera') + '#tab-playlists')

# --- RUTAS PÚBLICAS Y VISTAS DE DETALLES ---
@app.route('/artistas')
def artistas():
    artistas = []
    if database_type == 'mongodb':
        try:
            filas = list(db_mongo.artistas.find({"$or": [{"eliminado": False}, {"eliminado": {"$exists": False}}]}))
            for fila in filas:
                fecha_str = fila['fechaInicio'].strftime('%Y-%m-%d') if 'fechaInicio' in fila and fila['fechaInicio'] else 'N/A'
                artistas.append({
                    'artistaId': fila['artistaId'],
                    'nombreArtistico': fila['nombreArtistico'],
                    'pais': fila['pais'],
                    'fechaInicio': fecha_str,
                    'nombre': fila.get('discograficaNombre', 'Independiente'),
                    'discograficaId': fila.get('discograficaId')
                })
        except Exception as e:
            print(f"Error artistas MongoDB: {e}")
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            cursor.execute("{CALL soundwave.SP_ConsultarArtistas}")
            filas = cursor.fetchall()
            for fila in filas:
                fecha_str = fila.fechaInicio.strftime('%Y-%m-%d') if hasattr(fila.fechaInicio, 'strftime') else str(fila.fechaInicio) if fila.fechaInicio else 'N/A'
                artistas.append({
                    'artistaId': fila.artistaId,
                    'nombreArtistico': fila.nombreArtistico,
                    'pais': fila.pais,
                    'fechaInicio': fecha_str,
                    'nombre': fila.nombre,
                    'discograficaId': fila.discograficaId
                })
        except Exception as e:
            flash(f'Error al consultar artistas: {e}', 'error')
        finally:
            if conexion:
                conexion.close()
    return render_template('artistas.html', artistas=artistas)

@app.route('/canciones')
def canciones():
    canciones = []
    if database_type == 'mongodb':
        try:
            # Obtener todas las canciones de los álbumes
            pipeline = [
                {"$unwind": "$canciones"},
                {"$match": {"$or": [{"canciones.eliminado": False}, {"canciones.eliminado": {"$exists": False}}]}},
                {"$project": {
                    "cancionId": "$canciones.cancionId",
                    "titulo": "$canciones.titulo",
                    "duracion": "$canciones.duracion",
                    "explicita": "$canciones.explicita",
                    "album": "$titulo",
                    "albumId": "$albumId"
                }}
            ]
            filas = list(db_mongo.albums.aggregate(pipeline))
            for fila in filas:
                canciones.append({
                    'cancionId': fila['cancionId'],
                    'titulo': fila['titulo'],
                    'duracion': fila['duracion'],
                    'explicita': bool(fila['explicita']),
                    'album': fila['album'],
                    'albumId': fila['albumId']
                })
        except Exception as e:
            print(f"Error canciones MongoDB: {e}")
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            cursor.execute("{CALL soundwave.SP_ConsultarCanciones}")
            filas = cursor.fetchall()
            for fila in filas:
                canciones.append({
                    'cancionId': fila.cancionId,
                    'titulo': fila.titulo,
                    'duracion': fila.duracion,
                    'explicita': bool(fila.explicita),
                    'album': fila.album,
                    'albumId': fila.albumId
                })
        except Exception as e:
            flash(f'Error al consultar canciones: {e}', 'error')
        finally:
            if conexion:
                conexion.close()
    return render_template('canciones.html', canciones=canciones)

@app.route('/playlists')
def playlists():
    playlists = []
    if database_type == 'mongodb':
        try:
            filas = list(db_mongo.playlists.find({"$or": [{"eliminado": False}, {"eliminado": {"$exists": False}}]}))
            for f in filas:
                playlists.append((
                    f['playlistId'],
                    f['nombre'],
                    f['privacidad'],
                    f.get('usuarioNombre', 'Usuario'),
                    f['usuarioId']
                ))
        except Exception as e:
            print(f"Error playlists MongoDB: {e}")
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            cursor.execute("{CALL soundwave.SP_ConsultarPlaylists}")
            filas = cursor.fetchall()
            for fila in filas:
                playlists.append((
                    fila.playlistId,
                    fila.nombre,
                    fila.privacidad,
                    fila.creador,
                    fila.usuarioId
                ))
        except Exception as e:
            flash(f'Error al consultar playlists: {e}', 'error')
        finally:
            if conexion:
                conexion.close()
    return render_template('playlists.html', playlists=playlists)

@app.route('/usuarios')
@admin_required
def usuarios():
    usuarios = []
    if database_type == 'mongodb':
        try:
            filas = list(db_mongo.usuarios.find())
            for u in filas:
                # Filtrar eliminados según convención de la UI
                if u.get('eliminado'):
                    continue
                usuarios.append((
                    u['usuarioId'],
                    u['nombre'],
                    u['apellido'],
                    u['email'],
                    u.get('pais', 'Ecuador'),
                    u.get('estado', 'Activa')
                ))
        except Exception as e:
            print(f"Error usuarios MongoDB: {e}")
    else:
        conexion = get_db_connection()
        cursor = conexion.cursor()
        cursor.execute("SELECT usuarioId, nombre, apellido, email, pais, estado FROM soundwave.Usuario WHERE (eliminado = 0 OR eliminado IS NULL)")
        usuarios = cursor.fetchall()
        conexion.close()
    return render_template('usuarios.html', usuarios=usuarios)

@app.route('/usuarios/detalle/<int:usuario_id>')
@admin_required
def usuario_detalle(usuario_id):
    usuario = None
    pagos_list = []
    reproducciones_list = []
    total_reproducciones = 0
    
    if database_type == 'mongodb':
        try:
            u_doc = db_mongo.usuarios.find_one({"usuarioId": usuario_id})
            if not u_doc:
                flash('Usuario no encontrado.', 'error')
                return redirect(url_for('usuarios'))
                
            # Buscar plan activo
            plan_nombre = 'Ninguno'
            precio_plan = 0.0
            fecha_suscripcion_str = 'N/A'
            for s in u_doc.get('suscripciones', []):
                if s.get('estado') == 'Activa':
                    plan_nombre = s.get('plan', {}).get('nombre', 'Gratis')
                    precio_plan = s.get('plan', {}).get('precioMensual', 0.0)
                    if s.get('fechaInicio'):
                        fecha_suscripcion_str = s['fechaInicio'].strftime('%d %b %Y')
                    break
                    
            usuario = {
                'usuarioId': u_doc['usuarioId'],
                'nombre': u_doc['nombre'],
                'apellido': u_doc['apellido'],
                'email': u_doc['email'],
                'pais': u_doc.get('pais', 'Ecuador'),
                'estado': u_doc.get('estado', 'Activa'),
                'fechaSuscripcion': fecha_suscripcion_str,
                'planNombre': plan_nombre,
                'precioPlan': precio_plan
            }
            
            # Historial de pagos desde el documento embebido
            for s in u_doc.get('suscripciones', []):
                for p in s.get('pagos', []):
                    fecha_str = p['fechaPago'].strftime('%d/%m/%Y %H:%M') if 'fechaPago' in p and p['fechaPago'] else 'N/A'
                    pagos_list.append({
                        'pagoId': p['pagoId'],
                        'monto': p['monto'],
                        'fechaPago': fecha_str,
                        'metodoPago': p['metodoPago'],
                        'estado': p['estado']
                    })
            # Ordenar pagos por fecha desc
            pagos_list.sort(key=lambda x: x['pagoId'], reverse=True)
            
            # Historial de reproducciones desde reproducciones
            reps = list(db_mongo.reproducciones.find({"usuarioId": usuario_id}).sort("fechaHora", -1).limit(10))
            for r in reps:
                fecha_str = r['fechaHora'].strftime('%d/%m/%Y %H:%M') if 'fechaHora' in r and r['fechaHora'] else 'N/A'
                reproducciones_list.append({
                    'reproduccionId': r.get('reproduccionId', 1),
                    'fechaHora': fecha_str,
                    'dispositivo': r.get('dispositivo', 'Web'),
                    'cancion': r['cancionTitulo'],
                    'artista': r['artistaNombre']
                })
                
            total_reproducciones = db_mongo.reproducciones.count_documents({"usuarioId": usuario_id})
        except Exception as e:
            flash(f"Error en MongoDB: {e}", "error")
            return redirect(url_for('usuarios'))
    else:
        conexion = get_db_connection()
        cursor = conexion.cursor()
        
        cursor.execute("""
            SELECT 
                u.usuarioId, u.nombre, u.apellido, u.email, u.pais, u.estado, 
                s.fechaInicio AS fechaSuscripcion, ps.nombre AS planNombre, ps.precioMensual
            FROM soundwave.Usuario u
            LEFT JOIN soundwave.Suscripcion s ON u.usuarioId = s.Usuario_usuarioId AND s.estado = 'Activa'
            LEFT JOIN soundwave.PlanSuscripcion ps ON s.Plan_planId = ps.planId
            WHERE u.usuarioId = ?
        """, (usuario_id,))
        usuario_fila = cursor.fetchone()
        if not usuario_fila:
            conexion.close()
            flash('Usuario no encontrado.', 'error')
            return redirect(url_for('usuarios'))
            
        fecha_suscripcion_str = 'N/A'
        if usuario_fila.fechaSuscripcion:
            fecha_suscripcion_str = usuario_fila.fechaSuscripcion.strftime('%d %b %Y') if hasattr(usuario_fila.fechaSuscripcion, 'strftime') else str(usuario_fila.fechaSuscripcion)
            
        usuario = {
            'usuarioId': usuario_fila.usuarioId,
            'nombre': usuario_fila.nombre,
            'apellido': usuario_fila.apellido,
            'email': usuario_fila.email,
            'pais': usuario_fila.pais,
            'estado': usuario_fila.estado,
            'fechaSuscripcion': fecha_suscripcion_str,
            'planNombre': usuario_fila.planNombre or 'Ninguno',
            'precioPlan': usuario_fila.precioMensual or 0.00
        }
        
        cursor.execute("""
            SELECT p.pagoId, p.monto, p.fechaPago, p.metodoPago, p.estado
            FROM soundwave.Pago p
            JOIN soundwave.Suscripcion s ON p.Suscripcion_suscripcionId = s.suscripcionId
            WHERE s.Usuario_usuarioId = ?
            ORDER BY p.fechaPago DESC
        """, (usuario_id,))
        pagos = cursor.fetchall()
        for p in pagos:
            fecha_str = p.fechaPago.strftime('%d/%m/%Y %H:%M') if hasattr(p.fechaPago, 'strftime') else str(p.fechaPago)
            pagos_list.append({
                'pagoId': p.pagoId,
                'monto': p.monto,
                'fechaPago': fecha_str,
                'metodoPago': p.metodoPago,
                'estado': p.estado
            })
            
        cursor.execute("""
            SELECT TOP 10
                r.reproduccionId, r.fechaHora, r.dispositivo,
                c.titulo AS cancion, a.nombreArtistico AS artista
            FROM soundwave.Reproduccion r
            JOIN soundwave.Cancion c ON r.Cancion_cancionId = c.cancionId
            JOIN soundwave.Album al ON c.Album_albumId = al.albumId
            JOIN soundwave.Artista a ON al.Artista_artistaId = a.artistaId
            WHERE r.Usuario_usuarioId = ?
            ORDER BY r.fechaHora DESC
        """, (usuario_id,))
        reproducciones = cursor.fetchall()
        for r in reproducciones:
            fecha_str = r.fechaHora.strftime('%d/%m/%Y %H:%M') if hasattr(r.fechaHora, 'strftime') else str(r.fechaHora)
            reproducciones_list.append({
                'reproduccionId': r.reproduccionId,
                'fechaHora': fecha_str,
                'dispositivo': r.dispositivo,
                'cancion': r.cancion,
                'artista': r.artista
            })
            
        cursor.execute("SELECT COUNT(*) FROM soundwave.Reproduccion WHERE Usuario_usuarioId = ?", (usuario_id,))
        total_reproducciones = cursor.fetchone()[0]
        conexion.close()
        
    return render_template(
        'usuario_detalle.html',
        usuario=usuario,
        pagos=pagos_list,
        reproducciones=reproducciones_list,
        total_reproducciones=total_reproducciones
    )

@app.route('/usuarios/delete/<int:usuario_id>', methods=['POST'])
@admin_required
def delete_usuario(usuario_id):
    if database_type == 'mongodb':
        try:
            db_mongo.usuarios.update_one({"usuarioId": usuario_id}, {"$set": {"eliminado": True}})
            flash('¡Usuario enviado a la papelera exitosamente!', 'success')
        except Exception as e:
            flash(f'Error en MongoDB: {e}', 'error')
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            cursor.execute("UPDATE soundwave.Usuario SET eliminado = 1 WHERE usuarioId = ?", (usuario_id,))
            conexion.commit()
            flash('¡Usuario enviado a la papelera exitosamente!', 'success')
        except Exception as e:
            flash(f'Error al mover usuario a la papelera: {e}', 'error')
        finally:
            if conexion:
                conexion.close()
    return redirect(url_for('usuarios'))

@app.route('/usuarios/restore/<int:usuario_id>', methods=['POST'])
@admin_required
def restore_usuario(usuario_id):
    if database_type == 'mongodb':
        try:
            db_mongo.usuarios.update_one({"usuarioId": usuario_id}, {"$set": {"eliminado": False}})
            flash('¡Usuario restaurado exitosamente!', 'success')
        except Exception as e:
            flash(f'Error en MongoDB: {e}', 'error')
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            cursor.execute("UPDATE soundwave.Usuario SET eliminado = 0 WHERE usuarioId = ?", (usuario_id,))
            conexion.commit()
            flash('¡Usuario restaurado exitosamente!', 'success')
        except Exception as e:
            flash(f'Error al restaurar usuario: {e}', 'error')
        finally:
            if conexion:
                conexion.close()
    return redirect(url_for('papelera') + '#tab-usuarios')

@app.route('/usuarios/delete_permanent/<int:usuario_id>', methods=['POST'])
@admin_required
def delete_permanent_usuario(usuario_id):
    if database_type == 'mongodb':
        try:
            db_mongo.playlists.delete_many({"usuarioId": usuario_id})
            db_mongo.reproducciones.delete_many({"usuarioId": usuario_id})
            db_mongo.usuarios.delete_one({"usuarioId": usuario_id})
            flash('¡Usuario eliminado permanentemente del sistema!', 'success')
        except Exception as e:
            flash(f'Error en MongoDB: {e}', 'error')
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            cursor.execute("DELETE FROM soundwave.Pago WHERE Suscripcion_suscripcionId IN (SELECT suscripcionId FROM soundwave.Suscripcion WHERE Usuario_usuarioId = ?)", (usuario_id,))
            cursor.execute("DELETE FROM soundwave.Suscripcion WHERE Usuario_usuarioId = ?", (usuario_id,))
            cursor.execute("DELETE FROM soundwave.PlaylistCancion WHERE Playlist_playlistId IN (SELECT playlistId FROM soundwave.Playlist WHERE Usuario_usuarioId = ?)", (usuario_id,))
            cursor.execute("DELETE FROM soundwave.Playlist WHERE Usuario_usuarioId = ?", (usuario_id,))
            cursor.execute("DELETE FROM soundwave.Reproduccion WHERE Usuario_usuarioId = ?", (usuario_id,))
            cursor.execute("DELETE FROM soundwave.Usuario WHERE usuarioId = ?", (usuario_id,))
            conexion.commit()
            flash('¡Usuario eliminado permanentemente del sistema!', 'success')
        except Exception as e:
            flash(f'Error al eliminar permanentemente al usuario: {e}', 'error')
        finally:
            if conexion:
                conexion.close()
    return redirect(url_for('papelera') + '#tab-usuarios')

# --- ENDPOINTS AJAX DE DETALLES ---
@app.route('/api/artista/<int:artista_id>')
def api_artista(artista_id):
    try:
        if database_type == 'mongodb':
            art_doc = db_mongo.artistas.find_one({"artistaId": artista_id})
            if not art_doc:
                return jsonify({'error': 'Artista no encontrado'}), 404
                
            # Géneros
            gen_names = []
            for album in db_mongo.albums.find({"artistaId": artista_id}):
                for song in album.get('canciones', []):
                    for g in song.get('generos', []):
                        if g not in gen_names:
                            gen_names.append(g)
            generos_str = ", ".join(gen_names) if gen_names else "General"
            
            import hashlib
            h = int(hashlib.md5(art_doc['nombreArtistico'].encode('utf-8')).hexdigest(), 16)
            oyentes = f"{(h % 900 / 10) + 1:.1f}M"
            
            fecha_str = art_doc['fechaInicio'].strftime('%Y-%m-%d') if 'fechaInicio' in art_doc and art_doc['fechaInicio'] else 'N/A'
            artista_data = {
                'nombre': art_doc['nombreArtistico'],
                'pais': art_doc['pais'],
                'fechaInicio': fecha_str,
                'genero': generos_str,
                'oyentes': oyentes
            }
            
            # Álbumes
            albumes_filas = list(db_mongo.albums.find({"artistaId": artista_id}))
            albumes_list = [{
                'id': al['albumId'],
                'titulo': al['titulo'],
                'fechaLanzamiento': al['fechaLanzamiento'].strftime('%Y-%m-%d') if 'fechaLanzamiento' in al and al['fechaLanzamiento'] else 'N/A'
            } for al in albumes_filas]
            
            # Canciones
            canciones_list = []
            for al in albumes_filas:
                for c in al.get('canciones', []):
                    if not c.get('eliminado'):
                        canciones_list.append({
                            'id': c['cancionId'],
                            'titulo': c['titulo'],
                            'duracion': c['duracion'],
                            'album': al['titulo']
                        })
            return jsonify({
                'artista': artista_data,
                'albumes': albumes_list,
                'canciones': canciones_list
            })
        else:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            cursor.execute("SELECT nombreArtistico, pais, fechaInicio FROM soundwave.Artista WHERE artistaId = ?", (artista_id,))
            artista = cursor.fetchone()
            if not artista:
                conexion.close()
                return jsonify({'error': 'Artista no encontrado'}), 404
                
            cursor.execute("""
                SELECT DISTINCT g.nombre 
                FROM soundwave.Genero g
                JOIN soundwave.CancionGenero cg ON g.generoId = cg.Genero_generoId
                JOIN soundwave.Cancion c ON cg.Cancion_cancionId = c.cancionId
                JOIN soundwave.Album al ON c.Album_albumId = al.albumId
                WHERE al.Artista_artistaId = ?
            """, (artista_id,))
            generos_filas = cursor.fetchall()
            generos_list = [g.nombre for g in generos_filas]
            generos_str = ", ".join(generos_list) if generos_list else "General"
            
            import hashlib
            h = int(hashlib.md5(artista.nombreArtistico.encode('utf-8')).hexdigest(), 16)
            oyentes = f"{(h % 900 / 10) + 1:.1f}M"
            
            fecha_str = artista.fechaInicio.strftime('%Y-%m-%d') if hasattr(artista.fechaInicio, 'strftime') else str(artista.fechaInicio) if artista.fechaInicio else 'N/A'
            artista_data = {
                'nombre': artista.nombreArtistico,
                'pais': artista.pais,
                'fechaInicio': fecha_str,
                'genero': generos_str,
                'oyentes': oyentes
            }
            
            cursor.execute("SELECT albumId, titulo, fechaLanzamiento FROM soundwave.Album WHERE Artista_artistaId = ?", (artista_id,))
            albumes = cursor.fetchall()
            albumes_list = []
            for al in albumes:
                fecha_l = al.fechaLanzamiento.strftime('%Y-%m-%d') if hasattr(al.fechaLanzamiento, 'strftime') else str(al.fechaLanzamiento) if al.fechaLanzamiento else 'N/A'
                albumes_list.append({
                    'id': al.albumId,
                    'titulo': al.titulo,
                    'fechaLanzamiento': fecha_l
                })
                
            cursor.execute("""
                SELECT c.cancionId, c.titulo, c.duracion, al.titulo AS album
                FROM soundwave.Cancion c
                JOIN soundwave.Album al ON c.Album_albumId = al.albumId
                WHERE al.Artista_artistaId = ?
            """, (artista_id,))
            canciones = cursor.fetchall()
            canciones_list = [{
                'id': c.cancionId,
                'titulo': c.titulo,
                'duracion': c.duracion,
                'album': c.album
            } for c in canciones]
            
            conexion.close()
            return jsonify({
                'artista': artista_data,
                'albumes': albumes_list,
                'canciones': canciones_list
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/album/<int:album_id>')
def api_album(album_id):
    try:
        if database_type == 'mongodb':
            al_doc = db_mongo.albums.find_one({"albumId": album_id})
            if not al_doc:
                return jsonify({'error': 'Álbum no encontrado'}), 404
                
            fecha_l = al_doc['fechaLanzamiento'].strftime('%Y-%m-%d') if 'fechaLanzamiento' in al_doc and al_doc['fechaLanzamiento'] else 'N/A'
            album_data = {
                'titulo': al_doc['titulo'],
                'fechaLanzamiento': fecha_l,
                'artista': al_doc.get('artistaNombre', 'Artista')
            }
            canciones_list = [{
                'id': c['cancionId'],
                'titulo': c['titulo'],
                'duracion': c['duracion']
            } for c in al_doc.get('canciones', []) if not c.get('eliminado')]
            
            return jsonify({
                'album': album_data,
                'canciones': canciones_list
            })
        else:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            cursor.execute("""
                SELECT al.titulo, al.fechaLanzamiento, ar.nombreArtistico 
                FROM soundwave.Album al
                JOIN soundwave.Artista ar ON al.Artista_artistaId = ar.artistaId
                WHERE al.albumId = ?
            """, (album_id,))
            album = cursor.fetchone()
            if not album:
                conexion.close()
                return jsonify({'error': 'Álbum no encontrado'}), 404
                
            fecha_l = album.fechaLanzamiento.strftime('%Y-%m-%d') if hasattr(album.fechaLanzamiento, 'strftime') else str(album.fechaLanzamiento) if album.fechaLanzamiento else 'N/A'
            album_data = {
                'titulo': album.titulo,
                'fechaLanzamiento': fecha_l,
                'artista': album.nombreArtistico
            }
            
            cursor.execute("SELECT cancionId, titulo, duracion FROM soundwave.Cancion WHERE Album_albumId = ?", (album_id,))
            canciones = cursor.fetchall()
            canciones_list = [{
                'id': c.cancionId,
                'titulo': c.titulo,
                'duracion': c.duracion
            } for c in canciones]
            
            conexion.close()
            return jsonify({
                'album': album_data,
                'canciones': canciones_list
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/playlist/<int:playlist_id>')
def api_playlist(playlist_id):
    try:
        if database_type == 'mongodb':
            play_doc = db_mongo.playlists.find_one({"playlistId": playlist_id})
            if not play_doc:
                return jsonify({'error': 'Playlist no encontrada'}), 404
                
            playlist_data = {
                'nombre': play_doc['nombre'],
                'privacidad': play_doc['privacidad'],
                'creador': play_doc.get('usuarioNombre', 'Usuario')
            }
            canciones_list = [{
                'titulo': c['titulo'],
                'artista': c['artistaNombre'],
                'duracion': c['duracion'],
                'album': c.get('albumTitulo', 'Álbum')
            } for c in play_doc.get('canciones', [])]
            return jsonify({
                'playlist': playlist_data,
                'canciones': canciones_list
            })
        else:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            cursor.execute("""
                SELECT p.nombre, p.privacidad, u.nombre + ' ' + u.apellido AS creador
                FROM soundwave.Playlist p
                JOIN soundwave.Usuario u ON p.Usuario_usuarioId = u.usuarioId
                WHERE p.playlistId = ?
            """, (playlist_id,))
            playlist = cursor.fetchone()
            if not playlist:
                conexion.close()
                return jsonify({'error': 'Playlist no encontrada'}), 404
                
            playlist_data = {
                'nombre': playlist.nombre,
                'privacidad': playlist.privacidad,
                'creador': playlist.creador
            }
            
            cursor.execute("{CALL soundwave.SP_ContenidoPlaylist (?)}", (playlist_id,))
            canciones = cursor.fetchall()
            canciones_list = [{
                'titulo': c.Cancion,
                'artista': c.Artista,
                'duracion': c.DuracionSegundos,
                'album': c.Album
            } for c in canciones]
            
            conexion.close()
            return jsonify({
                'playlist': playlist_data,
                'canciones': canciones_list
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reproducir', methods=['POST'])
def api_reproducir():
    datos = request.get_json(silent=True) or request.form
    titulo = datos.get('titulo')
    album = datos.get('album')
    artista = datos.get('artista')
    dispositivo = datos.get('dispositivo', 'Web')
    
    usuario_id = datos.get('usuarioId')
    try:
        usuario_id = int(usuario_id) if usuario_id else None
    except ValueError:
        usuario_id = None
        
    if not usuario_id:
        usuario_id = 1
        
    if not titulo:
        return jsonify({'success': False, 'message': 'Falta título de la canción.'}), 400
        
    if database_type == 'mongodb':
        try:
            # Buscar la canción en los álbumes
            cancion_doc = None
            duracion = 180
            artista_nombre = artista or "Artista"
            
            # Intentar búsqueda exacta
            query = {"canciones.titulo": titulo}
            if artista:
                query["artistaNombre"] = artista
            elif album:
                query["titulo"] = album
                
            alb = db_mongo.albums.find_one(query)
            if not alb and (artista or album):
                # Fallback sin filtros extra
                alb = db_mongo.albums.find_one({"canciones.titulo": titulo})
                
            if alb:
                for c in alb.get('canciones', []):
                    if c['titulo'] == titulo:
                        cancion_doc = c
                        duracion = c['duracion']
                        artista_nombre = alb['artistaNombre']
                        break
                        
            if not cancion_doc:
                return jsonify({'success': False, 'message': 'Canción no encontrada en la base de datos.'}), 404
                
            # Generar id de reproducción autoincremental
            max_r = db_mongo.reproducciones.find_one(sort=[("reproduccionId", -1)])
            reproduccion_id = (max_r["reproduccionId"] + 1) if max_r else 1
            
            db_mongo.reproducciones.insert_one({
                "reproduccionId": reproduccion_id,
                "fechaHora": datetime.now(),
                "duracionEscuchada": duracion,
                "dispositivo": dispositivo,
                "usuarioId": usuario_id,
                "cancionId": cancion_doc['cancionId'],
                "cancionTitulo": titulo,
                "artistaNombre": artista_nombre
            })
            return jsonify({'success': True, 'message': 'Reproducción registrada exitosamente.', 'cancionId': cancion_doc['cancionId']})
        except Exception as e:
            print(f"Error al reproducir MongoDB: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    else:
        conexion = None
        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            
            cancion_id = None
            duracion = 180
            
            if artista:
                cursor.execute("""
                    SELECT c.cancionId, c.duracion 
                    FROM soundwave.Cancion c
                    JOIN soundwave.Album al ON c.Album_albumId = al.albumId
                    JOIN soundwave.Artista ar ON al.Artista_artistaId = ar.artistaId
                    WHERE c.titulo = ? AND ar.nombreArtistico = ?
                """, (titulo, artista))
                row = cursor.fetchone()
                if row:
                    cancion_id, duracion = row[0], row[1]
                    
            if not cancion_id and album:
                cursor.execute("""
                    SELECT c.cancionId, c.duracion 
                    FROM soundwave.Cancion c
                    JOIN soundwave.Album al ON c.Album_albumId = al.albumId
                    WHERE c.titulo = ? AND al.titulo = ?
                """, (titulo, album))
                row = cursor.fetchone()
                if row:
                    cancion_id, duracion = row[0], row[1]
                    
            if not cancion_id:
                cursor.execute("SELECT cancionId, duracion FROM soundwave.Cancion WHERE titulo = ?", (titulo,))
                row = cursor.fetchone()
                if row:
                    cancion_id, duracion = row[0], row[1]
                    
            if not cancion_id:
                conexion.close()
                return jsonify({'success': False, 'message': 'Canción no encontrada en la base de datos.'}), 404
                
            cursor.execute("""
                INSERT INTO soundwave.Reproduccion (fechaHora, duracionEscuchada, dispositivo, Cancion_cancionId, Usuario_usuarioId)
                VALUES (GETDATE(), ?, ?, ?, ?)
            """, (duracion, dispositivo, cancion_id, usuario_id))
            
            conexion.commit()
            conexion.close()
            return jsonify({'success': True, 'message': 'Reproducción registrada exitosamente.', 'cancionId': cancion_id})
        except Exception as e:
            if conexion:
                conexion.close()
            print(f"Error al registrar reproducción: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500

# --- MÓDULO DE REPORTES DINÁMICOS ---
@app.route('/reportes', methods=['GET', 'POST'])
@admin_required
def reportes():
    todos_artistas = []
    todas_playlists = []
    top_canciones = []
    ingresos = None
    stats_artista = None
    contenido_playlist = None
    
    fecha_inicio = request.form.get('fecha_inicio', '2024-01-01')
    fecha_fin = request.form.get('fecha_fin', '2024-12-31')
    artista_seleccionado = request.form.get('artista_id')
    playlist_seleccionada = request.form.get('playlist_id')
    
    if database_type == 'mongodb':
        try:
            # Artistas para dropdown
            filas_art = list(db_mongo.artistas.find().sort("nombreArtistico", 1))
            todos_artistas = [MongoRow(a) for a in filas_art]
            
            # Playlists para dropdown
            filas_play = list(db_mongo.playlists.find().sort("nombre", 1))
            todas_playlists = [MongoRow(p) for p in filas_play]
            
            # Reporte 1: Top Canciones
            # Mapear reproducciones en el mes actual
            now = datetime.now()
            start_of_month = datetime(now.year, now.month, 1)
            # Para asegurar que hay datos en desarrollo si la fecha actual es 2026 y los mocks son viejos:
            # Filtramos sin fecha para desarrollo o con la fecha real del sistema. Haremos filtro de mes actual:
            pipeline_top = [
                {"$match": {
                    "fechaHora": {
                        "$gte": datetime(now.year, now.month, 1),
                        "$lte": datetime(now.year, now.month, 28)  # Ajuste simple de rango
                    }
                }},
                {"$group": {
                    "_id": {"cancion": "$cancionTitulo", "artista": "$artistaNombre"},
                    "TotalReproducciones": {"$sum": 1}
                }},
                {"$project": {
                    "Cancion": "$_id.cancion",
                    "Artista": "$_id.artista",
                    "TotalReproducciones": 1,
                    "_id": 0
                }},
                {"$sort": {"TotalReproducciones": -1}},
                {"$limit": 50}
            ]
            
            # Fallback en caso de que no haya reproducciones en el mes actual: traer históricos
            reps_count = db_mongo.reproducciones.count_documents({"fechaHora": {"$gte": start_of_month}})
            if reps_count == 0:
                pipeline_top.pop(0) # Quitar filtro de fecha para demo
                
            top_canciones = [MongoRow(r) for r in db_mongo.reproducciones.aggregate(pipeline_top)]
            
            # Reporte 2: Ingresos Premium dinámicos
            date_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            date_fin = datetime.strptime(fecha_fin, '%Y-%m-%d')
            
            pipeline_ing = [
                {"$unwind": "$suscripciones"},
                {"$match": {"suscripciones.plan.nombre": "Premium"}},
                {"$unwind": "$suscripciones.pagos"},
                {"$match": {
                    "suscripciones.pagos.estado": "Aprobado",
                    "suscripciones.pagos.fechaPago": {"$gte": date_inicio, "$lte": date_fin}
                }},
                {"$group": {
                    "_id": None,
                    "TotalRecaudadoPremium": {"$sum": "$suscripciones.pagos.monto"},
                    "CantidadTransacciones": {"$sum": 1}
                }}
            ]
            res_ing = list(db_mongo.usuarios.aggregate(pipeline_ing))
            ingresos = MongoRow(res_ing[0]) if res_ing else MongoRow({"TotalRecaudadoPremium": 0, "CantidadTransacciones": 0})
            
            # Reporte 3: Estadísticas de Artista
            if artista_seleccionado:
                art_id = int(artista_seleccionado)
                # Sumar reproducciones de las canciones de este artista
                pipeline_stats = [
                    {"$match": {"artistaId": art_id}},
                    {"$unwind": "$canciones"},
                    {"$lookup": {
                        "from": "reproducciones",
                        "localField": "canciones.cancionId",
                        "foreignField": "cancionId",
                        "as": "plays"
                    }},
                    {"$project": {
                        "artistaNombre": 1,
                        "play_count": {"$size": "$plays"}
                    }},
                    {"$group": {
                        "_id": "$artistaNombre",
                        "ReproduccionesGlobalesTotales": {"$sum": "$play_count"}
                    }}
                ]
                res_stats = list(db_mongo.albums.aggregate(pipeline_stats))
                if res_stats:
                    stats_artista = MongoRow({
                        "Artista": res_stats[0]["_id"],
                        "ReproduccionesGlobalesTotales": res_stats[0]["ReproduccionesGlobalesTotales"]
                    })
                else:
                    # Traer nombre del artista aunque tenga 0 reproducciones
                    art_doc = db_mongo.artistas.find_one({"artistaId": art_id})
                    stats_artista = MongoRow({
                        "Artista": art_doc["nombreArtistico"] if art_doc else "Artista",
                        "ReproduccionesGlobalesTotales": 0
                    })
                    
            # Reporte 4: Contenido de Playlist
            if playlist_seleccionada:
                play_id = int(playlist_seleccionada)
                playlist_doc = db_mongo.playlists.find_one({"playlistId": play_id})
                if playlist_doc:
                    # Mapear de manera idéntica al SP
                    contenido_playlist = []
                    for c in playlist_doc.get('canciones', []):
                        contenido_playlist.append(MongoRow({
                            "NombrePlaylist": playlist_doc['nombre'],
                            "Cancion": c['titulo'],
                            "Artista": c['artistaNombre'],
                            "DuracionSegundos": c['duracion'],
                            "Album": c.get('albumTitulo', 'Álbum')
                        }))
        except Exception as e:
            print(f"Error reportes MongoDB: {e}")
    else:
        conexion = get_db_connection()
        cursor = conexion.cursor()
        
        cursor.execute("SELECT artistaId, nombreArtistico FROM soundwave.Artista ORDER BY nombreArtistico")
        todos_artistas = cursor.fetchall()
        
        cursor.execute("SELECT playlistId, nombre FROM soundwave.Playlist ORDER BY nombre")
        todas_playlists = cursor.fetchall()
        
        cursor.execute("{CALL soundwave.SP_ReporteTopCanciones}")
        top_canciones = cursor.fetchall()
        
        try:
            cursor.execute("{CALL soundwave.SP_ReporteIngresosPremium (?, ?)}", (fecha_inicio, fecha_fin))
            ingresos = cursor.fetchone()
        except Exception as e:
            ingresos = None
            print(f"Error en SP_ReporteIngresosPremium: {e}")
            
        if artista_seleccionado:
            try:
                cursor.execute("{CALL soundwave.SP_EstadisticasArtista (?)}", (int(artista_seleccionado),))
                stats_artista = cursor.fetchone()
            except Exception as e:
                print(f"Error en SP_EstadisticasArtista: {e}")
                
        if playlist_seleccionada:
            try:
                cursor.execute("{CALL soundwave.SP_ContenidoPlaylist (?)}", (int(playlist_seleccionada),))
                contenido_playlist = cursor.fetchall()
            except Exception as e:
                print(f"Error en SP_ContenidoPlaylist: {e}")
                
        conexion.close()
        
    return render_template(
        'reportes.html', 
        top_canciones=top_canciones, 
        ingresos=ingresos, 
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        todos_artistas=todos_artistas,
        todas_playlists=todas_playlists,
        artista_seleccionado=int(artista_seleccionado) if artista_seleccionado else None,
        stats_artista=stats_artista,
        playlist_seleccionada=int(playlist_seleccionada) if playlist_seleccionada else None,
        contenido_playlist=contenido_playlist
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)
