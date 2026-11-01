# Contratos del caso y decisiones de producción

## Vigente en el código local

- Venta = bruto menos descuento de pedidos ENTREGADO, atribuida a `fecha_pedido`.
- Enero 2025 a septiembre 2026; SQL mensual completa los 21 meses para cada canal. Cambiar el rango implica actualizar `Config` **y** los calendarios SQL.
- Sin venta en un mes: cero. Primer mes o previo cero: variación nula, no infinito ni crecimiento cero ficticio.
- Recompra: cohorte de registro; ventana de 1/3/6 meses calendario desde primera compra; otro pedido en fecha posterior; denominador con ventana madura.
- Personas: documentos normalizados unen IDs de cliente; un cliente desconocido conserva la venta y usa el miembro 0 en Gold.
- Fuente CSV en UTF-8, con BOM opcional, cabecera sin duplicados y columnas mínimas declaradas en `contracts.py`. Extra se conserva; fila con ancho distinto bloquea el archivo. Cabecera vacía bloquea; cabecera válida sin filas es técnicamente admisible y queda sujeta a compuertas.
- Importes: pesos enteros en BIGINT. Se aceptan `100` y `100.00`; `100.50`, notación no contractual y valores fuera de rango se rechazan con las reglas de importe. No se convierte una fracción silenciosamente en pesos enteros. `Decimal` evita pérdida por punto flotante.
- Categoría: se conserva como texto limpio y se incorpora como dimensión; **no** se afirma que exista catálogo gobernado. No se rechaza una categoría nueva inventando una decisión de negocio.
- Pagos: lookback de tres días; pendientes por pedido se releen; `--reconciliar` permite releer todo. Ausencia en fuente no autoriza borrar.
- Tickets: ID y fecha de creación válidos para Silver; cierre inválido o faltante se marca; horas de resolución solo para cerrado con fechas coherentes. No se aplica SLA contractual todavía.

## Pendiente de ratificar para una operación real

| Tema | Decisión requerida | Cambio técnico después de decidir |
|---|---|---|
| Moneda | ¿Pesos enteros o centavos? ¿Rechazo o redondeo? | Migrar tipos de Silver/Gold/DDL/medidas y referencias conjuntamente; nunca solo un cast |
| Devoluciones | ¿Cambian venta histórica, período de devolución o una métrica de recaudo? | Versionar contrato y recalcular períodos afectados |
| Snapshots | ¿Son completos, incrementales o parciales? ¿Cómo llegan bajas? | Habilitar bajas solo con tombstones o snapshot certificado |
| Categorías | Catálogo, responsable y evolución | Configuración versionada y tratamiento de no reconocidas |
| Frescura y calidad | Fecha/hora esperada, tolerancias y umbrales | JSON de política aprobado; no inferirlo del archivo del caso |
| Soporte | Estados finales y definición de SLA | Reglas y casos de prueba acordados |

No hay firma de negocio implícita. Para la prueba se conserva su definición; las alternativas anteriores no la reemplazan.

## Mapeo de consumo

`silver_*` → `gold.dim_*` → `gold.fact_pedido` / `fact_pago` / `fact_ticket` / `fact_venta_neta_diaria`.

El pipeline local reconstruye hechos dentro de la misma transacción; inserta claves de dimensión nuevas conservando las existentes. El cargador de SQL Server reutiliza esas claves con `IDENTITY_INSERT` en un entorno de pruebas expresamente confirmado. No pretende que el DDL de SQL Server sea universal para Fabric Warehouse.

El modelo semántico requiere configurar relaciones, tabla de fechas, filtros y medidas en Power BI. La existencia de `gold.fact_pedido` local no valida DAX.
