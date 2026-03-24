"""Dashboard Streamlit para explorar la red de bots."""

import streamlit as st
import pandas as pd
from sqlmodel import Session, select, func

from bodegas.db.models import Account, Relationship, Tweet
from bodegas.db.session import get_engine, create_tables


def get_stats() -> dict:
    engine = get_engine()
    with Session(engine) as session:
        total_accounts = session.exec(
            select(func.count()).select_from(Account)
        ).one()
        total_relationships = session.exec(
            select(func.count()).select_from(Relationship)
        ).one()
        total_tweets = session.exec(
            select(func.count()).select_from(Tweet)
        ).one()
        bots = session.exec(
            select(func.count()).select_from(Account).where(Account.bot_label == "bot")
        ).one()
        suspicious = session.exec(
            select(func.count()).select_from(Account).where(Account.bot_label == "suspicious")
        ).one()
        humans = session.exec(
            select(func.count()).select_from(Account).where(Account.bot_label == "human")
        ).one()

    return {
        "total_accounts": total_accounts,
        "total_relationships": total_relationships,
        "total_tweets": total_tweets,
        "bots": bots,
        "suspicious": suspicious,
        "humans": humans,
    }


def get_accounts_df() -> pd.DataFrame:
    engine = get_engine()
    with Session(engine) as session:
        accounts = session.exec(select(Account)).all()
    return pd.DataFrame([a.model_dump() for a in accounts])


def page_overview():
    st.header("Vista General")
    stats = get_stats()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Cuentas", stats["total_accounts"])
    col2.metric("Relaciones", stats["total_relationships"])
    col3.metric("Tweets", stats["total_tweets"])
    col4.metric("Bots detectados", stats["bots"])

    st.subheader("Distribución de clasificaciones")
    labels = {"bot": stats["bots"], "suspicious": stats["suspicious"], "human": stats["humans"]}
    if any(labels.values()):
        chart_df = pd.DataFrame(
            {"Clasificación": list(labels.keys()), "Cantidad": list(labels.values())}
        )
        st.bar_chart(chart_df.set_index("Clasificación"))
    else:
        st.info("Ejecuta 'bodegas detect' primero para clasificar cuentas.")


def page_accounts():
    st.header("Explorador de Cuentas")
    df = get_accounts_df()

    if df.empty:
        st.warning("No hay cuentas cargadas. Ejecuta 'bodegas collect' o 'bodegas import'.")
        return

    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        label_filter = st.multiselect(
            "Filtrar por clasificación",
            options=["bot", "suspicious", "human", None],
            format_func=lambda x: x if x else "Sin clasificar",
        )
    with col2:
        search = st.text_input("Buscar username")

    filtered = df
    if label_filter:
        filtered = filtered[filtered["bot_label"].isin(label_filter)]
    if search:
        filtered = filtered[filtered["username"].str.contains(search, case=False, na=False)]

    # Ordenar por bot_score descendente
    if "bot_score" in filtered.columns:
        filtered = filtered.sort_values("bot_score", ascending=False)

    # Mostrar tabla
    display_cols = [
        "username", "display_name", "bot_label", "bot_score",
        "followers_count", "following_count", "tweet_count",
        "community_id", "is_seed",
    ]
    available = [c for c in display_cols if c in filtered.columns]
    st.dataframe(filtered[available], use_container_width=True, height=500)

    st.download_button(
        "Descargar CSV",
        data=filtered[available].to_csv(index=False),
        file_name="cuentas_bodegas.csv",
        mime="text/csv",
    )


def page_account_detail():
    st.header("Detalle de Cuenta")
    df = get_accounts_df()

    if df.empty:
        st.warning("No hay cuentas cargadas.")
        return

    usernames = sorted(df["username"].tolist())
    selected = st.selectbox("Seleccionar cuenta", usernames)

    if selected:
        account = df[df["username"] == selected].iloc[0]

        col1, col2, col3 = st.columns(3)
        col1.metric("Bot Score", f"{account.get('bot_score', 0):.3f}")
        col2.metric("Clasificación", account.get("bot_label", "N/A"))
        col3.metric("Comunidad", account.get("community_id", "N/A"))

        st.subheader("Perfil")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Username**: @{account['username']}")
            st.write(f"**Nombre**: {account.get('display_name', '')}")
            st.write(f"**Bio**: {account.get('bio', '')}")
            st.write(f"**Ubicación**: {account.get('location', '')}")
        with col2:
            st.write(f"**Seguidores**: {account.get('followers_count', 0):,}")
            st.write(f"**Siguiendo**: {account.get('following_count', 0):,}")
            st.write(f"**Tweets**: {account.get('tweet_count', 0):,}")
            st.write(f"**Cuenta creada**: {account.get('created_at', 'N/A')}")
            st.write(f"**Verificada**: {'Sí' if account.get('is_verified') else 'No'}")
            st.write(f"**Avatar**: {'Sí' if account.get('has_avatar') else 'No'}")
            st.write(f"**Semilla**: {'Sí' if account.get('is_seed') else 'No'}")


def page_communities():
    st.header("Comunidades")
    df = get_accounts_df()

    if df.empty or "community_id" not in df.columns or df["community_id"].isna().all():
        st.warning("Ejecuta 'bodegas analyze' primero para detectar comunidades.")
        return

    communities = df.groupby("community_id").agg(
        miembros=("username", "count"),
        bot_score_promedio=("bot_score", "mean"),
        bots=("bot_label", lambda x: (x == "bot").sum()),
        sospechosos=("bot_label", lambda x: (x == "suspicious").sum()),
    ).reset_index()

    communities = communities.sort_values("miembros", ascending=False)
    st.dataframe(communities, use_container_width=True)

    # Detalle de comunidad seleccionada
    comm_id = st.selectbox(
        "Ver miembros de comunidad",
        communities["community_id"].tolist(),
    )
    if comm_id is not None:
        members = df[df["community_id"] == comm_id].sort_values("bot_score", ascending=False)
        display_cols = ["username", "bot_label", "bot_score", "followers_count", "following_count"]
        available = [c for c in display_cols if c in members.columns]
        st.dataframe(members[available], use_container_width=True)


def page_network():
    st.header("Grafo de Red")
    import os
    graph_path = "data/exports/network.html"
    if os.path.exists(graph_path):
        with open(graph_path, "r", encoding="utf-8") as f:
            html = f.read()
        st.components.v1.html(html, height=700, scrolling=True)
    else:
        st.warning(
            "No se ha generado el grafo. Ejecuta 'bodegas viz' para generarlo."
        )


def main():
    st.set_page_config(
        page_title="Bodegas - Detector de Bots",
        page_icon="🔍",
        layout="wide",
    )
    st.title("Bodegas - Análisis de Red y Detección de Bots")

    create_tables()

    pages = {
        "Vista General": page_overview,
        "Cuentas": page_accounts,
        "Detalle de Cuenta": page_account_detail,
        "Comunidades": page_communities,
        "Grafo de Red": page_network,
    }

    page = st.sidebar.radio("Navegación", list(pages.keys()))
    pages[page]()


if __name__ == "__main__":
    main()
