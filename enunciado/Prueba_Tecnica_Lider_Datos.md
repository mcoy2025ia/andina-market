# PROCESO DE SELECCIÓN

## Prueba Técnica
# Líder Técnico de Datos, BI y Automatización

**Caso práctico de datos, BI y arquitectura**

| Campo | Información |
|---|---|
| **Cargo** | Líder Técnico de Datos, BI y Automatización |
| **Fecha máxima de entrega** | Miércoles 21 de octubre de 2026, antes de las 11:59 p. m. (hora de Colombia) |
| **Dedicación estimada** | 5 a 6 horas |
| **Insumos** | `datos_prueba_tecnica.zip` (4 archivos CSV) |
| **Entrega** | Enlace a repositorio Git o archivo `.zip`, al correo indicado en la citación |
| **Sustentación** | 60 minutos, en fecha por confirmar |

---

## 1. Cómo está construida la prueba

La prueba tiene tres partes y se centra en la solidez técnica: SQL, Python, calidad de datos, optimización, modelado y arquitectura. La última parte evalúa cómo aplicas ese criterio al revisar el código de otros y resolver situaciones técnicas del equipo.

| Parte | Qué evalúa | Peso | Tiempo sugerido |
|---|---|---:|---:|
| **1. Resolución técnica** | SQL avanzado, optimización, calidad de datos, Python y DAX | 50 % | 3 h |
| **2. Arquitectura y decisiones** | Diseño de plataforma, tecnología, CI/CD y monitoreo | 30 % | 1,5 h |
| **3. Liderazgo técnico** | Revisión de código y situaciones técnicas del equipo | 20 % | 1 h |

- **Fecha límite:** Miércoles 21 de octubre de 2026, antes de las 11:59 p. m. (hora de Colombia).
- **Supuestos y priorización:** si algo es ambiguo o el tiempo no alcanza, decide, documéntalo y continúa.
- **Datos:** los archivos contienen errores intencionales. Detectarlos y tratarlos es parte de la prueba.
- **Herramientas e IA:** libre elección. Si usas IA generativa, indícalo; en la sustentación modificarás tu código en vivo.

## 2. El caso

Andina Market es una cadena que vende tecnología, hogar, moda y mercado por su página web, su app y sus tiendas físicas. Cada área calcula las ventas a su manera, los informes se arman a mano y la gerencia recibe cifras distintas para el mismo indicador. Tu reto es construir la solución técnica que lo resuelva.

### Archivos de datos

| Archivo | Registros aproximados | Columnas |
|---|---:|---|
| `clientes.csv` | ≈ 6.000 | `id_cliente`, `nombre`, `documento`, `ciudad`, `canal_registro`, `fecha_registro` |
| `pedidos.csv` | ≈ 19.700 | `id_pedido`, `id_cliente`, `fecha_pedido`, `canal`, `categoria`, `valor_bruto`, `descuento`, `estado`, `fecha_entrega` |
| `pagos.csv` | ≈ 20.900 | `id_pago`, `id_pedido`, `fecha_pago`, `valor` (negativo = reembolso), `medio_pago`, `fecha_carga` |
| `tickets_soporte.csv` | ≈ 2.100 | `id_ticket`, `id_cliente`, `id_pedido`, `fecha_creacion`, `canal`, `estado`, `fecha_cierre`, `descripcion` |

**Definición de venta neta:** valor bruto menos descuento de pedidos entregados. Los datos van de enero de 2025 a septiembre de 2026.

## 3. Parte 1. Resolución técnica (50 %)

1. **SQL.** Venta neta mensual por canal con su variación frente al mes anterior, y tasa de recompra por cohorte de registro (porcentaje de clientes que vuelven a comprar a 1, 3 y 6 meses). Indica en tres líneas qué te dicen los resultados.
2. **Calidad de datos.** Identifica al menos cinco tipos de problemas en los archivos, cuántos registros afectan y cómo los tratarías.
3. **Python.** Un proceso que cargue pedidos y pagos de forma incremental e idempotente (si se ejecuta dos veces, el resultado no cambia), aplique reglas de calidad, envíe los registros inválidos a una tabla de cuarentena y genere una tabla de venta neta diaria por canal y categoría. Incluye al menos tres pruebas unitarias.
4. **DAX.** Escribe y explica las medidas de venta neta, ticket promedio y variación frente al mismo mes del año anterior.
5. **Optimización.** La siguiente consulta tarda más de 20 minutos con 50 millones de pedidos. Identifica los problemas, reescríbela y propone índices o particiones.

