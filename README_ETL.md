# ETL Andina Market · estado actualizado

Leer junto con [estado de implementación](docs/ESTADO_IMPLEMENTACION.md), [contratos](docs/CONTRATOS_Y_DECISIONES.md) y [operación](docs/OPERACION_Y_RECUPERACION.md).

## Flujo local

CSV → validación estructural → Bronze Parquet → Silver → Gold diario → conciliación → modelo estrella → publicación.

- Clientes, pedidos y pagos son obligatorios; tickets_soporte es opcional.
- Bronze conserva todas las columnas como texto, hash SHA-256, archivo, run_id y fecha. Silver lee Bronze, no el CSV directamente.
- El mismo contenido reutiliza su snapshot. Archivos con cabecera duplicada/incompleta, codificación o ancho inválido fallan antes de transformar.
- Pedidos/clientes se leen completos; solo se escriben filas nuevas o con hash distinto.
- Pagos se filtran por watermark menos tres días después de leer el snapshot. No es CDC de extracción. Los pendientes por pedido se releen fuera de ventana.
- `--reconciliar` omite el filtro incremental de pagos. No elimina ausencias de origen.
- Un registro cargado que pasa a inválido se retira; Gold recalcula los días anteriores y nuevos afectados.
- Clientes que llegan después se reflejan en la bandera del pedido sin esperar que cambie el pedido.
- La cuarentena conserva historia; `calidad_incidencias` muestra abierta/resuelta solo después de reevaluar el ID.

## Modelo y transacción

`gold_venta_neta_diaria` mantiene el grano día/canal/categoría. `gold.dim_fecha`, `dim_canal`, `dim_categoria` y `dim_cliente` sirven a `fact_pedido`, `fact_pago`, `fact_ticket` y `fact_venta_neta_diaria`.

Las claves de dimensión existentes son estables. Los hechos se reconstruyen dentro de la transacción: es una estrategia local para este volumen, no una optimización de carga masiva. El calendario cubre años completos; DAX debe limitar fechas comparables.

La transacción DuckDB confirma Silver, cuarentena, incidencias, watermark, Gold, estrella y `publicacion_actual` juntos. El lock excluye escritores de esta aplicación para la misma base. Bronze persiste fuera de esa transacción: una caída puede dejar un archivo sin manifiesto confirmado, por lo que el siguiente intento puede reescribir el mismo destino de contenido.

## Calidad y publicación

La definición es ENTREGADO, bruto menos descuento, fecha_pedido. Los importes aceptados son pesos enteros exactos, sin truncar fracciones; la política de centavos sigue pendiente. No hay catálogo de categorías aprobado.

La compuerta compara todas las filas agregadas de Silver con Gold, no solo el total. Umbrales opcionales controlan fracción de rechazos en lote, mínimo de pedidos, total esperado/tolerancia y fecha mínima. Sin política adicional se aplica conciliación básica, no un SLA implícito.

Soporte conserva cierre anterior a creación o cerrado sin fecha con flags; su duración no participa como valor negativo. `ticket_clasificacion` prepara asociación por ticket, hash de texto y versión; no se ejecuta una API en la carga y `fact_ticket.tipo_caso` sigue sin clasificar automáticamente.

## Verificación y comandos

```bash
python scripts/verificar_entrega.py --raw data/original --caso
python scripts/ci_local.py
python scripts/ci_spark.py
```

El tercer comando requiere PySpark y Java; usa una base sintética y falla si las pruebas se omiten. En Windows las restricciones de Spark se explican en `tests/conftest.py`. No instalar Spark es una omisión declarada de la suite local, no un éxito de paridad.

Referencia del caso: 6.040 clientes, 19.270 pedidos, 20.124 pagos, 7.925 filas de Gold y COP 14.177.333.600. La carga opcional de soporte agrega 2.125 tickets sin cambiar la venta.

## Estado Spark/Delta

Las reglas de clientes/pedidos/pagos y el SQL tienen versiones Spark. El notebook se genera de forma determinista con `python src/shared/spark/build_notebook.py`. Las nuevas funciones de soporte, estrella, incidencias operativas, lock y compuertas de este bloque se implementaron en el flujo local: **no se declara paridad integral del notebook**.

La ejecución de reglas/SQL en Spark es distinta de ejecutar MERGE/DELETE/recuperación en Fabric o Databricks. Esa última validación sigue pendiente. El hashing del notebook lee el archivo completo mediante binaryFile y requiere rediseño para archivos grandes.

## Límites que permanecen

- Ausencias no se interpretan como bajas sin contrato de fuente.
- Fuera del modo de reconciliación, correcciones antiguas de pagos pueden quedar fuera de ventana.
- El pipeline materializa snapshots y consulta claves existentes en memoria; falta medir capacidad real de la máquina.
- Duplicados lógicos conservan el registro existente; no se cambia ganador arbitrariamente al recibir un ID menor.
- La cuarentena no incluye asignación a responsables humanos ni cierre firmado.
- El lock no coordina otros programas que escriban directamente ni varios nodos.
- Los umbrales, retención, permisos, RPO/RTO y alertas productivas requieren acuerdos y validación.
- El modelo estrella local no certifica DAX, SQL Server o compatibilidad completa del DDL con Fabric Warehouse.
