# Agricolix · Gestión agrícola de Doña Laura SpA

Plataforma web para registrar trabajadores y cosechas, importar planillas,
consultar productividad y preparar pagos semanales. Proyecto de título Capstone
APT de Ingeniería en Informática, sede Viña del Mar.

## Uso diario en Windows

Con las dependencias y PostgreSQL configurados:

1. Abre **Iniciar Agricolix.cmd** en la raíz del proyecto.
2. El iniciador comprueba la conexión, prepara las migraciones e inicia ambos
   servidores en segundo plano. Abre <http://127.0.0.1:5173>.
3. El primer administrador se genera una sola vez. Sus datos iniciales están en
   `.local/primer-acceso.txt`, excluido de Git. Cambia la contraseña en **Mi cuenta**.
4. Para detener los servidores usa **Detener Agricolix.cmd**.

Ejecuta los iniciadores con el mismo usuario de Windows. Los registros de
diagnóstico están en `.local/`. Si un puerto está ocupado, revisa esos registros;
el iniciador no detiene procesos ajenos. La aplicación sigue siendo local:
el cierre de Windows detiene los servicios, y el iniciador no instala un servicio
de inicio automático.

## Funcionalidades

- Panel general con volumen, productividad, personal activo, semanas por cerrar,
  evolución por fecha y distribución por sector. El período corresponde a los
  siete días terminados en el registro de producción más reciente, no a datos simulados.
- Registro de trabajadores, jornadas, sectores, labores y producción.
- Importación de Excel con vista previa, validación y guardado transaccional.
- Tarifas por semana, cálculo en pesos con redondeo decimal y cierre de pagos.
- Reportes de producción y pagos, CSV e impresión a PDF.
- Análisis de producción con K-Means, Isolation Forest y Random Forest.
- Asistente conversacional de OpenAI con consultas de solo lectura a los datos.
- Usuarios, sesiones, perfiles de acceso y registro de operaciones exitosas.

### Perfiles

| Perfil | Permisos |
| --- | --- |
| Administrador | Usuarios, tarifas, cierres, operación y consulta |
| Encargado | Trabajadores, configuración operativa, cosechas, importación y consulta |
| Solo consulta | Indicadores, reportes, análisis y asistente; sin escritura operativa |

El backend verifica los permisos en cada petición. Las contraseñas se derivan
con PBKDF2 y sal aleatoria; las sesiones duran ocho horas, se guardan como hashes
y se entregan mediante una cookie HttpOnly. Los intentos de acceso fallidos se
limitan por usuario y origen. Al cambiar permisos se invalidan las sesiones
del usuario afectado. El cambio de contraseña conserva únicamente la sesión actual.

### Semanas cerradas

Una semana cerrada no admite producción nueva, importaciones ni cambios de tarifa.
Las tres operaciones comparten un bloqueo transaccional con el cierre para
evitar que se confirmen cifras distintas al trabajar simultáneamente. Si un lote
incluye una semana cerrada, se rechaza completo. Los datos operativos anteriores
no se corrigen automáticamente.

### Clientes y faenas por kilo

En **Clientes y faenas**, el administrador registra la empresa cliente y crea
una faena con nombre, predio, cultivo, período y precio de cobro en CLP por kilo.
El precio al cliente es independiente de la tarifa semanal del trabajador.
Las faenas pueden estar Planificadas, Activas o Finalizadas. Todos los perfiles
pueden consultar; solo el administrador modifica clientes y acuerdos.

Al registrar una jornada de cosecha se puede elegir una faena activa. Se valida
que el cliente esté activo y que la fecha esté dentro del período acordado. Las
cosechas anteriores y la importación de Excel conservan su comportamiento y
quedan sin faena vinculada: no se asignan clientes a registros históricos de forma
automática. La vinculación nueva se hace en `POST /produccion/jornada`.

Una faena con producción conserva cliente, identificación, inicio y precio.
Para un precio o acuerdo nuevo se crea otra faena. Puede actualizarse su estado,
notas y fecha final, sin dejar fuera cosechas existentes. El control de versión
rechaza ediciones desactualizadas y los bloqueos coordinan cambios de precio con
el guardado concurrente de cosechas. Un cliente solo se desactiva cuando todas
sus faenas estén finalizadas. Los cambios quedan en auditoría.

El resumen por faena incluye kilos, horas, personas, jornadas y cobro estimado
(kilos por precio del cliente, redondeado a pesos). Incorpora ajustes separados
de cosechas cerradas. También muestra el pago bruto estimado por producción,
usando la tarifa del cierre cuando existe y la semanal en períodos abiertos.
Si falta alguna tarifa, ese importe se muestra pendiente, sin sustituirlo por
cero. Puede diferir del cierre por redondeos y no incluye transporte, insumos,
cotizaciones ni otros costos. No representa margen o utilidad.

