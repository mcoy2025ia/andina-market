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


def predecir(metodo, textos, modelo):
    if metodo == "reglas":
        return [clasificar_reglas(t) for t in textos], None
    clf = ClasificadorLLM(crear_llamada_deepseek(modelo))
    res = clf.clasificar(textos)
    return [r["tipo"] for r in res], {"llamadas": clf.llamadas, "invalidos": sum(not r["valido"] for r in res)}


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
    for nombre in ("evaluar", "clasificar"):
        q = s.add_parser(nombre)
        q.add_argument("--metodo", choices=["reglas", "llm"], default="reglas")
        q.add_argument("--modelo", default=MODELO_POR_DEFECTO)
        if nombre == "evaluar":
            q.add_argument("--conjunto", choices=["reales", "generalizacion", "ambos"], default="ambos")
            q.add_argument("--repeticiones", type=int, default=1)
        else:
            q.add_argument("--tickets", default=str(RAIZ / "data" / "original" / "tickets_soporte.csv"))
    a = p.parse_args()
    {"evaluar": evaluar, "clasificar": clasificar}[a.cmd](a)


if __name__ == "__main__":
    main()
