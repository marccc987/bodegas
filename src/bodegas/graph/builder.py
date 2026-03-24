"""Construcción del grafo de relaciones desde la base de datos."""

import logging

import networkx as nx
from sqlmodel import Session, select

from bodegas.db.models import Account, Relationship
from bodegas.db.session import get_engine

logger = logging.getLogger(__name__)


def build_graph(
    relationship_types: list[str] | None = None,
    min_weight: int = 1,
) -> nx.DiGraph:
    """Construir grafo dirigido desde la tabla relationships.

    Args:
        relationship_types: Filtrar por tipos (None = todos).
        min_weight: Peso mínimo de arista para incluir.
    """
    engine = get_engine()
    G = nx.DiGraph()

    with Session(engine) as session:
        # Cargar cuentas como nodos
        accounts = session.exec(select(Account)).all()
        for account in accounts:
            G.add_node(
                account.id,
                username=account.username,
                display_name=account.display_name,
                followers_count=account.followers_count,
                following_count=account.following_count,
                tweet_count=account.tweet_count,
                created_at=str(account.created_at) if account.created_at else "",
                is_verified=account.is_verified,
                has_avatar=account.has_avatar,
                has_bio=account.has_bio,
                avatar_url=account.avatar_url or "",
                bot_score=account.bot_score,
                bot_label=account.bot_label or "",
                community_id=account.community_id,
                is_seed=account.is_seed,
            )

        # Cargar relaciones como aristas
        stmt = select(Relationship)
        if relationship_types:
            stmt = stmt.where(Relationship.relationship_type.in_(relationship_types))
        if min_weight > 1:
            stmt = stmt.where(Relationship.weight >= min_weight)

        relationships = session.exec(stmt).all()
        for rel in relationships:
            if G.has_edge(rel.source_id, rel.target_id):
                # Si ya existe arista, combinar tipos
                edge = G[rel.source_id][rel.target_id]
                types = edge.get("types", set())
                types.add(rel.relationship_type)
                edge["types"] = types
                edge["weight"] = edge.get("weight", 0) + rel.weight
            else:
                G.add_edge(
                    rel.source_id,
                    rel.target_id,
                    weight=rel.weight,
                    types={rel.relationship_type},
                )

    # Remover nodos aislados (sin aristas)
    isolated = list(nx.isolates(G))
    G.remove_nodes_from(isolated)

    logger.info(
        f"Grafo construido: {G.number_of_nodes()} nodos, "
        f"{G.number_of_edges()} aristas ({len(isolated)} nodos aislados removidos)"
    )
    return G
