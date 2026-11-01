# Parte 1, punto 1: venta neta mensual y recompra por cohorte

Consultas: `sqlserver/01_ventas_recompra.sql` (T-SQL, entregable principal), `duckdb/`, `fabric/sql/` y `databricks/sql/` (misma lógica, distinto dialecto).

## Definiciones
- **Venta neta** = valor bruto menos descuento, solo pedidos entregados, atribuida a `fecha_pedido`.
- **Persona** = cliente maestro: los 40 clientes duplicados por documento cuentan una vez (6.040 clientes, 6.000 personas).
- **Cohorte** = mes de registro de la persona.
- **Recompra a N meses (N = 1, 3, 6)** = la persona hace otro pedido entregado, en una fecha posterior a su primer pedido entregado y dentro de N meses calendario de este.
- **Madurez:** solo se cuenta a quien ya tiene la ventana completa dentro de los datos (hasta 2026-09-30); si no, las cohortes recientes saldrían con una tasa artificialmente baja.

## Lectura de resultados (tres líneas)
1. La venta neta suma 14.177 millones: APP aporta el 42,8 %, WEB el 32,5 % y TIENDA el 24,7 %; desde diciembre de 2025 se estancó entre 780 y 950 millones al mes (agosto de 2026 cayó 9,4 %).
2. TIENDA cayó 51 % entre junio y septiembre de 2026 (217,6 a 105,8 millones) mientras APP crece y WEB queda casi plana: ahí está la mayor señal de alerta por canal.
3. La recompra se deterioró: a 3 meses fue 63,2 % en las cohortes de 2025 y 49,2 % en las de 2026 (a 1 mes, 32,1 % contra 26,1 %); los datos muestran la caída, no su causa, así que habría que revisar canal, categoría y experiencia de entrega antes de afirmar algo.

## Salvedades
- A 6 meses, las cohortes de 2026 con ventana completa son solo las de enero a marzo (856 personas); la comparación con 2025 (74,7 % contra 57,1 %) es válida, pero con una base menor.
- La base de la tasa son las personas con un primer pedido entregado y la ventana completa, no todos los registrados. Con todos los registrados de la cohorte como base, la caída se mantiene: a 3 meses, de 60,9 % a 46,4 %.
- La variación mensual ahora usa un calendario completo de enero 2025 a septiembre 2026 por canal: meses sin venta valen cero; previo cero o inexistente produce variación nula.
- El T-SQL no se ejecutó en SQL Server, y no hay traducción automática: es un texto paralelo a la versión DuckDB, revisado línea a línea. Las cifras de DuckDB coinciden con un recálculo independiente en pandas que no usa el código del ETL (`scripts/recalculo_independiente.py`). La versión Spark SQL actual se verifica en un job separado; consultar la evidencia vigente en ESTADO_IMPLEMENTACION.md.
