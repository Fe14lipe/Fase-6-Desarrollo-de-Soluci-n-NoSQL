import sys
import os
import json
import pyodbc

# Asegurar que importamos app desde el directorio de trabajo
sys.path.append(os.getcwd())
from app import get_db_connection

def main():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # SQL query to check if the column exists and add it if not
        sql = """
        IF NOT EXISTS (
            SELECT * 
            FROM sys.columns 
            WHERE object_id = OBJECT_ID('soundwave.Usuario') 
              AND name = 'eliminado'
        )
        BEGIN
            PRINT 'Adding column eliminado to soundwave.Usuario...';
            ALTER TABLE soundwave.Usuario ADD eliminado BIT NOT NULL DEFAULT 0;
        END
        ELSE
        BEGIN
            PRINT 'Column eliminado already exists in soundwave.Usuario.';
        END
        """
        
        print("Running database column migration for Usuario...")
        cursor.execute(sql)
        conn.commit()
        print("Migration successfully completed!")
        
        # Verify columns in Usuario
        cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'Usuario' AND TABLE_SCHEMA = 'soundwave'")
        columns = [row[0] for row in cursor.fetchall()]
        print(f"Current columns in soundwave.Usuario: {columns}")
        
        conn.close()
    except Exception as e:
        print(f"Error during migration: {e}")

if __name__ == '__main__':
    main()
