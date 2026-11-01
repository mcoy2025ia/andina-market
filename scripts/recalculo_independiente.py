"""Recálculo independiente de las cifras, escrito en una auditoría externa de la entrega.
No importa nada de src/: lee los CSV crudos con pandas y aplica las definiciones del enunciado y
las decisiones de negocio declaradas. Sirve para comprobar el ETL y el SQL con otro código.
Uso: python scripts/recalculo_independiente.py data/original   (imprime un JSON con las cifras)
"""
import sys
import unicodedata
import json
import pandas as pd
from dateutil.relativedelta import relativedelta

R = sys.argv[1].rstrip("/") + "/"
c = pd.read_csv(R + "clientes.csv", dtype=str, keep_default_na=False)
p = pd.read_csv(R + "pedidos.csv", dtype=str, keep_default_na=False)
g = pd.read_csv(R + "pagos.csv", dtype=str, keep_default_na=False)
t = pd.read_csv(R + "tickets_soporte.csv", dtype=str, keep_default_na=False)
out = {}


def canal(v):
    v = "".join(ch for ch in unicodedata.normalize("NFD", v) if unicodedata.category(ch) != "Mn")
    v = " ".join(v.upper().split())
    return {"WEB": "WEB", "PAGINA WEB": "WEB", "APP": "APP", "APLICACION": "APP",
            "TIENDA": "TIENDA", "TIENDA FISICA": "TIENDA"}.get(v)


# ---------------- pedidos
p["canal_n"] = p.canal.map(canal)
p["fp"] = pd.to_datetime(p.fecha_pedido, format="%Y-%m-%d %H:%M:%S", errors="coerce")
p["fe"] = pd.to_datetime(p.fecha_entrega.replace("", None), format="%Y-%m-%d", errors="coerce")
p["vb"] = pd.to_numeric(p.valor_bruto, errors="coerce")
p["ds"] = pd.to_numeric(p.descuento, errors="coerce")
p["dia"] = p.fp.dt.normalize()
r = {
    "canal_variante_sucia": (p.canal != p.canal_n).sum(),
    "canal_desconocido": p.canal_n.isna().sum(),
    "fuera_rango": ((p.dia < "2025-01-01") | (p.dia > "2026-09-30")).sum(),
    "fuera_rango_detalle": p.loc[(p.dia > "2026-09-30") | (p.dia < "2025-01-01"), "fp"].dt.year.value_counts().to_dict(),
    "vb_no_positivo": (p.vb <= 0).sum(),
    "desc_invalido": ((p.ds < 0) | (p.ds > p.vb)).sum(),
    "desc_negativo": (p.ds < 0).sum(),
    "desc_mayor_vb": (p.ds > p.vb).sum(),
    "entregado_sin_fecha": ((p.estado == "ENTREGADO") & p.fe.isna()).sum(),
    "entrega_antes_pedido": (p.fe.notna() & (p.fe < p.dia)).sum(),
    "cancelado_con_entrega": ((p.estado == "CANCELADO") & p.fe.notna()).sum(),
    "devuelto_sin_entrega": ((p.estado == "DEVUELTO") & p.fe.isna()).sum(),
    "cliente_inexistente": (~p.id_cliente.isin(c.id_cliente)).sum(),
}
mal = ((p.dia < "2025-01-01") | (p.dia > "2026-09-30") | (p.vb <= 0) | (p.ds < 0) | (p.ds > p.vb)
       | ((p.estado == "ENTREGADO") & p.fe.isna()) | (p.fe.notna() & (p.fe < p.dia)) | p.canal_n.isna())
