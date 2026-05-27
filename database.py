import sqlite3

DB_NAME = "mantenimiento.db"


def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT UNIQUE NOT NULL,
        nombre TEXT NOT NULL,
        area TEXT NOT NULL,
        tipo_equipo TEXT NOT NULL,
        estado TEXT NOT NULL,
        fecha_registro TEXT NOT NULL,
        hora_inicio_operacion TEXT NOT NULL,
        hora_fin_operacion TEXT NOT NULL,
        dias_operacion TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ordenes_trabajo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        activo_id INTEGER,
        codigo_equipo TEXT,
        nombre_equipo TEXT,
        tipo_mantenimiento TEXT NOT NULL,
        fecha_inicio TEXT NOT NULL,
        fecha_fin TEXT NOT NULL,
        descripcion TEXT,
        personal TEXT,
        tiempo_intervencion REAL DEFAULT 0,
        costo_mano_obra REAL DEFAULT 0,
        otros_costos REAL DEFAULT 0,
        moneda TEXT DEFAULT 'CRC',
        es_falla INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS paros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        activo_id INTEGER,
        codigo_equipo TEXT,
        nombre_equipo TEXT,
        fecha_inicio TEXT NOT NULL,
        fecha_fin TEXT NOT NULL,
        tiempo_paro REAL DEFAULT 0,
        tipo_paro TEXT DEFAULT 'No programado',
        causa TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS repuestos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        orden_id INTEGER NOT NULL,
        codigo TEXT NOT NULL,
        descripcion TEXT NOT NULL,
        cantidad_utilizada INTEGER NOT NULL,
        costo_unitario REAL NOT NULL,
        costo_total REAL NOT NULL,
        moneda TEXT DEFAULT 'CRC',
        FOREIGN KEY(orden_id) REFERENCES ordenes_trabajo(id)
    )
    """)

    conn.commit()
    conn.close()
