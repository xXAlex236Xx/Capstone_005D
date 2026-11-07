# Demostración de dos años

La aplicación tiene una base de demostración independiente de los datos originales. Todo el historial simulado es ficticio, incluidos clientes, personas, producción y pagos. No representa cobros ni transferencias reales.

## Qué incluye

Periodo: 6 de noviembre de 2024 al 5 de noviembre de 2026.

| Información | Cantidad inicial |
| --- | ---: |
| Trabajadores | 36, con 30 activos |
| Clientes ficticios | 8 |
| Faenas históricas, activas y planificadas | 77 |
| Jornadas con producción | 498 |
| Registros de cosecha | 14.470 |
| Tarifas semanales | 105 |
| Pagos semanales cerrados | 3.303 |
| Abonos simulados | 3.930 |

El módulo de cobros a clientes añade 18 acuerdos ficticios y sus abonos de ejemplo, con cuentas pagadas, parciales, vencidas y por vencer. Están separados de los pagos a trabajadores. Sus cifras representan una cartera demostrativa, no dinero real.

Incluye cambios estacionales, variaciones de rendimiento, registros atípicos, correcciones y ajustes, pagos completos, parciales y pendientes. Las últimas dos semanas quedan abiertas para practicar el cierre. El cobro a clientes se estima por kilo y no acredita dinero recibido ni utilidad.

## Abrir y volver a los datos originales

- Abre `Usar demostracion.cmd` para iniciar esta copia. La aplicación muestra una franja amarilla **ENTORNO DE DEMOSTRACIÓN**.
- Abre `Volver a datos reales.cmd` para regresar a la base original. Ambos accesos reinician la aplicación y conservan ambas bases.
- No mezcles exportaciones de demostración con documentos reales. Los nombres de personas y clientes ficticios incluyen `[DEMO]`.

Sí, después se puede eliminar la copia de demostración. Volver al entorno original no necesita borrar nada. Los accesos anteriores no ejecutan eliminaciones; una limpieza posterior debe verificar el identificador de la copia antes de retirarla.

## Usuarios para probar permisos

Se crean seis cuentas de prueba: `demo.admin` (administrador), `demo.campo`, `demo.supervisor` y `demo.operaciones` (encargados), `demo.gerencia` y `demo.reportes` (consulta). Las contraseñas iniciales están en `.local/accesos-demostracion.txt`, excluido de Git. Solo funcionan en la copia. También se conserva el acceso del administrador existente.

## Preguntas para el asistente

- ¿Qué clientes concentran más kilos y cuál es su cobro estimado?
- ¿Cuánto queda pendiente de pago a trabajadores?
- Compara la producción mensual de 2025 con 2026 e indica los meses incompletos.
- ¿Qué trabajadores vienen a la baja y qué revisarías antes de concluir algo?
- ¿Hay registros extraños que convenga revisar?
- ¿Qué tan confiable es el modelo de IA con estos datos simulados?

Los análisis de rendimiento pueden tardar porque entrenan el modelo con el historial. Los resultados sobre datos sintéticos sirven para demostrar funcionalidades; no validan precisión en una empresa real.

## Resguardos técnicos

`backend/demo.py --crear` crea una base nueva y verifica que los conteos originales no cambien. El manifiesto `.local/demostracion.json` guarda los nombres de ambas bases y el identificador único de demostración. `--activar` valida el prefijo y el marcador interno antes de cambiar únicamente `DB_NAME` en el `.env`; `--original` permite regresar sin depender de que la copia siga disponible. No se publican credenciales mediante `/entorno`.

Los respaldos guardan el nombre de su base en el manifiesto: una copia de demostración no cuenta como el respaldo diario de la base original. La restauración se hace en una base nueva, sin sobrescribir la operación.