r["individual_malo"] = int(mal.sum())
key = ["id_cliente", "fecha_pedido", "valor_bruto", "categoria"]
# duplicados en TODO el archivo (antes de reglas) vs solo entre válidos
grp_all = p.groupby(key).id_pedido.transform("count")
r["filas_en_grupo_dup_todo_archivo"] = int((grp_all > 1).sum())
r["dup_sobrantes_todo_archivo"] = int((grp_all > 1).sum() - p[grp_all > 1].groupby(key).ngroups)
cand = p[~mal].copy()
cand["ganador"] = cand.groupby(key).id_pedido.transform("min")
dup = cand.id_pedido != cand.ganador
r["dup_logicos_entre_validos"] = int(dup.sum())
# ¿los duplicados difieren en estado o canal?
gd = cand[cand.groupby(key).id_pedido.transform("count") > 1]
r["grupos_dup_con_estado_distinto"] = int((gd.groupby(key).estado.nunique() > 1).sum())
r["grupos_dup_con_canal_distinto"] = int((gd.groupby(key).canal_n.nunique() > 1).sum())
r["grupos_dup_con_desc_distinto"] = int((gd.groupby(key).descuento.nunique() > 1).sum())
r["grupos_dup_con_entrega_distinta"] = int((gd.groupby(key).fecha_entrega.nunique() > 1).sum())
validos = cand[~dup].copy()
r["pedidos_validos"] = len(validos)
r["registros_rechazados"] = len(p) - len(validos)
out["pedidos"] = r

ent = validos[validos.estado == "ENTREGADO"].copy()
ent["neto"] = ent.vb - ent.ds
out["venta_neta_total"] = int(ent.neto.sum())
out["pedidos_entregados"] = len(ent)
out["filas_gold_dia_canal_cat"] = int(ent.groupby([ent.dia, ent.canal_n, ent.categoria]).ngroups)
# sensibilidad: sin deduplicar / sin cuarentena alguna
todo_ent = p[p.estado == "ENTREGADO"]
out["sensibilidad"] = {
    "venta_sin_ninguna_regla": int((todo_ent.vb - todo_ent.ds).sum()),
    "venta_validos_sin_dedup": int((cand[cand.estado == "ENTREGADO"].vb - cand[cand.estado == "ENTREGADO"].ds).sum()),
}
# ganador alterno: max id en vez de min id (sensibilidad de la regla de desempate)
cand2 = p[~mal].copy()
cand2["g"] = cand2.groupby(key).id_pedido.transform("max")
v2 = cand2[cand2.id_pedido == cand2.g]
v2e = v2[v2.estado == "ENTREGADO"]
out["sensibilidad"]["venta_si_gana_max_id"] = int((v2e.vb - v2e.ds).sum())

# mensual por canal
ent["mes"] = ent.dia.dt.to_period("M")
m = ent.groupby(["canal_n", "mes"]).neto.sum().unstack(0).sort_index()
out["meses_por_canal"] = {k: int(m[k].notna().sum()) for k in m.columns}
out["share_canal"] = {k: round(100 * m[k].sum() / m.values.sum(), 1) for k in m.columns}
tot = ent.groupby("mes").agg(venta=("neto", "sum"), n=("neto", "size"))
out["mensual_total"] = {str(k): [int(v.venta), int(v.n)] for k, v in tot.iterrows()}
out["tienda_jun_sep_2026"] = [int(m.loc[pd.Period("2026-06"), "TIENDA"]), int(m.loc[pd.Period("2026-09"), "TIENDA"])]
out["var_mes_anterior_2026_08"] = round(100 * (tot.venta[pd.Period("2026-08")] / tot.venta[pd.Period("2026-07")] - 1), 1)
mm = m.pct_change() * 100
out["var_canal_2026"] = {str(i): {k: round(mm.loc[i, k], 1) for k in m.columns} for i in mm.index if i.year == 2026}
# DAX
dax = {}
for mes in ["2026-01", "2026-02", "2026-03", "2026-06", "2026-09"]:
    a = pd.Period(mes); b = a - 12
    v, n = tot.venta[a], tot.n[a]; pv = tot.venta[b]
    dax[mes] = {"venta": int(v), "pedidos": int(n), "ticket": round(v / n), "previo": int(pv),
                "var_pct": round(100 * (v - pv) / pv, 2)}
