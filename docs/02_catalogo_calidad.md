# Catálogo de problemas de calidad de datos

Generado por `scripts/catalogo_calidad.py` con los conteos reales de los CSV y del almacén local. Los conteos de cuarentena son **registros distintos** (un registro con dos problemas cuenta una vez por regla).

| # | Problema | Tabla | Registros | Tratamiento |
|---|---|---|---:|---|
| 1 | Canal escrito de ocho formas distintas (`app`, `web `, `PAGINA WEB`, `TIENDA FISICA`...) | pedidos | 810 | Se normaliza a WEB, APP o TIENDA con un mapa explícito; un valor fuera del mapa va a cuarentena (`CANAL_DESCONOCIDO`). |
| 2 | Fecha de pago en dos formatos (`yyyy-mm-dd` y `dd/mm/yyyy`) | pagos | 1.200 | Se interpreta cada formato de forma explícita; nunca se deja que pandas adivine (`03/04/2026` es 3 de abril). |
| 3 | Documento del cliente con puntos, espacios o ceros a la izquierda | clientes | 40 | Se limpia a solo dígitos sin ceros iniciales; se conserva el original en `documento_original`. |
| 4 | Clientes duplicados (mismo documento limpio, distinto `id_cliente`) | clientes | 40 | Se conservan ambos ids y la vista `v_cliente_maestro` los une en una persona para contarla una sola vez. |
| 5 | Pedidos con cliente que no existe en `clientes` | pedidos | 60 | Se conservan (la venta es real) con `flag_cliente_desconocido`; el modelo Gold del DDL lo asigna a un cliente DESCONOCIDO. |
| 6 | Pedidos duplicados con otro `id_pedido` (mismo cliente, fecha-hora, valor y categoría) | pedidos | 295 | Se conserva uno (el que ya estaba en Silver, o el menor id) y el resto va a cuarentena. |
| 7 | Descuento negativo o mayor que el valor bruto | pedidos | 74 | Cuarentena (`DESCUENTO_INVALIDO`). |
| 8 | Valor bruto cero o negativo | pedidos | 35 | Cuarentena (`VALOR_BRUTO_NO_POSITIVO`). |
| 9 | Fecha de pedido fuera del rango del caso (2027) | pedidos | 20 | Cuarentena (`FECHA_FUERA_DE_RANGO`). |
| 10 | Entrega anterior a la fecha del pedido | pedidos | 87 | Cuarentena (`ENTREGA_ANTERIOR_A_PEDIDO`). |
| 11 | Pagos duplicados (mismo pedido, valor y medio; incluso con la fecha en otro formato) | pagos | 344 | Se conserva uno y el resto va a cuarentena. El conteo es sobre los pagos que pasaron las demás reglas; sobre el archivo completo, sin filtrar, son más (350 con los datos del caso). |
| 12 | Pagos de un pedido que no existe | pagos | 70 | Cuarentena (`PAGO_HUERFANO`). |
| 13 | Pagos de un pedido que fue rechazado | pagos | 345 | Cuarentena (`PEDIDO_EN_CUARENTENA`); si el pedido se corrige o llega después, el pago se relee y se carga en la siguiente corrida. |
| 14 | Ticket con fecha de cierre anterior a la de creación | tickets | 99 | Tratamiento propuesto (el ETL actual no carga tickets; el DDL lo prevé): se conserva el ticket y `horas_resolucion` queda nula para no promediar tiempos negativos. |
| 15 | Ticket cerrado sin fecha de cierre | tickets | 59 | Tratamiento propuesto, igual que el anterior; tampoco está implementado en el ETL. |

## Hallazgos de negocio (no son errores de formato, se reportan)

- **122 pedidos entregados no tienen ningún pago registrado.** Pueden ser pagos no cargados o ventas sin cobrar; no se corrigen, se escalan.
- 345 pagos pertenecen a pedidos que fueron rechazados por calidad; conviene verificar si hubo cobros duplicados.

## Alcance

Cada regla vive en `src/shared/andina_etl/rules.py` y tiene su prueba en `tests/test_rules.py`. Los problemas 1 a 5 se **corrigen o se marcan**; del 6 al 13 se **rechazan a cuarentena**, con la fila original completa en JSON para poder revisarla y reprocesarla; el 14 y el 15 (tickets) son tratamientos propuestos que el ETL todavía no implementa. Hay además reglas de defensa que con estos datos no encuentran casos: ids nulos, ids repetidos en el mismo archivo y fechas ilegibles.
