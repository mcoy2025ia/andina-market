# Parte 3. Liderazgo técnico

## 3.1 Revisión del pull request

> Hola, gracias por abrir el PR y por querer automatizar este reporte: la idea es buena y se nota el esfuerzo. Te dejo comentarios agrupados por prioridad, con el porqué de cada uno, porque varios son errores muy comunes que conviene conocer. Los bloqueantes hay que resolverlos antes de integrar.

### Bloqueantes (no se puede integrar así)

| # | Dónde | Comentario | Por qué importa |
|---|---|---|---|
| 1 | `pyodbc.connect("...UID=admin;PWD=<REDACTADO_EJEMPLO>")` | Hay una contraseña y un usuario administrador escritos en el código. | Quien lea el repositorio tiene acceso total al DWH, y la clave ya quedó en el historial de Git aunque se borre. Hay que **rotar esa contraseña hoy**, leer la cadena de conexión desde una variable de entorno o Key Vault y usar un usuario de solo lectura con permisos mínimos. |
| 2 | `f"SELECT ... canal = '{canal}' ..."` | El SQL se arma con un f-string. | Es inyección SQL: con `canal = "x' OR 1=1; DROP TABLE pedidos --"` se ejecuta lo que el usuario escriba. Se usan parámetros (`?`), que separan el código de los datos. |
| 3 | `def ventas_netas(canal, pedidos=[])` | Un argumento por defecto mutable. | Python crea esa lista una sola vez, y se comparte entre llamadas: al calcular APP ya trae los pedidos de WEB, y TIENDA los de las dos anteriores. El ticket de cada canal sale mal y no da error. Se usa `None` o, mejor, no se necesita la lista. |
| 4 | `resultado.append(row)` fuera del `if` | El total suma **todos** los pedidos, incluso cancelados y devueltos, pero el ticket divide por los que no son cancelados. | La venta neta es solo de pedidos `ENTREGADO`. El numerador y el denominador miden cosas distintas, y las cifras salen infladas e inconsistentes. Es un error de negocio, no de estilo. |
| 5 | `fecha_pedido = '{fecha}'` | Se compara una columna con hora contra una fecha sin hora. | `fecha_pedido` incluye hora (por ejemplo `2026-09-10 09:05:00`), así que la igualdad solo encuentra pedidos de las 00:00:00 y el reporte sale casi vacío. Debe ser un rango: `>= día AND < día siguiente`. |
| 6 | `DataFrame.append` | Ese método fue eliminado en pandas 2.0. | Con una versión actual falla con `AttributeError` (lo comprobé con pandas 3). Además, `iterrows` más `append` en un bucle es muy lento: copia todo el DataFrame en cada vuelta. La suma se hace en SQL con `SUM`/`GROUP BY`. |
| 7 | `except: pass` | Se traga cualquier error y sigue como si nada. | Es lo que convierte los errores 3, 5 y 6 en un reporte vacío que nadie nota. Un `except` sin tipo captura incluso `Ctrl+C`. Si algo falla, debe verse: se registra el error y el proceso termina con código distinto de 0 para que la herramienta que lo programa avise. |
| 8 | `total / len(pedidos)` | División por cero cuando no hay pedidos. | Un día o un canal sin ventas rompe el cálculo (y el `except` lo esconde). Si no hay pedidos, el ticket no existe: se devuelve `None`, no 0. |

### Importantes

| # | Comentario | Por qué |
|---|---|---|
| 9 | `datetime.today()` usa la hora y la zona del servidor. | Los servidores suelen estar en UTC: pasadas las 7 p. m. en Colombia ya es «mañana». Usa la zona `America/Bogota`. |
| 10 | Un reporte que sale a las 7:00 con el día en curso sale casi vacío. | Confirma con quien lo pidió si quiere el día anterior (cerrado). En la versión corregida es el valor por defecto y es un parámetro. |
| 11 | La conexión se abre al importar el módulo y nunca se cierra. | Importar el archivo ya se conecta a producción (en pruebas también). Abre la conexión dentro de la función y ciérrala con `with`/`closing`. |
| 12 | `enviar_reporte()` se ejecuta al importar. | Protégelo con `if __name__ == "__main__":`; así el módulo se puede importar y probar sin efectos. |
| 13 | `SELECT *` | Trae todas las columnas cuando solo hacen falta tres, y se rompe si alguien cambia la tabla. Mejor, que el motor agregue y devuelva solo `canal`, `total` y `pedidos`. |
| 14 | No hay pruebas. | Con este PR una prueba de «día sin pedidos» o de «dos llamadas seguidas» habría encontrado los errores 3 y 8. |
| 15 | La consulta lee la tabla cruda `pedidos`, no la tabla oficial de venta. | Aunque se arreglen los bloqueantes, la cifra no coincidiría con Power BI: en los datos del caso, 810 pedidos (4,1 %) traen el canal con otra escritura (`app `, `PAGINA WEB`) y no entrarían en `canal = 'APP'`, y 295 pedidos duplicados se contarían dos veces. Un reporte de ventas tiene que leer la misma tabla certificada que el resto de la empresa (`gold.fact_venta_neta_diaria`); si no, volvemos al problema de «cada área con su cifra». |

