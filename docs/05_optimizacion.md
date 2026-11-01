# Parte 1, punto 5: optimización de la consulta de 50 millones de pedidos

Archivos: `sqlserver/optimizacion/02_optimizacion.sql` (consulta reescrita, índices, particiones), `sqlserver/optimizacion/experimento_optimizacion.py` (medición) y `sqlserver/optimizacion/ablacion_cast.py` (qué parte causa la lentitud).

## Problemas identificados, de mayor a menor peso
1. **`CAST(... AS VARCHAR(20))` en ambos lados del cruce con `tickets_soporte`.** Ambas columnas `id_cliente` ya son texto de 9 caracteres. El CAST impide buscar por índice, así que el motor recorre los tickets para cada cliente.
2. **Subconsulta correlacionada para `venta_mes`.** Se ejecuta una vez por cliente en lugar de agregar una sola vez.
3. **`YEAR()` y `MONTH()` sobre `fecha_pedido`.** El predicado no es SARGable: no se puede usar un índice por fecha. Se reemplaza por un rango `>= primer día del mes AND < primer día del mes siguiente`.
4. **`IN (SELECT DISTINCT ...)`.** Buena práctica más que causa de lentitud: el optimizador de SQL Server normalmente convierte este `IN` en una semiunión y descarta el `DISTINCT`, así que `EXISTS` no suele cambiar el plan. Se reescribe con `EXISTS` porque expresa mejor la intención («tiene al menos una devolución»).
5. **`TOP 1 ... ORDER BY fecha_creacion DESC` sin índice de apoyo.** Ordena los tickets de cada cliente en cada ejecución. Lo resuelve el índice `(id_cliente, fecha_creacion DESC) INCLUDE (canal)`.
6. **`GETDATE()` en el predicado.** Buena práctica, no causa de lentitud: SQL Server evalúa `GETDATE()` una sola vez por consulta, no por fila. Se calcula antes en una variable para que el rango del mes sea explícito y fácil de probar con otra fecha.

Observación de negocio: la consulta original suma **todos los estados** del mes, no solo los entregados. La reescritura conserva ese resultado para ser equivalente. Si la intención es venta neta, basta descomentar `AND p.estado = 'ENTREGADO'`. Conviene confirmarlo con quien pidió la consulta.

## Qué se midió (y qué no)
No se ejecutó en SQL Server. Se hizo un experimento con datos sintéticos en **SQLite**, elegido a propósito porque ejecuta las subconsultas correlacionadas fila a fila, como el plan que describe la prueba (DuckDB las reescribe solo y escondería el problema). Muestra la forma del problema; los tiempos absolutos de SQL Server serán otros.

| Pedidos | Original sin índices | Original con índices | Reescrita con índices |
|---:|---:|---:|---:|
| 4.000 | 0,07 s | 0,01 s | 0,00 s |
| 8.000 | 0,28 s | 0,05 s | 0,00 s |
| 16.000 | 0,88 s | 0,17 s | 0,00 s |
| 32.000 | 3,61 s | 0,67 s | 0,00 s |
| 500.000 | no se ejecutó | 199,18 s | 0,08 s |
| 2.000.000 | no se ejecutó | no se ejecutó | 0,38 s |

- Sin índices, el tiempo se multiplica por cuatro cada vez que los datos se duplican: crecimiento cuadrático, que es lo que lleva a más de 20 minutos con 50 millones.
- Con índices, la consulta original **sigue creciendo**: 199 segundos con 500.000 pedidos. La reescrita tarda 0,08 s sobre los mismos datos, y los resultados son idénticos (columna de comparación en el script).
- Con 100.000 pedidos, aislé la causa (`sqlserver/optimizacion/ablacion_cast.py`): la original con índices tarda 7,28 s; solo quitando el CAST del cruce con tickets baja a 0,06 s. Quitar además las funciones sobre la fecha apenas cambia el tiempo en este experimento (0,05 s). Los tiempos varían entre equipos (en otra ejecución: 10,86 s, 0,09 s y 0,05 s), pero la proporción se mantiene y las cuatro variantes dan el mismo resultado. Eso confirma que el CAST es el problema principal. La corrección de la fecha sigue siendo necesaria en SQL Server con 50M de filas, porque ahí la tabla de pedidos no se puede leer entera, pero no puedo demostrarla con este experimento.

## Índices y particiones propuestos
- `ix_pedidos_fecha (fecha_pedido) INCLUDE (id_cliente, valor_bruto, descuento)`: la venta del mes se lee por rango y sin volver a la tabla.
- `ix_pedidos_devueltos (id_cliente) WHERE estado = 'DEVUELTO'`: índice filtrado pequeño para el `EXISTS`.
- `ix_tickets_cliente_fecha (id_cliente, fecha_creacion DESC) INCLUDE (canal)`: el último ticket sale directo.
- **Partición mensual** de `pedidos` por `fecha_pedido`: la consulta del mes toca una sola partición y archivar meses antiguos es un `SWITCH`. Es una mejora de mantenimiento más que de velocidad; la velocidad la dan los índices. Para analítica pesada, una alternativa es un índice columnstore no agrupado.

Costo a mencionar: cada índice extra encarece las cargas. Con el ETL incremental de este proyecto (por lotes diarios) es aceptable.