out["dax"] = dax
y25 = tot.venta[[x for x in tot.index if x.year == 2025]].sum()
y26 = tot.venta[[x for x in tot.index if x.year == 2026]].sum()
y25_9 = tot.venta[[x for x in tot.index if x.year == 2025 and x.month <= 9]].sum()
out["dax_anual"] = {"2025_completo": int(y25), "2026_ene_sep": int(y26), "2025_ene_sep": int(y25_9),
                    "var_anual_si_compara_12_vs_9": round(100 * (y26 / y25 - 1), 1),
                    "var_anual_comparable_9_vs_9": round(100 * (y26 / y25_9 - 1), 1)}

# ---------------- recompra por cohorte de registro
c["doc"] = c.documento.str.replace(r"\D", "", regex=True).str.lstrip("0")
c["fr"] = pd.to_datetime(c.fecha_registro, format="%Y-%m-%d")
c["persona"] = c.groupby("doc").id_cliente.transform("min")
out["clientes"] = {"total": len(c), "personas": int(c.persona.nunique()),
                   "doc_con_formato_sucio": int((c.documento != c.documento.str.replace(r"\D", "", regex=True)).sum()
                                                + (c.documento.str.replace(r"\D", "", regex=True).str.startswith("0")).sum()),
                   "ids_extra_por_doc": int(len(c) - c.doc.nunique())}
pers = c.groupby("persona").fr.min().dt.to_period("M").rename("cohorte")
e2 = ent.merge(c[["id_cliente", "persona"]], on="id_cliente", how="inner")
fechas = e2.groupby("persona").dia.apply(lambda s: sorted(s))
ULT = pd.Timestamp("2026-09-30")
rows = []
for persona, coh in pers.items():
    fs = fechas.get(persona)
    rec = {"cohorte": coh, "compra": fs is not None}
    if fs is not None:
        f0 = fs[0]
        for n in (1, 3, 6):
            lim = f0 + relativedelta(months=n)
            rec[f"madura{n}"] = lim <= ULT
            rec[f"r{n}"] = any(f0 < f <= lim for f in fs)
    rows.append(rec)
rc = pd.DataFrame(rows)
res = {}
for anio in (2025, 2026):
    s = rc[(rc.cohorte.dt.year == anio) & rc.compra]
    res[anio] = {}
    for n in (1, 3, 6):
        b = s[s[f"madura{n}"] == True]
        res[anio][f"{n}m"] = [round(100 * b[f"r{n}"].mean(), 1), int(len(b))]
out["recompra_por_anio_cohorte"] = res
# denominador alterno: todos los registrados maduros por fecha de registro (lectura literal del enunciado)
alt = {}
for anio in (2025, 2026):
    s = rc[rc.cohorte.dt.year == anio].copy()
    for n in (1, 3, 6):
        ok = s.cohorte.dt.to_timestamp() + pd.DateOffset(months=n) <= ULT
        b = s[ok]
        alt.setdefault(anio, {})[f"{n}m"] = round(100 * b.get(f"r{n}", pd.Series(dtype=bool)).fillna(False).astype(bool).mean(), 1)
out["recompra_denominador_todos_registrados"] = alt
coh6_2026 = rc[(rc.cohorte.dt.year == 2026) & rc.compra & (rc.get("madura6") == True)]
out["base_6m_2026"] = {"personas": len(coh6_2026), "cohortes": sorted(str(x) for x in coh6_2026.cohorte.unique())}

# ---------------- pagos
g["fpago"] = pd.to_datetime(g.fecha_pago, format="%Y-%m-%d", errors="coerce").fillna(
    pd.to_datetime(g.fecha_pago, format="%d/%m/%Y", errors="coerce"))
