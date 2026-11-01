# Operación local y recuperación

## Comandos no destructivos

```powershell
# Desde la raíz; en PowerShell, habilitar los módulos compartidos.
$env:PYTHONPATH = "src/shared"
python -m andina_etl --raw data/original --db .local/operacion.duckdb --bronze .local/bronze
python -m andina_etl --raw data/original --db .local/operacion.duckdb --bronze .local/bronze --reconciliar
python scripts/reconciliar_fuentes.py --raw data/original --db .local/operacion.duckdb
python scripts/previsualizar_reporte.py --db .local/operacion.duckdb --dia 2026-09-30
python scripts/respaldo_local.py respaldar .local/operacion.duckdb .local/backup_01.duckdb
python scripts/respaldo_local.py restaurar .local/backup_01.duckdb .local/restaurada_01.duckdb
```

El reporte es una vista previa local. No existe transporte de correo habilitado. Los respaldos pueden contener datos personales: se quedan en `.local/`, excluido de Git y del ZIP.

## Compuertas de publicación

La conciliación básica compara por día, canal y categoría los pedidos, bruto, descuento y neto calculados desde Silver con Gold. Un desbalance aborta y revierte la corrida. `publicacion_actual` se actualiza solo dentro del commit correcto.

Para probar políticas adicionales, crear un archivo local y pasarlo con `--politica .local/politica.json`. Este ejemplo es **de pruebas**, no un umbral aprobado:

```json
{
  "min_pedidos": 1,
  "max_fraccion_cuarentena": 0.5,
  "venta_esperada": 14177333600,
  "tolerancia": 0,
  "fecha_minima_datos": "2026-09-30"
}
```

La fracción se mide en el lote reevaluado de cada tabla, incluyendo los inválidos que ya estaban en cuarentena; no solo sobre las incidencias nuevas. Fechas y total esperado son referencias del caso, no configuraciones de producción reutilizables.

## Si falla la corrida

1. Consultar `etl_run_log` y el mensaje del proceso. No publicar ni reenviar una cifra no validada.
2. Identificar error de esquema, datos, conciliación o entorno. Los mensajes de contrato no imprimen registros personales.
3. Corregir la fuente/configuración y reejecutar. Silver, incidencias, watermark, Gold, estrella y marcador de publicación se confirman juntos en DuckDB.
4. Si Gold fue alterado externamente, usar `--recalcular-gold`; una corrida sin cambios no disimula la corrupción.
5. Si el fallo ocurrió en una función nueva del modelo estrella, la transacción revierte también Silver y Gold.
6. Bronze está fuera de la transacción del motor: puede conservar archivos de un intento fallido. No interpretar su existencia como publicación exitosa.

## Lock y concurrencia

`<base>.lock` se crea de forma exclusiva antes de abrir el escritor e incluye PID y hora UTC. Se retira al terminar incluso con una excepción normal. Un cierre forzado puede dejarlo abandonado: verificar que no exista un escritor vivo y revisar la base antes de retirar **ese archivo exacto**. No hay caducidad automática, para evitar habilitar dos escritores.

El lock coordina las herramientas de este proyecto en la misma máquina. No cubre clientes externos que lo ignoren ni un entorno distribuido. No ejecutar dos cargas que compartan una carpeta Bronze pero usen bases distintas como si tuvieran un lock común.

## Respaldos y restauración

El respaldo requiere base cerrada, sin WAL pendiente y sin otro escritor de la aplicación. Se copia a un destino nuevo y se abre para verificar lectura y total. La restauración también usa destino nuevo; no reemplaza silenciosamente la base activa. Comparar tablas/fechas y el reporte en la copia antes de una sustitución operativa.

Este ensayo demuestra restauración local del caso. No demuestra RPO/RTO, retención o recuperación cloud. En Delta se necesita validar fallo entre tablas, reejecución y publicación por versión en la plataforma.

## CI y ambientes

`scripts/ci_local.py` valida sintaxis, notebook determinista, SQL generado, archivos empaquetables y pruebas/carga sintética. El job Spark usa Python 3.11 y Java 17 con una base sintética temporal; una omisión hace fallar ese job. No accede a datos reales ni secretos.

El workflow está en `.github/workflows/validacion.yml`; no implementa despliegue a producción ni protección de ramas. Para despliegue remoto se requieren entornos, permisos y aprobación del alcance.

Acciones oficiales consultadas para la configuración: [checkout](https://github.com/actions/checkout), [setup-python](https://github.com/actions/setup-python). Las referencias del workflow están fijadas a commits para evitar cambios implícitos de las etiquetas.
