"""Dashboard - Red de cuentas con comportamiento sincronizado."""
import json
from pathlib import Path

import streamlit as st
import pandas as pd
from streamlit_agraph import agraph, Node, Edge, Config

st.set_page_config(
    page_title="Red de Cuentas Sincronizadas",
    page_icon="🔍",
    layout="wide",
)

# ---------- Load data ----------
data_path = Path(__file__).parent / "data" / "exports" / "graph_data.json"
if not data_path.exists():
    st.error("Datos no encontrados.")
    st.stop()

data = json.loads(data_path.read_text(encoding="utf-8"))
accounts = data["accounts"]
stats = data["stats"]

# ---------- Header ----------
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

# ---------- Stats ----------
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Cuentas sincronizadas", stats["total_synced"])
c2.metric("🤖 Bots", stats["bots"], delta="alta probabilidad", delta_color="inverse")
c3.metric("⚠️ Sospechosas", stats["suspicious"])
c4.metric("✅ Probablemente humanas", stats["human"])
c5.metric("Tweets analizados", f"{stats['total_tweets']:,}")

st.divider()

# ---------- Graph ----------
st.subheader("Grafo de relaciones")
st.caption(
    "Las cuentas semilla de la campaña aparecen en rojo grande. "
    "Los nodos alrededor son cuentas sincronizadas coloreadas por clasificación: "
    "🔴 Bot · 🟠 Sospechosa · 🟢 Humana. Haz clic en un nodo para ver detalles."
)

ag_nodes = []
ag_edges = []

for n in data["nodes"]:
    img = n.get("image", "")
    ag_nodes.append(
        Node(
            id=n["id"],
            label=n["label"],
            size=n.get("size", 20),
            color=n.get("color", "#3498db"),
            image=img if img else "",
            shape="circularImage" if img else "dot",
            borderWidth=n.get("borderWidth", 2),
            font=n.get("font", {"size": 10, "color": "#ccc"}),
            title=n.get("title", ""),
        )
    )

for e in data["edges"]:
    ag_edges.append(
        Edge(
            source=e["from"],
            target=e["to"],
            color=e.get("color", {}).get("color", "#444"),
            width=e.get("width", 1),
        )
    )

config = Config(
    width="100%",
    height=700,
    directed=False,
    physics={
        "barnesHut": {
            "gravitationalConstant": -4000,
            "centralGravity": 0.4,
            "springLength": 180,
            "damping": 0.3,
        },
        "stabilization": {"iterations": 200},
    },
    backgroundColor="#0d0d1a",
)

col_graph, col_legend = st.columns([5, 1])

with col_graph:
    agraph(nodes=ag_nodes, edges=ag_edges, config=config)

with col_legend:
    st.markdown("**Clasificación**")
    st.markdown("🔴 Bot")
    st.markdown("🟠 Sospechosa")
    st.markdown("🟢 Probablemente humana")
    st.markdown("---")
    st.markdown("**Semillas de campaña**")
    for s in data.get("seeds", []):
        st.markdown(f"🎯 @{s['u']}")
    st.markdown("---")
    st.markdown("**Patrones detectados**")
    st.markdown("• Actividad idéntica")
    st.markdown("• Multi-objetivo")
    st.markdown("• Username autogenerado")
    st.markdown("• Volumen extremo")
    st.markdown("• Cuenta reciente")

st.divider()

# ---------- Classification breakdown ----------
st.subheader("Clasificación de cuentas")

tab_bots, tab_suspicious, tab_human, tab_all = st.tabs(
    [f"🤖 Bots ({stats['bots']})", f"⚠️ Sospechosas ({stats['suspicious']})",
     f"✅ Humanas ({stats['human']})", f"📋 Todas ({stats['total_synced']})"]
)