Estos importes son estimaciones de gestión: no emiten facturas, no agregan
impuestos, no registran cobros de clientes ni confirman ingresos recibidos.
La tabla de detalle muestra hasta 200 registros recientes; su resumen incluye
toda la producción vinculada. Los reportes originales de producción y pagos
mantienen su alcance y no filtran por cliente o faena.

### Registro de cosechas

En **Cosechas**, elige una fecha, un sector y una labor; luego agrega los
trabajadores, kilos y horas. El lote es transaccional: un error rechaza todas las
filas. Si la fecha no tiene una jornada, se crea dentro de la misma transacción.
Las claves de envío evitan duplicaciones ante reintentos, y los registros
existentes se revisan antes de insertar. No se permite superar 24 horas acumuladas
por trabajador en una jornada desde el registro por lote o una corrección.

**Registros e historial** permite filtrar los últimos 200 registros. En semanas
abiertas se corrigen kilos y horas con motivo obligatorio y control de versión:
si otra persona modificó el registro, se debe actualizar antes de guardar. El
historial conserva los valores anteriores, los nuevos, el responsable y la fecha.

Una semana cerrada admite únicamente un **ajuste separado por administrador**.
Los originales y el cierre se conservan. Los ajustes se consultan en el historial
y se incorporan al saldo en **Seguimiento de pagos**, usando el precio congelado
del cierre. Los reportes originales de producción y cierre no se reescriben.

### Seguimiento de pagos

Cerrar una semana calcula su obligación; no significa que se haya pagado. En
**Seguimiento de pagos** el administrador aprueba el monto y registra abonos con
fecha y referencia de comprobante. Se distingue Calculado, Aprobado, Pago parcial
y Pagado, con saldo pendiente. No se ejecutan transferencias bancarias.

Los abonos son idempotentes y no pueden superar el saldo, incluso si dos personas
los registran al mismo tiempo. Un ajuste obliga a revisar y aprobar de nuevo el
pago. No se permite reducir el total por debajo de lo ya abonado. Esta versión
no incluye anulaciones de abonos ni conciliación bancaria: revisa la referencia,
fecha y monto antes de registrar un pago informado.

### Respaldos y recuperación

El backend comprueba al iniciar y cada hora si existe una copia íntegra del día
(hora de Santiago). Si falta, crea una en `.local/backups/` usando `pg_dump` y un
snapshot coherente de PostgreSQL. No hay copias automáticas mientras el equipo o
el backend están apagados. Se requiere tener `pg_dump` y `pg_restore` instalados.

**Respaldar Agricolix.cmd** crea una copia adicional manual. Cada `.dump` tiene un
manifiesto `.json` con checksum SHA-256 y conteos de todas las tablas. Conserva ambos
archivos juntos. Las copias incluyen datos y hashes de acceso: son privadas,
están fuera de Git y deben guardarse también en un destino externo protegido;
estas herramientas solo crean la copia local y no la suben a ningún servicio.

Desde `backend`, para probar una restauración real sin cambiar la operación:

```powershell
.venv\Scripts\python.exe respaldo.py --verificar "RUTA_ABSOLUTA_DE_LA_COPIA.dump"
```

La verificación restaura en una base temporal, compara integridad y conteos y la
elimina. Para recuperar en una base nueva y conservarla:

```powershell
.venv\Scripts\python.exe respaldo.py --restaurar "RUTA_ABSOLUTA_DE_LA_COPIA.dump" --destino agricolix_recuperada_revision
```

El destino debe ser nuevo y tener ese prefijo. Tras revisar la base recuperada,
el administrador puede configurar `DB_NAME` y reiniciar. Nunca se sobrescribe la
base operativa. Los errores de la tarea automática quedan en `.local/backend-error.log`.

### Fuentes del análisis

La fuente por defecto es la producción de **PostgreSQL**, agrupada por trabajador
y fecha para las labores cuyo nombre comienza con `Cosecha`. Los registros nuevos
aparecen al actualizar el análisis. No se mezclan automáticamente con el CSV de ejemplo.

En **Análisis de datos** puedes seleccionar por separado el **Histórico de ejemplo**.
Se conserva el archivo anonimizado del repositorio o el CSV indicado por `DATASET_PATH`.
El asistente usa por defecto la producción operativa. Las fuentes se identifican
en las respuestas y en la pantalla de análisis.

El modelo se evalúa con un corte temporal global 80/20 y se compara con la media
de las tres jornadas previas. La pantalla muestra el error de ambas alternativas.
Cuando no hay suficientes secuencias, no se genera una predicción. Los kilos por
jornada deben interpretarse junto con horas, sector, cultivo y condiciones de trabajo;
las estimaciones no sustituyen el criterio humano.

## Instalación desde cero

