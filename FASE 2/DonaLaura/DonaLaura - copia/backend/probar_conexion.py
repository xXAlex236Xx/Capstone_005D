
from database import conectar_bd

try:
    with conectar_bd() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT current_database();")
            resultado = cursor.fetchone()

            print("¡Conexión exitosa!")
            print("Base de datos:", resultado[0])

            cursor.execute("SELECT * FROM trabajadores LIMIT 1;")
            print("¡La tabla trabajadores existe!")

except Exception as error:
    print("ERROR DETECTADO:")
    print(type(error).__name__)
    print(error)