### Sugerencias

- Usa `logging` en lugar de `print`, con nivel y fecha.
- Define los canales y la consulta como constantes al inicio del archivo.
- El driver `{SQL Server}` es antiguo; usa «ODBC Driver 18 for SQL Server».
- Añade anotaciones de tipos y una línea de documentación por función.
- Termina el `TODO` del correo en otro PR, para que este quede pequeño y fácil de revisar.

**Lo que está bien:** separar el cálculo (`ventas_netas`) del envío (`enviar_reporte`), y recorrer los canales con un bucle. Esa estructura se conserva en la versión corregida.

### Versión corregida
`src/shared/reporte_ventas.py`, con cinco pruebas en `tests/test_reporte_ventas.py` (suma de las categorías del día por canal, canal sin ventas, día sin pedidos, llamadas repetidas con el mismo resultado y día a reportar en hora de Colombia). Lee `gold.fact_venta_neta_diaria` (comentario 15), que ya trae solo entregados, el canal normalizado y sin duplicados; por eso el filtro de estado y el rango de horas (bloqueantes 4 y 5) ya no están en la consulta, sino en el ETL. Las pruebas pasan sobre SQLite en memoria; el SQL con `?` es el mismo que ejecutaría pyodbc, pero **no se probó contra un SQL Server real**.

## 3.2 Situaciones (10 líneas cada una)

### 1. Incidente: el informe de ventas muestra 40 % menos y llegó a presidencia

1. 7:30: aviso escrito a gerencia y presidencia: «La cifra de hoy está en revisión, no la usen; la confirmo a las 9:30».
2. Pauso envíos y actualizaciones automáticas, nombro un responsable y un solo canal de comunicación.
3. Diagnostico de la fuente hacia el informe: comparo contra Gold y contra el transaccional.
4. Reviso el registro de la carga nocturna, la cuarentena y el volumen frente al promedio (un 40 % suele ser carga parcial).
5. Miro el historial de Git y los despliegues de las últimas 24 horas, y los filtros del informe.
6. Corrijo: revierto el despliegue o reproceso la carga (es idempotente) y concilio con la fuente antes de enviar.
7. Mando la cifra corregida a los mismos destinatarios, con una explicación de dos líneas.
8. Para que no vuelva: compuerta que bloquea la publicación si el volumen cae o no cuadra la conciliación, y verificación a las 6:00.
9. Prueba de regresión del caso y alerta temprana en Teams.
10. Análisis posterior en 48 horas, sin buscar culpables, con responsables y fechas.

### 2. Conflicto: el desarrollador más antiguo rechaza los estándares y sus cambios fallaron dos veces

1. Hablo con él a solas y con curiosidad: quiero entender por qué se resiste, y reconozco su conocimiento del negocio.
2. Separo estándares (se pueden discutir) de fallos en producción (son hechos).
3. Revisamos juntos los dos fallos, sin culpas: qué paso (revisión, prueba, ambiente de prueba) los habría detectado.
4. Le doy un papel: dueño de las pruebas de reglas de negocio o revisor de la lógica en los PR de otros.
5. Dejo claro qué no se negocia (PR, pruebas y revisión antes de producción) y qué sí (herramientas y forma).
6. Acordamos 30 días de prueba con métricas simples: despliegues fallidos y reversiones.
7. Hago que cumplir sea lo fácil: CI automático y rama protegida, sin depender de mi insistencia.
8. Nunca lo critico en público; dejo registro de los acuerdos.
9. Si persiste, lo hablo con mi jefe con hechos y datos.
10. Mientras tanto, sus cambios pasan por revisión obligatoria antes de llegar a producción.
