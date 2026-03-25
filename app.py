"""Dashboard - Red de cuentas con comportamiento sincronizado."""
import json
from pathlib import Path

import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Red de Cuentas Sincronizadas",
    page_icon="🔍",
    layout="wide",
)

EXPORTS = Path(__file__).parent / "data" / "exports"
data_path = EXPORTS / "graph_data.json"
if not data_path.exists():
    st.error("Datos no encontrados.")
    st.stop()

data = json.loads(data_path.read_text(encoding="utf-8"))
accounts = data["accounts"]
stats = data["stats"]
seeds_list = data.get("seeds", [])

# ──────────── Header ────────────
st.markdown(
    """
    <div style='text-align:center; padding: 10px 0 20px;'>
        <h1>🔍 Red de Cuentas con Comportamiento Sincronizado</h1>
        <p style='color:#888; font-size:1.1rem;'>
            Análisis de cuentas en X que operan de manera coordinada en torno a la campaña
            presidencial de Abelardo De La Espriella · Colombia 2026
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ──────────── Stats ────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Cuentas sincronizadas", stats["total_synced"])
c2.metric("🤖 Bots", stats["bots"])
c3.metric("⚠️ Sospechosas", stats["suspicious"])
c4.metric("✅ Humanas", stats["human"])
c5.metric("Tweets analizados", f"{stats['total_tweets']:,}")

st.divider()

# ──────────── 1. MAIN GRAPH ────────────
st.subheader("Grafo general de relaciones")
st.caption(
    "Relaciones entre las cuentas sincronizadas y las cuentas semilla de la campaña. "
    "🟣 Semilla · 🔴 Bot · 🟠 Sospechosa · 🟢 Humana · Línea azul = reply · Línea roja = retweet"
)
main_graph = EXPORTS / "main_graph.png"
if main_graph.exists():
    st.image(str(main_graph), use_container_width=True)
else:
    st.warning("Grafo principal no generado.")

st.divider()

# ──────────── 2. PER-SEED GRAPHS ────────────
st.subheader("Desglose por cuenta semilla")
st.caption("Red de cada cuenta semilla con las cuentas sincronizadas que interactúan directamente con ella.")

seed_files = {
    "ABDELAESPRIELLA": EXPORTS / "seed_abdelaespriella.png",
    "defensoresco": EXPORTS / "seed_defensoresco.png",
    "ADLESinCensura": EXPORTS / "seed_adlesincensura.png",
    "AbelardoPTE": EXPORTS / "seed_abelardopte.png",
}

# Show in 2x2 grid
cols = st.columns(2)
for i, (seed_name, fpath) in enumerate(seed_files.items()):
    with cols[i % 2]:
        if fpath.exists():
            st.image(str(fpath), use_container_width=True)
        else:
            st.info(f"@{seed_name}: sin datos")

st.divider()

# ──────────── 3. ENRICHED TABLE ────────────
st.subheader("Clasificación de cuentas")

# Helper
def format_reasons(bot_reasons):
    reasons_es = {
        "actividad_identica": "Actividad idéntica",
        "multi_objetivo_4+": "Multi-objetivo (4+)",
        "multi_objetivo_3": "Multi-objetivo (3)",
        "multi_objetivo_2": "Multi-objetivo (2)",
        "username_autogenerado": "Username autogenerado",
        "username_numerico": "Username numérico",
        "sin_bio": "Sin biografía",
        "sin_avatar": "Sin foto",
        "cuenta_reciente": "Cuenta <1 año",
        "cuenta_joven": "Cuenta <2 años",
        "ratio_sospechoso": "Ratio F/F alto",
        "sin_followers": "Sin seguidores",
        "conectada_a_semillas": "Conectada a semillas",
    }
    out = []
    for r in bot_reasons:
        if r.startswith("volumen_extremo"):
            out.append(f"Volumen extremo ({r.split('_')[-1]})")
        elif r.startswith("volumen_alto"):
            out.append(f"Volumen alto ({r.split('_')[-1]})")
        elif r in reasons_es:
            out.append(reasons_es[r])
    return ", ".join(out)


def build_df(accs):
    rows = []
    for a in accs:
        # Seed connection columns
        seed_cols = {}
        for s in ["ABDELAESPRIELLA", "defensoresco", "ADLESinCensura", "AbelardoPTE"]:
            conn = next((sc for sc in a["seed_connections"] if sc["seed"] == s), None)
            seed_cols[s] = f"{conn['type']} (×{conn['weight']})" if conn else "—"

        rows.append({
            "Cuenta": f"@{a['u']}",
            "Score": a.get("bot_score", 0),
            "Clasificación": {
                "bot": "🤖 Bot",
                "suspicious": "⚠️ Sospechosa",
                "human": "✅ Humana",
            }.get(a.get("bot_label", ""), ""),
            "Indicadores": format_reasons(a.get("bot_reasons", [])),
            "→ ABDELAESPRIELLA": seed_cols["ABDELAESPRIELLA"],
            "→ defensoresco": seed_cols["defensoresco"],
            "→ ADLESinCensura": seed_cols["ADLESinCensura"],
            "→ AbelardoPTE": seed_cols["AbelardoPTE"],
            "Followers": a["followers"],
            "Following": a["following"],
            "Tweets": a["tweets"],
            "Edad (días)": a["age_days"],
            "Creada": a["created"],
        })
    return pd.DataFrame(rows)


tab_bots, tab_susp, tab_human, tab_all = st.tabs([
    f"🤖 Bots ({stats['bots']})",
    f"⚠️ Sospechosas ({stats['suspicious']})",
    f"✅ Humanas ({stats['human']})",
    f"📋 Todas ({stats['total_synced']})",
])

bots = sorted([a for a in accounts if a.get("bot_label") == "bot"],
              key=lambda x: -x.get("bot_score", 0))
suspicious = sorted([a for a in accounts if a.get("bot_label") == "suspicious"],
                    key=lambda x: -x.get("bot_score", 0))
humans = sorted([a for a in accounts if a.get("bot_label") == "human"],
                key=lambda x: -x.get("bot_score", 0))

with tab_bots:
    st.markdown(f"**{len(bots)} cuentas** con alta probabilidad de ser bots (score ≥ 0.50)")
    if bots:
        st.dataframe(build_df(bots), use_container_width=True, height=400)

with tab_susp:
    st.markdown(f"**{len(suspicious)} cuentas** con comportamiento sospechoso (score 0.25–0.49)")
    if suspicious:
        st.dataframe(build_df(suspicious), use_container_width=True, height=400)

with tab_human:
    st.markdown(f"**{len(humans)} cuentas** probablemente humanas (score < 0.25)")
    if humans:
        st.dataframe(build_df(humans), use_container_width=True, height=400)

with tab_all:
    st.dataframe(build_df(accounts), use_container_width=True, height=500)

st.divider()

# ──────────── Methodology ────────────
st.subheader("Metodología")
st.markdown(
    """
1. **Identificación de cuentas semilla:** Se identificaron las cuentas principales
   asociadas a la campaña presidencial de Abelardo De La Espriella.

2. **Detección de actividad sincronizada:** Se detectaron dos patrones:
   - **Actividad idéntica:** Grupo de cuentas con exactamente el mismo número de
     publicaciones, evidencia de operación automatizada.
   - **Comportamiento multi-objetivo:** Cuentas que responden de forma coordinada
     a múltiples cuentas distintas.

3. **Clasificación bot / sospechosa / humana:** Cada cuenta recibe un puntaje basado en:
   pertenencia a patrón de actividad idéntica, comportamiento multi-objetivo,
   username con sufijos numéricos autogenerados, ausencia de biografía o foto de perfil,
   antigüedad de la cuenta, volumen de publicaciones por día, ratio following/followers,
   y conexión directa con cuentas semilla.

4. **Grafo de relaciones:** Se verificó cuáles de las cuentas sincronizadas también
   interactúan directamente (retweet, reply, mención) con las cuentas semilla de la campaña.

> **Nota:** Este análisis identifica patrones de comportamiento coordinado basándose
> en datos públicos. La presencia de un patrón no implica necesariamente automatización,
> pero la probabilidad de que estas coincidencias ocurran de forma independiente es
> estadísticamente muy baja.
"""
)