Se necesita Python 3.12, Node.js con npm compatible con el Vite del proyecto y PostgreSQL.

### Base de datos

Desde `FASE 2/DonaLaura/backend`:

```powershell
psql -U postgres -c "CREATE DATABASE dona_laura_db"
psql -U postgres -d dona_laura_db -f esquema.sql
```

Si la base ya existe, no la recrees. `esquema.sql` crea las tablas operativas;
las migraciones adicionales del directorio `migrations/` se aplican una sola vez
al iniciar, con registro de versiones.

### Backend

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements_ia.txt
Copy-Item .env.example .env
```

Completa la conexión a PostgreSQL en `.env`. Para el asistente configura
`OPENAI_API_KEY` con una clave válida de tu cuenta de OpenAI. Las consultas a ese
servicio utilizan la API de esa cuenta. La clave no debe subirse a Git. El análisis
estadístico local no requiere clave de OpenAI.

### Frontend

Desde `FASE 2/DonaLaura/frontend`:

```powershell
npm install
```

Luego usa **Iniciar Agricolix.cmd**. Para desarrollo manual:

```powershell
# Terminal 1, dentro de backend
.venv\Scripts\python.exe crear_admin.py
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000

# Terminal 2, dentro de frontend
npm run dev
```

El frontend usa `/api`, con proxy local hacia el backend. No hace falta editar
cada pantalla para cambiar la conexión. `VITE_API_URL` permite configurarla para
otro entorno; deben ajustarse también CORS, los orígenes permitidos y HTTPS.
`COOKIE_SECURE=true` es necesario al servir sesiones por HTTPS en un despliegue.

## Verificación

Desde `backend`:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.venv\Scripts\python.exe -m pytest

# Incluye PostgreSQL real; necesita permisos para crear una base temporal.
$env:RUN_POSTGRES_TESTS = "1"
.venv\Scripts\python.exe -m pytest
```

Las pruebas de integración crean una base con prefijo `agricolix_test_` y un
identificador aleatorio, y la eliminan al terminar. No truncan la base operativa.
Comprueban cierres concurrentes, cosecha durante un cierre, importaciones repetidas,
rechazo atómico de lotes, autenticación, permisos, auditoría, límite de intentos,
migraciones e incorporación de cosechas al análisis.

Desde `frontend`, `npm run build` comprueba la compilación y `npm run lint` revisa
el código. `/health` comprueba la disponibilidad del backend y de PostgreSQL.

## Estructura

```text
FASE 1/                         Documentación y evidencias iniciales
FASE 2/
  Documentacion/                Informes del proyecto
  Evidencias Individuales/      Evidencias del equipo
  DonaLaura/
    backend/
      main.py                   API de operación e importación
      pagos.py                  Tarifas y cierres
      operacion.py              Jornadas por lote, correcciones y ajustes
      seguimiento.py            Aprobaciones, abonos y saldos
      respaldo.py               Copias y recuperación comprobable
      seguridad.py              Sesiones, usuarios y permisos
      resumen.py                Indicadores del panel general
      reportes.py               Reportes y exportación
      crear_admin.py            Primer acceso local
      migrations/               Cambios versionados de esquema
      ia/                       Modelos, herramientas y asistente
      tests/                    Pruebas unitarias e integración
    frontend/src/               Aplicación React
scripts/                        Inicio y detención en Windows
.local/                         Acceso inicial y logs locales, fuera de Git
```

## Alcance de esta versión

Esta versión incorpora acceso y pruebas de los procesos principales, pero el
iniciador utiliza servidores de desarrollo locales. Antes de un despliegue externo
se deben preparar hosting, HTTPS, destino externo y retención de respaldos y políticas
de operación. No incluye recuperación de contraseña por correo ni integración
bancaria; el módulo calcula y registra pagos, sin transferir dinero.

## Equipo

Sebastián Valenzuela · Alex Núñez · Alexander Vivanco · Diego Álvarez.
Profesor guía: Cristian Molina Pedernera.

## Demostración de dos años

Para explorar la aplicación con una empresa ficticia ya operando, abre `Usar demostracion.cmd`. Para volver a la base original, abre `Volver a datos reales.cmd`. Los accesos conservan ambas bases y reinician la aplicación. La franja amarilla identifica el entorno de demostración.

Consulta [DEMOSTRACION.md](DEMOSTRACION.md) para conocer los datos, las cuentas de prueba, las preguntas sugeridas al asistente y los resguardos. Los respaldos diarios distinguen la base original de la copia mediante su manifiesto.

## Simulador de contratos

En **Finanzas → Simulador de contratos** (`#simulador`), evalúa una oferta por kilo antes de comprometer una faena. Usa supuestos editables, independientes del historial: kilos, precio al cliente, tarifa variable de trabajadores, días, transporte y supervisión diarios, otros costos, reserva y margen objetivo sobre ventas.