g["v"] = pd.to_numeric(g.valor, errors="coerce")
rechazados = set(p.id_pedido) - set(validos.id_pedido)
gp = {
    "fecha_dmy": int(g.fecha_pago.str.contains("/").sum()),
    "fecha_invalida": int(g.fpago.isna().sum()),
    "valor_cero": int((g.v == 0).sum()),
    "reembolsos": int((g.v < 0).sum()),
    "huerfanos": int((~g.id_pedido.isin(p.id_pedido)).sum()),
    "de_pedido_rechazado": int(g.id_pedido.isin(rechazados).sum()),
}
fped = validos.set_index("id_pedido").dia
gg = g[g.id_pedido.isin(validos.id_pedido)].copy()
gp["anterior_a_pedido"] = int((gg.fpago < gg.id_pedido.map(fped)).sum())
gok = gg[~(gg.fpago < gg.id_pedido.map(fped)) & gg.fpago.notna() & (gg.v != 0)].copy()
gk = ["id_pedido", "fpago", "v", "medio_pago"]
gok["gan"] = gok.groupby(gk).id_pago.transform("min")
gp["dup_logicos_fecha_normalizada"] = int((gok.id_pago != gok.gan).sum())
gok2 = gg.copy(); gok2["gan"] = gok2.groupby(["id_pedido", "fecha_pago", "valor", "medio_pago"]).id_pago.transform("min")
gp["dup_logicos_fecha_texto_sin_filtrar"] = int((gok2.id_pago != gok2.gan).sum())
gall = g.copy(); gall["gan"] = gall.groupby(["id_pedido", "fpago", "v", "medio_pago"]).id_pago.transform("min")
gp["dup_logicos_fecha_norm_todo_archivo"] = int((gall.id_pago != gall.gan).sum())
gall2 = g.copy(); gall2["gan"] = gall2.groupby(["id_pedido", "fecha_pago", "valor", "medio_pago"]).id_pago.transform("min")
gp["dup_logicos_fecha_texto_todo_archivo"] = int((gall2.id_pago != gall2.gan).sum())
gvalid = gok[gok.id_pago == gok.gan]
gp["pagos_validos"] = len(gvalid)
gp["pagos_rechazados"] = len(g) - len(gvalid)
# pedidos entregados sin pagos
gp["entregados_sin_pago_valido"] = int((~ent.id_pedido.isin(gvalid.id_pedido)).sum())
gp["entregados_sin_ningun_pago_crudo"] = int((~ent.id_pedido.isin(g.id_pedido)).sum())
# conciliación neto vs pagado
pag = gvalid.groupby("id_pedido").v.sum()
conc = ent.set_index("id_pedido").neto.to_frame().join(pag.rename("pagado"), how="inner")
gp["entregados_pagado_distinto_a_neto"] = int((conc.neto != conc.pagado).sum())
gp["reembolso_en_pedido_entregado"] = int(gvalid[(gvalid.v < 0) & gvalid.id_pedido.isin(ent.id_pedido)].shape[0])
out["pagos"] = gp
# watermark: distribución de fecha_carga - fecha_pago
lag = (pd.to_datetime(g.fecha_carga) - g.fpago).dt.days
out["pagos"]["lag_carga_dias"] = lag.describe().round(1).to_dict()
out["pagos"]["lag_carga_mayor_3"] = int((lag > 3).sum())

# ---------------- tickets
t["fc"] = pd.to_datetime(t.fecha_creacion, errors="coerce")
t["fz"] = pd.to_datetime(t.fecha_cierre.replace("", None), errors="coerce")
out["tickets"] = {
    "cierre_antes_creacion": int((t.fz < t.fc).sum()),
    "cerrado_sin_fecha": int(((t.estado == "CERRADO") & t.fz.isna()).sum()),
    "abierto_con_cierre": int(((t.estado != "CERRADO") & t.fz.notna()).sum()),
    "cliente_inexistente": int((~t.id_cliente.isin(c.id_cliente) & (t.id_cliente != "")).sum()),
    "pedido_inexistente": int((~t.id_pedido.isin(p.id_pedido) & (t.id_pedido != "")).sum()),
    "id_pedido_vacio": int((t.id_pedido == "").sum()),
    "ticket_dup_id": int(t.id_ticket.duplicated().sum()),
    "descripcion_distintas": int(t.descripcion.nunique()),
}
print(json.dumps(out, indent=1, default=str, ensure_ascii=False))
