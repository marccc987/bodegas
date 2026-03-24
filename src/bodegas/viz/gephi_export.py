"""Exportar grafo en formato GEXF para Gephi."""

import logging
from pathlib import Path

import networkx as nx

logger = logging.getLogger(__name__)


def export_gexf(
    G: nx.DiGraph,
    output_path: str = "data/exports/network.gexf",
) -> str:
    """Exportar grafo a GEXF con todos los atributos."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Convertir sets a strings para compatibilidad GEXF
    G_export = G.copy()
    for u, v, data in G_export.edges(data=True):
        if "types" in data and isinstance(data["types"], set):
            data["types"] = ",".join(data["types"])

    # Asegurar que todos los atributos de nodo son serializables
    for node_id in G_export.nodes():
        attrs = G_export.nodes[node_id]
        for key, value in list(attrs.items()):
            if value is None:
                attrs[key] = ""
            elif isinstance(value, (set, list)):
                attrs[key] = str(value)

    nx.write_gexf(G_export, str(output))
    logger.info(f"GEXF exportado: {output}")
    return str(output)