```sql
SELECT c.id_cliente,
       (SELECT SUM(p.valor_bruto - p.descuento) FROM pedidos p
         WHERE p.id_cliente = c.id_cliente
           AND YEAR(p.fecha_pedido) = YEAR(GETDATE())
           AND MONTH(p.fecha_pedido) = MONTH(GETDATE())) AS venta_mes,
       (SELECT TOP 1 t.canal FROM tickets_soporte t
         WHERE CAST(t.id_cliente AS VARCHAR(20)) = CAST(c.id_cliente AS VARCHAR(20))
         ORDER BY t.fecha_creacion DESC) AS ultimo_canal_soporte
  FROM clientes c
 WHERE c.id_cliente IN (SELECT DISTINCT id_cliente FROM pedidos WHERE estado = 'DEVUELTO')
 ORDER BY venta_mes DESC;
```

**Entrega:** el código en un repositorio con un `README` que permita ejecutarlo desde cero.

## 4. Parte 2. Arquitectura y decisiones (30 %)

Hoy la empresa tiene un SQL Server on-premise con procedimientos almacenados sin versionar, más de 30 informes en Power BI (varios conectados a archivos Excel) y fuentes con APIs: e-commerce, app, punto de venta y la plataforma de soporte. El presupuesto se aprueba por fases.

**En máximo dos páginas, entrega:**

1. Un diagrama de la arquitectura de datos que propones a 12 meses.
2. Tu recomendación entre dos alternativas tecnológicas (por ejemplo, Microsoft Fabric o Databricks), con criterios de costo, riesgo y capacidad del equipo.
3. Cómo versionarías, desplegarías y monitorearías los procesos y modelos (Git, ambientes, CI/CD, alertas y calidad de datos).
4. Qué entregarías en los primeros 90 días y cómo garantizarías que todas las áreas usen la misma cifra de ventas.

## 5. Parte 3. Liderazgo técnico (20 %)

### 3.1. Revisión de código

Un analista junior de tu equipo abrió este pull request. Escribe la revisión como si fuera real: comentarios clasificados como bloqueante, importante o sugerencia, explicando el porqué para que aprenda. Luego propone la versión corregida.

```python
import pandas as pd
import pyodbc
from datetime import datetime

conn = pyodbc.connect("DRIVER={SQL Server};SERVER=10.0.0.15;DATABASE=DWH;UID=admin;PWD=<REDACTADO_EJEMPLO>")

def ventas_netas(canal, pedidos=[]):
    fecha = datetime.today().strftime("%Y-%m-%d")
    query = f"SELECT * FROM pedidos WHERE canal = '{canal}' AND fecha_pedido = '{fecha}'"
    df = pd.read_sql(query, conn)
    resultado = pd.DataFrame()
    for i, row in df.iterrows():
        if row['estado'] != 'CANCELADO':
            pedidos.append(row['id_pedido'])
        resultado = resultado.append(row)
    total = resultado['valor_bruto'].sum() - resultado['descuento'].sum()
    ticket = total / len(pedidos)
    return round(total), round(ticket)

def enviar_reporte():
    try:
        for c in ['WEB', 'APP', 'TIENDA']:
            total, ticket = ventas_netas(c)
            print("Ventas " + c + ": " + str(total) + " - ticket: " + str(ticket))
            # TODO enviar correo
    except:
        pass

enviar_reporte()
```

### 3.2. Situaciones

Responde cada una en máximo 10 líneas.

1. **Incidente.** Lunes, 7:30 a. m.: el informe de ventas que recibió la gerencia muestra 40 % menos que el valor real y ya llegó a presidencia. ¿Qué haces en las primeras dos horas y qué dejas para que no vuelva a pasar?
2. **Conflicto.** El desarrollador más antiguo, el que más sabe del negocio, se niega a usar los estándares que definiste y sus cambios han fallado dos veces en producción. ¿Cómo lo manejas?

## 6. Sustentación (60 minutos)

| Bloque | Duración | Contenido |
|---|---:|---|
| **Presentación** | 10 min | Hallazgos y arquitectura propuesta |
| **Técnica** | 30 min | Preguntas sobre tu entrega y un ajuste en vivo a tu código |
| **Liderazgo técnico** | 10 min | Profundización en la parte 3 |
| **Tus preguntas** | 10 min | Espacio para conocer el reto y el equipo |

## Opcional (suma puntos, no resta)

Clasifica con IA las descripciones de `tickets_soporte.csv` por tipo de caso y explica cómo medirías la calidad del resultado.

---

## Observaciones de transcripción

- Se conservaron el contenido, los nombres de archivos, los campos, las cifras, las instrucciones y el código fuente del documento.
- En el código Python, el nombre del controlador ODBC aparece partido por un salto de línea en el PDF entre `SQL` y `Server`. Se unió como `SQL Server` para conservar la cadena de conexión en una sola línea; no se modificó el resto del código.
- La tabla de la sustentación aparece dividida entre las páginas 4 y 5 del PDF original. Se consolidó en una sola tabla, sin cambiar sus bloques ni duraciones.
- No se añadieron soluciones ni se corrigieron posibles errores técnicos del enunciado: el archivo se convirtió, no se reinterpretó.
