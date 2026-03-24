"""Detección de comunidades usando Louvain."""

import logging

import networkx as nx
from networkx.algorithms.community import louvain_communities
from sqlmodel import Session

from bodegas.db.models import Account
from bodegas.db.session import get_engine

logger = logging.getLogger(__name__)


def detect_communities(G: nx.DiGraph, resolution: float = 1.0) -> dict[str, int]:
    """Detectar comunidades usando Louvain.

    Retorna dict de {node_id: community_id}.
    """
    if G.number_of_nodes() == 0:
        return {}

    # Louvain requiere grafo no dirigido
    G_undirected = G.to_undirected()

    communities = louvain_communities(
        G_undirected, weight="weight", resolution=resolution, seed=42
    )

    node_to_community = {}
    for community_id, members in enumerate(communities):
        for node in members:
            node_to_community[node] = community_id

    logger.info(f"Detectadas {len(communities)} comunidades")
    return node_to_community


def assign_communities_to_graph(G: nx.DiGraph, communities: dict[str, int]) -> None:
    """Asignar community_id como atributo de nodos."""
    for node_id, community_id in communities.items():
        if node_id in G.nodes():
            G.nodes[node_id]["community_id"] = community_id


def save_communities_to_db(communities: dict[str, int]) -> int:
    """Guardar community_id en la tabla accounts."""
    engine = get_engine()
    updated = 0
    with Session(engine) as session:
        for node_id, community_id in communities.items():
            account = session.get(Account, node_id)
            if account:
                account.community_id = community_id
                updated += 1
        session.commit()
    logger.info(f"Community ID asignado a {updated} cuentas")
    return updated


def get_community_summary(
    G: nx.DiGraph, communities: dict[str, int], metrics: dict[str, dict] | None = None
) -> list[dict]:
    """Generar resumen por comunidad."""
    community_nodes: dict[int, list[str]] = {}
    for node_id, comm_id in communities.items():
        community_nodes.setdefault(comm_id, []).append(node_id)

    summaries = []
    for comm_id, nodes in sorted(community_nodes.items()):
        members = []
        for n in nodes:
            if n in G.nodes():
                members.append({
                    "id": n,
                    "username": G.nodes[n].get("username", ""),
                    "pagerank": metrics.get(n, {}).get("pagerank", 0) if metrics else 0,
                })

        # Ordenar por pagerank
        members.sort(key=lambda x: x["pagerank"], reverse=True)

        avg_bot_score = 0.0
        scores = [
            G.nodes[n].get("bot_score")
            for n in nodes
            if n in G.nodes() and G.nodes[n].get("bot_score") is not None
        ]
        if scores:
            avg_bot_score = sum(scores) / len(scores)

        summaries.append({
            "community_id": comm_id,
            "size": len(nodes),
            "top_members": members[:5],
            "avg_bot_score": round(avg_bot_score, 3),
        })

    summaries.sort(key=lambda x: x["size"], reverse=True)
    return summaries
