"""Streamlit dashboard - Red de cuentas sincronizadas."""
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
attackers = data["attackers"]
stats = data["stats"]

# ---------- Header ----------
st.markdown(
    """
    <div style='text-align:center; padding: 10px 0 20px;'>
        <h1>🔍 Red de Cuentas con Comportamiento Sincronizado</h1>
        <p style='color:#888; font-size:1.1rem;'>
            Cuentas en X que responden coordinadamente a múltiples críticos
            de la campaña presidencial de Abelardo De La Espriella
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------- Stats ----------
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Cuentas analizadas", f"{stats['total_accounts_analyzed']:,}")
c2.metric("Tweets analizados", f"{stats['total_tweets']:,}")
c3.metric("Cuentas sincronizadas", f"{stats['total_multi']}")
c4.metric("Atacan 4 de 5 blancos", f"{stats['multi_4plus']}", delta="alta coordinación", delta_color="inverse")
c5.metric("Atacan 3 blancos", f"{stats['multi_3']}")

st.divider()

# ---------- Graph ----------
st.subheader("Grafo de relaciones entre cuentas sincronizadas")
st.caption(
    "Cada nodo es una cuenta. Dos cuentas se conectan si responden a los mismos blancos. "
    "Las conexiones rojas indican 3 o más blancos en común."
)

# Build agraph nodes & edges
ag_nodes = []
ag_edges = []

for n in data["nodes"]:
    color = n.get("color", "#f1c40f")
    size_val = n.get("size", 20)
    img = n.get("image")

    ag_nodes.append(
        Node(
            id=n["id"],
            label=n["label"],
            size=size_val,
            color=color,
            image=img if img else "",
            shape="circularImage" if img else "dot",
            borderWidth=2,
            font={"size": 10, "color": "#cccccc"},
            title=n.get("title", ""),
        )
    )

for e in data["edges"]:
    ecolor = e.get("color", {}).get("color", "#555")
    width = e.get("width", 1)
    ag_edges.append(
        Edge(
            source=e["from"],
            target=e["to"],
            color=ecolor,
            width=width,
        )
    )

config = Config(
    width="100%",
    height=700,
    directed=False,
    physics={
        "barnesHut": {
            "gravitationalConstant": -5000,
            "centralGravity": 0.5,
            "springLength": 150,
            "damping": 0.3,
        },
        "stabilization": {"iterations": 200},
    },
    node={"borderWidthSelected": 4},
    backgroundColor="#0d0d1a",
)

col_graph, col_legend = st.columns([5, 1])

with col_graph:
    agraph(nodes=ag_nodes, edges=ag_edges, config=config)

with col_legend:
    st.markdown("**Nodos**")
    st.markdown("🔴 Atacan 4+ blancos")
    st.markdown("🟠 Atacan 3 blancos")
    st.markdown("🟡 Atacan 2 blancos")
    st.markdown("---")
    st.markdown("**Conexiones**")
    st.markdown("🔴 3+ blancos compartidos")
    st.markdown("⚫ 2 blancos compartidos")
    st.markdown("---")
    st.markdown("**Blancos monitoreados**")
    st.markdown("🎯 @CCarrizosaC")
    st.markdown("🎯 @DiegoASantos")
    st.markdown("🎯 @ghitis")
    st.markdown("🎯 @julipalacioc")
    st.markdown("🎯 @ToroDeArena")

st.divider()

# ---------- Table ----------
st.subheader("Detalle de cuentas sincronizadas")
st.caption("Cuentas que responden a 2 o más blancos, ordenadas por nivel de coordinación.")

df = pd.DataFrame(attackers)
df = df.rename(columns={
    "u": "Cuenta", "tc": "Blancos", "tw": "Replies",
    "followers": "Followers", "following": "Following",
    "tweets": "Tweets", "age_days": "Edad (días)",
    "created": "Creada", "bio": "Bio", "av": "Foto",
    "targets": "Blancos atacados",
})
df["Cuenta"] = df["Cuenta"].apply(lambda x: f"@{x}")
df["Blancos atacados"] = df["Blancos atacados"].apply(lambda x: ", ".join(x))
df["Bio"] = df["Bio"].map({True: "✅", False: "❌"})
df["Foto"] = df["Foto"].map({True: "✅", False: "❌"})

st.dataframe(
    df[["Cuenta", "Blancos", "Blancos atacados", "Followers", "Following",
        "Tweets", "Edad (días)", "Creada", "Bio", "Foto"]],
    use_container_width=True,
    height=500,
)

st.divider()

# ---------- Methodology ----------
st.subheader("Metodología")
st.markdown(
    """
1. **Selección de blancos:** Se identificaron 5 cuentas públicas que han expresado críticas
   o apoyos a la candidata Paloma Valencia y que reciben avalanchas de respuestas negativas
   asociadas a la campaña de Abelardo De La Espriella.

2. **Recolección de datos:** Se recolectaron las replies más recientes a cada una de las
   5 cuentas blanco usando la API oficial de X.

3. **Detección de sincronización:** Se cruzaron las listas de cuentas que responden a cada
   blanco. Las cuentas que aparecen respondiendo a **2 o más blancos distintos** muestran
   un patrón de comportamiento coordinado.

4. **Grafo de co-ocurrencia:** Dos cuentas se conectan en el grafo si atacan a los mismos
   blancos. A mayor cantidad de blancos compartidos, más fuerte la evidencia de coordinación.

> **Nota:** Este análisis identifica patrones de comportamiento sincronizado. Que una cuenta
> responda a múltiples críticos no prueba que sea un bot, pero la probabilidad de que
> múltiples cuentas independientes coincidan en atacar exactamente a los mismos 4 de 5
> blancos es estadísticamente muy baja.
"""
)
