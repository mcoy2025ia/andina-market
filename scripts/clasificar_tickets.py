"""Clasificación de tickets por tipo de caso y medición de su calidad.

Ejemplos (desde la raíz del repositorio):
  python scripts/clasificar_tickets.py evaluar --metodo reglas
  python scripts/clasificar_tickets.py evaluar --metodo llm --modelo deepseek-flash     # requiere DEEPSEEK_API_KEY
  python scripts/clasificar_tickets.py evaluar --metodo llm --repeticiones 2            # mide consistencia
  python scripts/clasificar_tickets.py clasificar --metodo llm                          # etiqueta tickets_soporte.csv

Conjuntos de evaluación:
  reales          las 34 descripciones distintas de tickets_soporte.csv, etiquetadas a mano (cerrado: casi trivial)
  generalizacion  150 frases NUEVAS (paráfrasis, errores de escritura, casos fuera de catálogo), sintéticas,
                  con etiqueta conocida: es donde se ve si el LLM aporta sobre las reglas.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src" / "shared"))
from tickets_ia import metricas  # noqa: E402
from tickets_ia.llm import MODELO_POR_DEFECTO, ClasificadorLLM, crear_llamada_deepseek  # noqa: E402
from tickets_ia.reglas import clasificar_reglas  # noqa: E402
from tickets_ia.taxonomia import ETIQUETAS  # noqa: E402

DATOS = RAIZ / "src" / "shared" / "tickets_ia" / "datos"
SALIDA = RAIZ / "resultados" / "ia"


def leer(nombre):
    with open(DATOS / nombre, encoding="utf-8", newline="") as f:
        return [(r["descripcion"], r["tipo"]) for r in csv.DictReader(f)]


def predecir(metodo, textos, modelo, telemetria=None):
    if metodo == "reglas":
        return [clasificar_reglas(t) for t in textos], None
    clf = ClasificadorLLM(crear_llamada_deepseek(modelo), modelo=modelo)
    res = clf.clasificar(textos)
    if telemetria is not None:
        telemetria.extend(clf.telemetria)
    return [r["tipo"] for r in res], {"llamadas": clf.llamadas, "invalidos": sum(not r["valido"] for r in res)}


def reservada(a):
    """Evalúa una muestra reservada con el arnés completo (IA-R04).

    La muestra la aporta quien la tenga (U06). Con `--sintetica` se usa una partición
    del conjunto de generalización, que sirve para comprobar que el arnés funciona,
    **no** para afirmar desempeño productivo: esas frases son sintéticas.
    """
    from tickets_ia.evaluacion import evaluar_reservada

    if a.sintetica:
        datos = leer("generalizacion.csv")
        # Partición determinista: una de cada tres frases se reserva y el resto
        # hace de desarrollo. Sin aleatoriedad, para que el informe sea repetible.
        muestra = [d for i, d in enumerate(datos) if i % 3 == 0]
        desarrollo = [d for i, d in enumerate(datos) if i % 3 != 0]
        procedencia = ("SINTÉTICA: partición del conjunto de generalización, escrito por una IA. "
                       "No acredita desempeño sobre tickets reales (pendiente U06).")
    else:
        muestra = leer_externo(a.muestra)
        desarrollo = leer("etiquetas_reales.csv") + leer("generalizacion.csv")
        procedencia = a.procedencia

    textos = [t for t, _ in muestra]
    reales = [e for _, e in muestra]
    telemetria = []
    predichos, extra = predecir(a.metodo, textos, a.modelo, telemetria)

    informe = evaluar_reservada(
        textos, reales, predichos,
        desarrollo=[t for t, _ in desarrollo], telemetria=telemetria,
        precios=json.loads(a.precios) if a.precios else None,
        procedencia=procedencia)
    informe["metodo"] = a.metodo + (f" ({a.modelo})" if a.metodo == "llm" else "")
    if extra:
        informe["cliente"] = extra

    SALIDA.mkdir(parents=True, exist_ok=True)
    destino = SALIDA / f"reservada_{a.metodo}{'_sintetica' if a.sintetica else ''}.json"
    destino.write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")

    lo, hi = informe["intervalo_exactitud"]
    print(f"\n== muestra reservada · {informe['metodo']} · n = {informe['n']}")
    print(f"   exactitud {informe['exactitud']:.3f}  (IC 95 % {lo:.3f} a {hi:.3f})")
    print(f"   F1 macro  {informe['f1_macro']:.3f}")
    print(f"   muestra válida (sin fugas literales): {informe['muestra_reservada_valida']}")
    for tipo, n in informe["errores_criticos"]["conteo"].items():
        print(f"   error crítico · {tipo}: {n}")
    tel = informe["telemetria"]
    if tel["llamadas"]:
        print(f"   {tel['llamadas']} llamadas · mediana {tel['latencia_s']['mediana']} s "
              f"· p95 {tel['latencia_s']['p95']} s · {tel['tokens']['total']} tokens")
    print(f"   procedencia: {informe['procedencia_de_la_muestra']}")
    print(f"   informe -> {destino}")


def leer_externo(ruta):
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f))
    faltan = [c for c in ("descripcion", "tipo") if filas and c not in filas[0]]
    if faltan:
        raise SystemExit(f"{ruta}: faltan las columnas {faltan}")
    return [(r["descripcion"], r["tipo"]) for r in filas]


def mostrar(nombre, m, errs, extra):
    print(f"\n== {nombre}: exactitud {m['exactitud']:.3f} | F1 macro {m['f1_macro']:.3f} | n = {m['n']}", extra or "")
    flojos = sorted(((v["f1"], k) for k, v in m["por_clase"].items() if v["soporte"] and v["f1"] is not None and v["f1"] < 1))
    for f1, k in flojos[:6]:
        print(f"   F1 {f1:.2f}  {k}")
    for t, r, p in errs[:8]:
        print(f"   error: «{t}» real={r} predicho={p}")


def evaluar(a):
    SALIDA.mkdir(parents=True, exist_ok=True)
    conjuntos = ["reales", "generalizacion"] if a.conjunto == "ambos" else [a.conjunto]
    for c in conjuntos:
        datos = leer("etiquetas_reales.csv" if c == "reales" else "generalizacion.csv")
        textos, reales = [d for d, _ in datos], [t for _, t in datos]
        corridas = []
        for i in range(a.repeticiones):
            pred, extra = predecir(a.metodo, textos, a.modelo)
            corridas.append(pred)
        m = metricas.evaluar(reales, corridas[0], ETIQUETAS)
        errs = metricas.errores(textos, reales, corridas[0])
        mostrar(f"{a.metodo} / {c}", m, errs, extra)
        if len(corridas) > 1:
            print(f"   consistencia entre ejecuciones: {metricas.consistencia(corridas[0], corridas[1]):.3f}")
        nombre = f"{a.metodo}_{c}" + (f"_{a.modelo}" if a.metodo == "llm" else "")
        (SALIDA / f"{nombre}.json").write_text(json.dumps({"metricas": m, "errores": errs}, ensure_ascii=False, indent=2), encoding="utf-8")


def clasificar(a):
    import pandas as pd
    ruta = Path(a.tickets)
    t = pd.read_csv(ruta, dtype=str)
    unicas = list(t["descripcion"].dropna().unique())  # se clasifica cada texto distinto una sola vez
    pred, extra = predecir(a.metodo, unicas, a.modelo)
    mapa = dict(zip(unicas, pred))
    t["tipo_caso"] = t["descripcion"].map(mapa)
    SALIDA.mkdir(parents=True, exist_ok=True)
    destino = SALIDA / f"tickets_clasificados_{a.metodo}.csv"
    t.to_csv(destino, index=False)
    print(f"{len(t)} tickets, {len(unicas)} textos distintos clasificados -> {destino}", extra or "")
    print(t["tipo_caso"].value_counts().to_string())


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)
    for nombre in ("evaluar", "clasificar", "reservada"):
        q = s.add_parser(nombre)
        q.add_argument("--metodo", choices=["reglas", "llm"], default="reglas")
        q.add_argument("--modelo", default=MODELO_POR_DEFECTO)
        if nombre == "evaluar":
            q.add_argument("--conjunto", choices=["reales", "generalizacion", "ambos"], default="ambos")
            q.add_argument("--repeticiones", type=int, default=1)
        elif nombre == "clasificar":
            q.add_argument("--tickets", default=str(RAIZ / "data" / "original" / "tickets_soporte.csv"))
        else:
            q.add_argument("--muestra", help="CSV con columnas descripcion,tipo")
            q.add_argument("--sintetica", action="store_true",
                           help="usar una partición del conjunto sintético para probar el arnés")
            q.add_argument("--procedencia", default="no declarada",
                           help="de dónde salió la muestra y quién la etiquetó")
            q.add_argument("--precios", help='JSON: {"moneda":"COP","entrada":0,"salida":0}')
    a = p.parse_args()
    if a.cmd == "reservada" and not (a.sintetica or a.muestra):
        p.error("reservada necesita --muestra o --sintetica")
    {"evaluar": evaluar, "clasificar": clasificar, "reservada": reservada}[a.cmd](a)


if __name__ == "__main__":
    main()