Muestra ingresos, costos y margen; compara volúmenes conservador, esperado y mayor cosecha; permite variar el volumen entre 50% y 150% manteniendo días y costos fijos. Calcula precio y kilos de equilibrio y precio para alcanzar el objetivo. “Probar este precio” solo cambia el supuesto del simulador. Los importes son netos en CLP y el resultado no incorpora automáticamente costos omitidos ni impuestos. No es una predicción de IA, no modifica contratos o pagos y no se guarda al recargar. Pruebas de fórmulas y casos límite: `npm test` en el frontend.

## Mi día y repetición de jornadas

La entrada `#inicio` muestra **Mi día**: producción del día en horario de Chile, faenas activas vigentes, inicios previstos en los próximos siete días, saldo de pagos cerrados (incluidos ajustes y abonos) y semanas anteriores con producción sin cierre. La semana actual se excluye de este pendiente. El acceso de cierres abre la primera semana pendiente. La vista general anterior permanece en `#resumen`. Una faena sin registros hoy es una invitación a revisar, no una ausencia laboral ni un atraso comprobado.

En **Cosechas → Repetir jornada anterior**, la búsqueda usa la última fecha anterior con producción, sin confundir jornadas vacías con jornadas trabajadas. También se puede elegir una fecha histórica. Cada grupo conserva sector, labor y faena; se excluyen trabajadores inactivos y quienes ya tienen un registro coincidente en el destino. El usuario elige explícitamente reemplazar su borrador. Los kilos y horas quedan vacíos y no se guarda nada hasta completar y enviar el formulario. Si el acuerdo anterior no está vigente, se exige elegir otra faena. Una semana de destino cerrada no permite cargar el equipo. El servidor vuelve a validar trabajadores, fechas y duplicados al guardar.

## Cobros a clientes

En **Finanzas → Cobros a clientes** (`#cobros`), el administrador confirma una cuenta por faena con producción: monto acordado en CLP enteros, fecha, vencimiento y concepto. La pantalla propone el estimado por kilos (incluidos ajustes) y requiere revisión explícita. Se conserva una referencia al confirmar; las correcciones posteriores de producción no cambian el monto acordado. Hay una sola cuenta vigente por faena, incluso si está pagada: no se crean automáticamente cobros por producción posterior.

Los abonos representan dinero que el usuario declara recibido, con fecha y referencia. Se impiden fechas futuras o anteriores al acuerdo, referencias duplicadas y sobrepagos, también en envíos simultáneos. Las claves de envío evitan duplicados al reintentar. Un cobro sin abonos puede anularse con motivo, conservando historial; no hay eliminación ni edición de montos confirmados. Los perfiles de consulta y encargado pueden leer, pero solo el administrador registra movimientos.

Mi día muestra saldo, cobros vencidos y vencimientos del día. El asistente consulta cartera actual por cliente, separada del período de producción y de los pagos a trabajadores. El mensaje de cobranza se prepara para copiar y revisar: la aplicación no envía WhatsApp. No se emiten facturas tributarias, no se verifican bancos y no se realizan transferencias.

La demostración incluye 18 cuentas ficticias con distintos saldos y abonos. `backend/demo_cobros.py` solo puede ampliar la base de demostración registrada y verificada; rechaza la base original. La migración `004_cobros_clientes.sql` se aplica automáticamente al iniciar cada entorno, sin trasladar datos entre bases.

## Preparar la semana y resumen PDF

En **Preparar la semana** (`#semana`) se selecciona una semana de lunes a domingo; por defecto se abre la última completa. La guía consulta producción y ajustes, posibles duplicados, horas vacías o acumuladas sobre 24, registros sin faena, tarifa y estado de cierre. Las alertas son controles de revisión, no una verificación de asistencia ni una garantía de ausencia de errores. Cada día permite abrir su historial de cosechas sin reemplazar el borrador de registro.

La guía y `GET /preparar-semana` son de solo lectura. El cierre exige ir al detalle de Pagos y confirmarlo allí; aprobar y registrar abonos siguen siendo operaciones separadas. Descargar `GET /preparar-semana/pdf` tampoco cierra ni paga nada y está disponible para todos los perfiles autenticados.

El PDF A4 de una página contiene producción de la semana (original más ajustes), pagos estimados o cierres congelados con ajustes, abonos de clientes y trabajadores según la fecha anotada del movimiento, hasta cuatro faenas y saldos actuales de clientes. Estos saldos actuales no reconstruyen la deuda al final del período elegido; tampoco se restan movimientos de períodos diferentes para calcular una utilidad. Se recalcula al descargar, no se almacena como cierre contable. Requiere `reportlab` incluido en `backend/requirements.txt`. Los PDF locales de ejemplo se excluyen de Git.
