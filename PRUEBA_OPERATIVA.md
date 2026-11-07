# Prueba de uso con el encargado

Esta guía está preparada para la validación humana; no sustituye observar al
encargado usando el sistema. Realizar los pasos en una **copia recuperada de la
base**, con datos de prueba, para conservar la operación original.

El administrador prepara la copia siguiendo README → Respaldos y recuperación,
configura DB_NAME para esa copia y crea una cuenta de encargado. Confirmar que
los respaldos y la operación real estén preservados antes de iniciar.

| Tarea | Resultado esperado |
| --- | --- |
| Registrar una jornada para dos trabajadores | Comparte fecha, sector y labor; guarda ambas filas y muestra confirmación |
| Repetir un trabajador dentro del lote | Rechaza todo el lote y explica el problema |
| Reintentar una jornada ya ingresada | Evita duplicar los registros existentes |
| Buscar la jornada en Registros e historial | Muestra personas, cantidades y estado de la semana |
| Corregir kilos indicando un motivo | Guarda la corrección y conserva el antes y el después |
| Abrir el historial | Permite identificar quién cambió el dato, cuándo y por qué |
| Preparar y cerrar una semana como administrador | Conserva el detalle y bloquea nuevas cosechas para esa semana |
| Intentar corregir una semana cerrada | Ofrece ajuste separado al administrador; no cambia el original |
| Aprobar y registrar un abono de prueba | Exige referencia y fecha, muestra saldo parcial y detalle |
| Completar el saldo de prueba | Muestra Pagado y evita abonos superiores al saldo |
| Registrar un ajuste positivo de kilos | Cambia el saldo y exige una aprobación nueva |
| Verificar una copia de seguridad | Restaura en una base temporal y comprueba integridad y conteos |

Durante la prueba, pedir al encargado que piense en voz alta. Registrar:

- Qué tarea no pudo completar sin ayuda y en qué paso.
- Qué nombres, cantidades o estados le resultaron confusos.
- Cuántos pasos necesitó para ingresar una jornada habitual.
- Qué información esperaba encontrar y no vio.
- Si pudo corregir un error y explicar qué quedó en el historial.

No registrar pagos reales ni modificar la base original durante esta validación.
Al terminar, el administrador revisa los resultados y vuelve a la configuración
operativa antes de permitir el ingreso de información real.
# Clientes y faenas por kilo

Validación adicional pendiente con el encargado, en una copia de prueba:

1. Registrar un cliente y una faena con precio de cobro por kilo diferente de
   la tarifa semanal de los trabajadores.
2. Comprobar que una faena Planificada no recibe cosechas. Activarla y guardar
   una jornada dentro de su período, seleccionando la faena.
3. Comparar kilos por precio del cliente con el cobro estimado. Comparar por
   separado el pago bruto estimado con la tarifa del trabajador.
4. Revisar el detalle por faena y su identificación en el historial de cosechas.
5. Intentar cambiar el precio después de registrar producción: debe rechazarse.
   Crear otra faena cuando corresponda un nuevo acuerdo.
6. Finalizar la faena y comprobar que no recibe producción nueva. Confirmar que
   no puede desactivarse un cliente mientras tenga faenas sin finalizar.
7. Revisar el caso de tarifas semanales faltantes: el pago estimado debe quedar
   pendiente, no mostrarse como cero.
8. Acordar que estos importes son estimaciones, sin emisión de facturas,
   impuestos, cobros recibidos ni costos completos de operación.
