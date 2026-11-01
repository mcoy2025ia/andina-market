"""Métricas de clasificación sin dependencias externas."""
from collections import Counter, defaultdict


def evaluar(reales, predichos, etiquetas):
    """Exactitud, precisión/recall/F1 por clase, F1 macro y matriz de confusión."""
    n = len(reales)
    aciertos = sum(r == p for r, p in zip(reales, predichos))
    matriz = defaultdict(Counter)
    for r, p in zip(reales, predichos):
        matriz[r][p] += 1
    por_clase = {}
    for e in etiquetas:
        tp = matriz[e][e]
        fp = sum(matriz[r][e] for r in etiquetas if r != e)
        fn = sum(matriz[e][p] for p in etiquetas if p != e)
        prec = tp / (tp + fp) if tp + fp else None
        rec = tp / (tp + fn) if tp + fn else None
        f1 = 2 * prec * rec / (prec + rec) if prec and rec else (0.0 if (tp + fp + fn) else None)
        por_clase[e] = {"soporte": tp + fn, "precision": prec, "recall": rec, "f1": f1}
    f1s = [v["f1"] for v in por_clase.values() if v["f1"] is not None and v["soporte"] > 0]
    return {"n": n, "exactitud": aciertos / n if n else None,
            "f1_macro": sum(f1s) / len(f1s) if f1s else None,
            "por_clase": por_clase, "matriz": {r: dict(c) for r, c in matriz.items()}}


def errores(textos, reales, predichos):
    return [(t, r, p) for t, r, p in zip(textos, reales, predichos) if r != p]


def consistencia(corrida_a, corrida_b):
    """Proporción de textos con la misma etiqueta en dos ejecuciones iguales."""
    return sum(a == b for a, b in zip(corrida_a, corrida_b)) / len(corrida_a) if corrida_a else None
