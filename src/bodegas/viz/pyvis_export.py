"""Exportar grafo como HTML interactivo con pyvis, con fotos de perfil."""

import logging
from pathlib import Path

import networkx as nx
from pyvis.network import Network

logger = logging.getLogger(__name__)

LABEL_COLORS = {
    "bot": "#e74c3c",        # rojo
    "suspicious": "#f39c12",  # amarillo/naranja
    "human": "#2ecc71",       # verde
    "": "#95a5a6",            # gris (sin clasificar)
}


def export_interactive_graph(
    G: nx.DiGraph,
    output_path: str = "data/exports/network.html",
    height: str = "900px",
    width: str = "100%",
    max_nodes: int = 500,
) -> str:
    """Generar grafo HTML interactivo con pyvis y fotos de perfil."""
    # Si el grafo es muy grande, filtrar por PageRank
    if G.number_of_nodes() > max_nodes:
        pagerank = nx.pagerank(G, weight="weight")
        top_nodes = sorted(pagerank, key=pagerank.get, reverse=True)[:max_nodes]
        G = G.subgraph(top_nodes).copy()
        logger.info(f"Grafo filtrado a top {max_nodes} nodos por PageRank")

    net = Network(
        height=height,
        width=width,
        directed=True,
        notebook=False,
        bgcolor="#0f0f1a",
        font_color="#e0e0e0",
    )

    net.set_options("""
    {
        "physics": {
            "forceAtlas2Based": {
                "gravitationalConstant": -80,
                "centralGravity": 0.008,
                "springLength": 180,
                "springConstant": 0.06,
                "damping": 0.5
            },
            "solver": "forceAtlas2Based",
            "stabilization": {"iterations": 200}
        },
        "interaction": {
            "hover": true,
            "tooltipDelay": 50,
            "navigationButtons": true,
            "zoomView": true
        },
        "edges": {
            "smooth": {"type": "continuous"}
        }
    }
    """)

    pagerank = nx.pagerank(G, weight="weight")
    max_pr = max(pagerank.values()) if pagerank else 1

    for node_id in G.nodes():
        attrs = G.nodes[node_id]
        username = attrs.get("username", node_id)
        label = attrs.get("bot_label", "")
        score = attrs.get("bot_score")
        community = attrs.get("community_id", "N/A")
        followers = attrs.get("followers_count", 0)
        following = attrs.get("following_count", 0)
        avatar_url = attrs.get("avatar_url", "")
        tweet_count = attrs.get("tweet_count", 0)

        color = LABEL_COLORS.get(label, LABEL_COLORS[""])
        pr_val = pagerank.get(node_id, 0)
        size = 15 + (pr_val / max_pr) * 50

        score_str = f"{score:.3f}" if score is not None else "N/A"
        title = (
            f"<div style='font-family:Arial;padding:8px;'>"
            f"<b style='font-size:14px;'>@{username}</b><br>"
            f"<span style='color:{color};font-weight:bold;'>{label.upper() or 'SIN CLASIFICAR'}</span> "
            f"(score: {score_str})<br>"
            f"<hr style='margin:4px 0;border-color:#444;'>"
            f"Comunidad: {community}<br>"
            f"Seguidores: {followers:,}<br>"
            f"Siguiendo: {following:,}<br>"
            f"Tweets: {tweet_count:,}<br>"
            f"PageRank: {pr_val:.6f}"
            f"</div>"
        )

        # Use avatar as node image if available
        if avatar_url and "default_profile" not in avatar_url:
            net.add_node(
                node_id,
                label=f"@{username}",
                title=title,
                image=avatar_url,
                shape="circularImage",
                size=size,
                borderWidth=3,
                borderWidthSelected=5,
                color={
                    "border": color,
                    "highlight": {"border": color},
                },
                font={"size": 10, "color": "#e0e0e0"},
            )
        else:
            net.add_node(
                node_id,
                label=f"@{username}",
                title=title,
                color=color,
                size=size,
                shape="dot",
                borderWidth=2,
                borderWidthSelected=4,
                font={"size": 10, "color": "#e0e0e0"},
            )

    # Aristas
    edge_type_colors = {
        "mention": "#3498db55",
        "retweet": "#e74c3c55",
        "follows": "#2ecc7155",
        "reply": "#f39c1255",
        "quote": "#9b59b655",
    }

    for u, v, data in G.edges(data=True):
        weight = data.get("weight", 1)
        types = data.get("types", set())
        if isinstance(types, set):
            type_list = list(types)
        elif isinstance(types, str):
            type_list = types.split(",")
        else:
            type_list = ["unknown"]

        primary_type = type_list[0] if type_list else "unknown"
        edge_color = edge_type_colors.get(primary_type, "#ffffff33")
        type_str = ", ".join(type_list)

        net.add_edge(
            u, v,
            width=min(weight * 0.8, 6),
            title=f"Tipo: {type_str} | Peso: {weight}",
            color={"color": edge_color, "highlight": "#ffffff88"},
            arrows={"to": {"enabled": True, "scaleFactor": 0.4}},
            smooth={"type": "continuous"},
        )

    # Guardar
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    net.save_graph(str(output))

    # Inject custom legend HTML
    _inject_legend(str(output))

    logger.info(
        f"Grafo exportado: {G.number_of_nodes()} nodos, "
        f"{G.number_of_edges()} aristas → {output}"
    )
    return str(output)


def _inject_legend(html_path: str):
    """Inyectar leyenda HTML en el grafo."""
    legend_html = """
    <div id="legend" style="
        position:fixed; top:15px; right:15px; background:rgba(15,15,26,0.92);
        border:1px solid #333; border-radius:10px; padding:16px 20px;
        font-family:Arial,sans-serif; color:#e0e0e0; font-size:13px;
        z-index:9999; box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    ">
        <div style="font-weight:bold; font-size:15px; margin-bottom:10px; color:#fff;">
            Bodegas - Red #YoVotoPorAbelardo
        </div>
        <div style="margin-bottom:6px;">
            <span style="display:inline-block;width:14px;height:14px;background:#e74c3c;border-radius:50%;vertical-align:middle;"></span>
            <span style="vertical-align:middle;"> Bot</span>
        </div>
        <div style="margin-bottom:6px;">
            <span style="display:inline-block;width:14px;height:14px;background:#f39c12;border-radius:50%;vertical-align:middle;"></span>
            <span style="vertical-align:middle;"> Sospechosa</span>
        </div>
        <div style="margin-bottom:6px;">
            <span style="display:inline-block;width:14px;height:14px;background:#2ecc71;border-radius:50%;vertical-align:middle;"></span>
            <span style="vertical-align:middle;"> Humana</span>
        </div>
        <div style="margin-bottom:6px;">
            <span style="display:inline-block;width:14px;height:14px;background:#95a5a6;border-radius:50%;vertical-align:middle;"></span>
            <span style="vertical-align:middle;"> Sin clasificar</span>
        </div>
        <hr style="border-color:#444; margin:8px 0;">
        <div style="font-size:11px; color:#999;">
            Aristas: <span style="color:#3498db;">menciones</span> |
            <span style="color:#e74c3c;">retweets</span> |
            <span style="color:#2ecc71;">follows</span><br>
            Nodo grande = mayor PageRank<br>
            Foto = avatar de X
        </div>
    </div>
    """
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    content = content.replace("</body>", legend_html + "\n</body>")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(content)
