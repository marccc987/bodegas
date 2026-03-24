"""Cálculo de métricas de grafos por nodo."""

import logging

import networkx as nx
from sqlmodel import Session

from bodegas.db.models import Account
from bodegas.db.session import get_engine

logger = logging.getLogger(__name__)


def compute_metrics(G: nx.DiGraph) -> dict[str, dict]:
    """Calcular métricas de centralidad por nodo.

    Retorna dict de {node_id: {metric_name: value}}.
    """
    if G.number_of_nodes() == 0:
        return {}

    logger.info(f"Calculando métricas para {G.number_of_nodes()} nodos...")

    # Convertir a no-dirigido para clustering
    G_undirected = G.to_undirected()

    metrics = {}

    in_degree = dict(G.in_degree())
    out_degree = dict(G.out_degree())
    pagerank = nx.pagerank(G, weight="weight")
    betweenness = nx.betweenness_centrality(G, weight="weight")
    clustering = nx.clustering(G_undirected)

    # Closeness solo si el grafo no es muy grande (es O(n²))
    if G.number_of_nodes() <= 5000:
        closeness = nx.closeness_centrality(G)
    else:
        closeness = {n: 0.0 for n in G.nodes()}
        logger.info("Grafo grande: omitiendo closeness centrality")

    for node in G.nodes():
        metrics[node] = {
            "in_degree": in_degree.get(node, 0),
            "out_degree": out_degree.get(node, 0),
            "pagerank": pagerank.get(node, 0.0),
            "betweenness": betweenness.get(node, 0.0),
            "closeness": closeness.get(node, 0.0),
            "clustering": clustering.get(node, 0.0),
        }

    logger.info("Métricas calculadas")
    return metrics


def save_metrics_to_graph(G: nx.DiGraph, metrics: dict[str, dict]) -> None:
    """Guardar métricas como atributos de nodos en el grafo."""
    for node_id, node_metrics in metrics.items():
        if node_id in G.nodes():
            for metric_name, value in node_metrics.items():
                G.nodes[node_id][metric_name] = value


def get_top_nodes(
    metrics: dict[str, dict],
    metric_name: str,
    n: int = 10,
    G: nx.DiGraph | None = None,
) -> list[dict]:
    """Obtener los top-N nodos por una métrica.

    Si se provee el grafo, incluye el username.
    """
    sorted_nodes = sorted(
        metrics.items(), key=lambda x: x[1].get(metric_name, 0), reverse=True
    )[:n]

    results = []
    for node_id, node_metrics in sorted_nodes:
        entry = {"id": node_id, metric_name: node_metrics.get(metric_name, 0)}
        if G and node_id in G.nodes():
            entry["username"] = G.nodes[node_id].get("username", "")
        results.append(entry)

    return results
