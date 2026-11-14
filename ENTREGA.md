# Agricolix para Doña Laura

La entrega usa una base PostgreSQL nueva. El primer arranque crea las tablas y la cuenta `admin`. El administrador puede configurar sectores y labores y luego registrar los trabajadores, clientes y faenas de la empresa. El análisis usa las cosechas registradas en esta base.

## Publicar en Render

1. Sube esta versión al repositorio de GitHub. En el panel de Render, crea un Blueprint del repositorio y elige la rama que contiene `render.yaml`.
2. Revisa el plan del servicio web y de PostgreSQL antes de aplicar el Blueprint. El servicio entregará la interfaz y la API bajo una misma dirección HTTPS. La configuración crea una base nueva con acceso desde la red privada del proveedor.
3. Completa `AGRICOLIX_CLAVE_INICIAL` en Render con una clave aleatoria de al menos 16 caracteres. El primer arranque la usa para crear `admin`. Después de comprobar el acceso, cambia esa clave desde **Mi cuenta** y retira `AGRICOLIX_CLAVE_INICIAL` del entorno de Render. En cada reinicio se conservan los usuarios registrados.
4. Para habilitar el asistente conversacional agrega `OPENAI_API_KEY` en las variables privadas del servicio. Los informes y el análisis estadístico consumen los registros disponibles en PostgreSQL. La empresa debe acordar qué datos operativos se pueden procesar mediante el asistente antes de habilitarlo con datos reales.
5. Verifica la restauración y retención de respaldos de PostgreSQL en el plan contratado. En este despliegue los respaldos los gestiona el proveedor de la base.
6. Verifica el acceso desde el computador y el teléfono. Comparte con el dueño el enlace HTTPS y entrégale su credencial por un canal privado.

[Configurar un Blueprint en Render](https://render.com/docs/infrastructure-as-code) · [Precios de los planes](https://render.com/pricing) · [Respaldos y recuperación de PostgreSQL](https://render.com/docs/postgresql-backups)

## Instalar en el dispositivo

- **Windows.** Abre el enlace en Edge y usa el menú **Aplicaciones → Instalar este sitio como una aplicación**.
- **Android.** Abre el enlace en Chrome y elige **Agregar a la pantalla principal → Instalar** si aparece esa opción.
- **iPhone.** Abre el enlace en Safari, toca **Compartir → Agregar a Inicio** y selecciona **Abrir como app web** si está disponible.

La aplicación instalada se conecta al mismo servidor desde ambos dispositivos. Necesita conexión para consultar y guardar registros.