def build_df(accs):
    rows = []
    for a in accs:
        patterns = []
        if "patron_34" in a["groups"]:
            patterns.append("Actividad idéntica")
        if "multi_blanco" in a["groups"]:
            patterns.append("Multi-objetivo")

        seed_links = ", ".join(
            [f"@{sc['seed']} ({sc['type']})" for sc in a["seed_connections"]]
        ) if a["seed_connections"] else "—"

        reasons_es = {
            "actividad_identica": "Actividad idéntica",
            "multi_objetivo_4+": "Multi-objetivo (4+)",
            "multi_objetivo_3": "Multi-objetivo (3)",
            "multi_objetivo_2": "Multi-objetivo (2)",
            "username_autogenerado": "Username autogenerado",
            "username_numerico": "Username numérico",
            "sin_bio": "Sin biografía",
            "sin_avatar": "Sin foto de perfil",
            "cuenta_reciente": "Cuenta reciente (<1 año)",
            "cuenta_joven": "Cuenta joven (<2 años)",
            "ratio_sospechoso": "Ratio following/followers alto",
            "sin_followers": "Sin seguidores",
            "conectada_a_semillas": "Conectada a semillas",
        }

        bot_reasons = [reasons_es.get(r, r) for r in a.get("bot_reasons", [])
                       if not r.startswith("volumen_")]
        # Add volume reasons
        for r in a.get("bot_reasons", []):
            if r.startswith("volumen_extremo"):
                bot_reasons.append(f"Volumen extremo ({r.split('_')[-1]})")
            elif r.startswith("volumen_alto"):
                bot_reasons.append(f"Volumen alto ({r.split('_')[-1]})")

        rows.append({
            "Cuenta": f"@{a['u']}",
            "Score": a.get("bot_score", 0),
            "Clasificación": {"bot": "🤖 Bot", "suspicious": "⚠️ Sospechosa", "human": "✅ Humana"}.get(a.get("bot_label", ""), ""),
            "Razones": ", ".join(bot_reasons),
            "Patrón": " + ".join(patterns),
            "Semillas": seed_links,
            "Followers": a["followers"],
            "Following": a["following"],
            "Tweets": a["tweets"],
            "Edad (días)": a["age_days"],
            "Creada": a["created"],
            "Bio": "✅" if a["bio"] else "❌",
            "Foto": "✅" if a["av"] else "❌",
        })
    return pd.DataFrame(rows)


bots = sorted([a for a in accounts if a.get("bot_label") == "bot"], key=lambda x: -x.get("bot_score", 0))
suspicious = sorted([a for a in accounts if a.get("bot_label") == "suspicious"], key=lambda x: -x.get("bot_score", 0))
humans = sorted([a for a in accounts if a.get("bot_label") == "human"], key=lambda x: -x.get("bot_score", 0))

with tab_bots:
    st.markdown(f"**{len(bots)} cuentas** clasificadas como bot (score ≥ 0.50)")
    if bots:
        st.dataframe(build_df(bots), use_container_width=True, height=400)

with tab_suspicious:
    st.markdown(f"**{len(suspicious)} cuentas** clasificadas como sospechosas (score 0.25 - 0.49)")
    if suspicious:
        st.dataframe(build_df(suspicious), use_container_width=True, height=400)

with tab_human:
    st.markdown(f"**{len(humans)} cuentas** probablemente humanas (score < 0.25)")
    if humans:
        st.dataframe(build_df(humans), use_container_width=True, height=400)

with tab_all:
    st.dataframe(build_df(accounts), use_container_width=True, height=500)

st.divider()

# ---------- Methodology ----------
st.subheader("Metodología")
st.markdown(
    """
1. **Identificación de cuentas semilla:** Se identificaron las cuentas principales
   asociadas a la campaña presidencial de Abelardo De La Espriella.

2. **Detección de actividad sincronizada:** Se detectaron dos patrones principales:
   - **Actividad idéntica:** Grupo de cuentas con exactamente el mismo número de
     publicaciones, evidencia de operación automatizada.
   - **Comportamiento multi-objetivo:** Cuentas que responden de forma coordinada
     a múltiples cuentas distintas, lo cual es estadísticamente improbable de forma
     independiente.

3. **Clasificación bot/sospechosa/humana:** Cada cuenta recibe un puntaje basado en:
   - Pertenencia a patrón de actividad idéntica
   - Comportamiento multi-objetivo
   - Username con sufijos numéricos autogenerados
   - Ausencia de biografía o foto de perfil
   - Antigüedad de la cuenta
   - Volumen de publicaciones por día
   - Ratio following/followers
   - Conexión directa con cuentas semilla de campaña

4. **Grafo de relaciones:** Se muestra cómo las cuentas sincronizadas se conectan
   con las cuentas semilla de la campaña.

> **Nota:** Este análisis identifica patrones de comportamiento coordinado basándose
> en datos públicos. La presencia de un patrón no implica necesariamente automatización,
> pero la probabilidad de que estas coincidencias ocurran de forma independiente es
> estadísticamente muy baja.
"""
)
