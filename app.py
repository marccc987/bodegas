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
c2.metric("Patrón de actividad idéntica", stats["patron_34"], help="Cuentas con exactamente el mismo número de tweets")
c3.metric("Comportamiento multi-objetivo", stats["multi_blanco"])
c4.metric("Conectadas a cuentas semilla", stats["connected_to_seeds"])
c5.metric("Tweets analizados", f"{stats['total_tweets']:,}")

st.divider()

# ---------- Graph ----------
st.subheader("Grafo de relaciones con cuentas semilla de campaña")
st.caption(
    "Las cuentas semilla (rojo grande) son las cuentas principales de la campaña. "
    "Los nodos alrededor son cuentas sincronizadas que interactúan con ellas. "
    "Haz clic en un nodo para ver detalles."
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
    st.markdown("**Nodos**")
    st.markdown("🔴 Cuentas semilla de campaña")
    st.markdown("🟠 Patrón de actividad idéntica")
    st.markdown("🟡 Alta coordinación")
    st.markdown("🔵 Coordinación detectada")
    st.markdown("---")
    st.markdown("**Semillas identificadas**")
    for s in data.get("seeds", []):
        st.markdown(f"🎯 @{s['u']}")

st.divider()

# ---------- Synchronized accounts list ----------
st.subheader("Listado de cuentas sincronizadas")

# Filter controls
col_f1, col_f2 = st.columns(2)
with col_f1:
    group_filter = st.multiselect(
        "Filtrar por patrón detectado",
        ["patron_34", "multi_blanco"],
        default=["patron_34", "multi_blanco"],
        format_func=lambda x: "Actividad idéntica (34 tweets)" if x == "patron_34" else "Comportamiento multi-objetivo",
    )
with col_f2:
    seed_filter = st.checkbox("Solo cuentas conectadas a semillas", value=False)

# Build dataframe
rows = []
for a in accounts:
    if not any(g in a["groups"] for g in group_filter):
        continue
    if seed_filter and not a["seed_connections"]:
        continue

    patterns = []
    if "patron_34" in a["groups"]:
        patterns.append("Actividad idéntica")
    if "multi_blanco" in a["groups"]:
        patterns.append("Multi-objetivo")

    seed_links = ", ".join(
        [f"@{sc['seed']} ({sc['type']})" for sc in a["seed_connections"]]
    ) if a["seed_connections"] else "—"

    rows.append({
        "Cuenta": f"@{a['u']}",
        "Patrones": " + ".join(patterns),
        "Conexión a semillas": seed_links,
        "Followers": a["followers"],
        "Following": a["following"],
        "Tweets": a["tweets"],
        "Edad (días)": a["age_days"],
        "Creada": a["created"],
        "Bio": "✅" if a["bio"] else "❌",
        "Foto": "✅" if a["av"] else "❌",
    })

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True, height=500)
st.caption(f"Mostrando {len(df)} de {stats['total_synced']} cuentas sincronizadas")

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

3. **Cruce con cuentas semilla:** Se verificó cuáles de las cuentas sincronizadas
   también interactúan directamente (retweet, mención, respuesta) con las cuentas
   principales de la campaña.

4. **Grafo de relaciones:** Se construyó un grafo que muestra las conexiones entre
   las cuentas sincronizadas y las cuentas semilla de campaña.

> **Nota:** Este análisis identifica patrones de comportamiento coordinado basándose
> en datos públicos. La presencia de un patrón no implica necesariamente automatización,
> pero la probabilidad de que estas coincidencias ocurran de forma independiente es
> estadísticamente muy baja.
"""
)
