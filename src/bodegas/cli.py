"""CLI para Bodegas - Detección de bots en X."""

import logging
import sys

import typer
from rich.console import Console
from rich.table import Table

from bodegas.db.session import create_tables

app = typer.Typer(help="Bodegas - Grafo de relacionamiento y detección de bots en X")
console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


@app.command()
def init():
    """Inicializar la base de datos."""
    create_tables()
    console.print("[green]Base de datos inicializada correctamente.[/green]")


@app.command()
def collect(
    seeds: str = typer.Option("data/seeds.json", help="Ruta al archivo seeds.json"),
):
    """Recolectar perfiles de X API. Si la API falla, crea cuentas semilla básicas."""
    create_tables()
    from bodegas.collector.tasks import collect_profiles, seed_accounts

    try:
        result = collect_profiles(seeds)
        console.print(
            f"[green]Recolectados {result['found']} perfiles "
            f"de {result['total']} semillas via API.[/green]"
        )
    except Exception as e:
        console.print(f"[yellow]API no disponible: {e}[/yellow]")
        console.print("[blue]Creando cuentas semilla sin API...[/blue]")
        result = seed_accounts(seeds)
        console.print(
            f"[green]{result['saved']} cuentas semilla creadas.[/green]\n"
            "[yellow]Nota: sin datos de perfil (seguidores, bio, etc). "
            "Agrega datos manuales via CSV para un mejor análisis.[/yellow]"
        )


@app.command(name="import")
def import_data(
    path: str = typer.Option("data/imports", help="Directorio con CSVs a importar"),
):
    """Importar datos manuales desde CSVs."""
    create_tables()
    from bodegas.collector.tasks import import_manual_data

    results = import_manual_data(path)

    for category, files in results.items():
        for filename, stats in files.items():
            imported = stats.get("imported", 0)
            skipped = stats.get("skipped", 0)
            errors = stats.get("errors", [])
            console.print(
                f"[green]{filename}[/green]: {imported} importados, {skipped} omitidos"
            )
            for err in errors[:5]:
                console.print(f"  [yellow]{err}[/yellow]")


@app.command()
def resolve():
    """Resolver cuentas placeholder (de CSVs) via X API."""
    create_tables()
    from bodegas.collector.tasks import resolve_placeholders

    resolved = resolve_placeholders()
    console.print(f"[green]{resolved} cuentas resueltas via API.[/green]")


@app.command()
def analyze():
    """Construir grafo, calcular métricas y detectar comunidades."""
    create_tables()
    from bodegas.graph.builder import build_graph
    from bodegas.graph.metrics import compute_metrics, save_metrics_to_graph
    from bodegas.graph.communities import (
        detect_communities,
        assign_communities_to_graph,
        save_communities_to_db,
        get_community_summary,
    )

    console.print("[blue]Construyendo grafo...[/blue]")
    G = build_graph()

    if G.number_of_nodes() == 0:
        console.print("[yellow]No hay datos suficientes para construir el grafo.[/yellow]")
        raise typer.Exit(1)

    console.print(f"Grafo: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas")

    console.print("[blue]Calculando métricas...[/blue]")
    metrics = compute_metrics(G)
    save_metrics_to_graph(G, metrics)

    console.print("[blue]Detectando comunidades...[/blue]")
    communities = detect_communities(G)
    assign_communities_to_graph(G, communities)
    save_communities_to_db(communities)

    summaries = get_community_summary(G, communities, metrics)

    table = Table(title="Comunidades detectadas")
    table.add_column("ID", style="cyan")
    table.add_column("Miembros", justify="right")
    table.add_column("Top cuenta", style="green")
    table.add_column("Bot score prom.", justify="right")

    for s in summaries[:15]:
        top = s["top_members"][0]["username"] if s["top_members"] else "N/A"
        table.add_row(
            str(s["community_id"]),
            str(s["size"]),
            f"@{top}",
            f"{s['avg_bot_score']:.3f}",
        )

    console.print(table)


@app.command()
def detect(
    method: str = typer.Option("heuristic", help="Método: heuristic, ml, both"),
):
    """Ejecutar detección de bots."""
    create_tables()
    from bodegas.detection.heuristics import run_heuristic_detection

    if method in ("heuristic", "both"):
        console.print("[blue]Ejecutando detección heurística...[/blue]")
        results = run_heuristic_detection()

        table = Table(title="Resultados de detección heurística")
        table.add_column("Categoría", style="cyan")
        table.add_column("Cantidad", justify="right")
        table.add_row("[red]Bots[/red]", str(results["bot"]))
        table.add_row("[yellow]Sospechosas[/yellow]", str(results["suspicious"]))
        table.add_row("[green]Humanas[/green]", str(results["human"]))
        table.add_row("Total", str(results["total"]))
        console.print(table)

    if method in ("ml", "both"):
        console.print("[blue]Ejecutando detección ML...[/blue]")
        from bodegas.detection.ml_model import build_feature_matrix, train_model, predict, save_ml_predictions

        try:
            df = build_feature_matrix()
            model_result = train_model(df)
            console.print(
                f"CV Accuracy: {model_result['cv_accuracy']:.3f} "
                f"(+/- {model_result['cv_std']:.3f})"
            )
            console.print("Top features:")
            for name, importance in model_result["top_features"][:5]:
                console.print(f"  {name}: {importance:.4f}")

            df = predict(df, model_result)
            save_ml_predictions(df)
            console.print("[green]Predicciones ML guardadas.[/green]")
        except ValueError as e:
            console.print(f"[yellow]{e}[/yellow]")


@app.command()
def viz(
    output: str = typer.Option("data/exports/network.html", help="Ruta del HTML de salida"),
    max_nodes: int = typer.Option(500, help="Máximo de nodos a mostrar"),
):
    """Generar grafo HTML interactivo."""
    create_tables()
    from bodegas.graph.builder import build_graph
    from bodegas.graph.metrics import compute_metrics, save_metrics_to_graph
    from bodegas.graph.communities import detect_communities, assign_communities_to_graph
    from bodegas.viz.pyvis_export import export_interactive_graph

    G = build_graph()
    if G.number_of_nodes() == 0:
        console.print("[yellow]No hay datos para visualizar.[/yellow]")
        raise typer.Exit(1)

    metrics = compute_metrics(G)
    save_metrics_to_graph(G, metrics)
    communities = detect_communities(G)
    assign_communities_to_graph(G, communities)

    path = export_interactive_graph(G, output, max_nodes=max_nodes)
    console.print(f"[green]Grafo exportado: {path}[/green]")
    console.print(f"Abre el archivo en tu navegador para explorarlo.")


@app.command()
def export(
    format: str = typer.Option("gexf", help="Formato: gexf, csv, json"),
    output: str = typer.Option("data/exports/", help="Directorio de salida"),
):
    """Exportar datos en distintos formatos."""
    create_tables()
    from pathlib import Path
    import json as json_mod

    outdir = Path(output)
    outdir.mkdir(parents=True, exist_ok=True)

    if format == "gexf":
        from bodegas.graph.builder import build_graph
        from bodegas.viz.gephi_export import export_gexf
        G = build_graph()
        path = export_gexf(G, str(outdir / "network.gexf"))
        console.print(f"[green]Exportado: {path}[/green]")

    elif format == "csv":
        from sqlmodel import Session, select
        from bodegas.db.models import Account
        import pandas as pd

        engine = create_tables()
        with Session(engine) as session:
            accounts = session.exec(select(Account)).all()
        df = pd.DataFrame([a.model_dump() for a in accounts])
        csv_path = str(outdir / "accounts.csv")
        df.to_csv(csv_path, index=False)
        console.print(f"[green]Exportado: {csv_path}[/green]")

    elif format == "json":
        from sqlmodel import Session, select
        from bodegas.db.models import Account

        engine = create_tables()
        with Session(engine) as session:
            accounts = session.exec(select(Account)).all()
        data = [a.model_dump() for a in accounts]
        # Serializar datetimes
        for d in data:
            for k, v in d.items():
                if hasattr(v, "isoformat"):
                    d[k] = v.isoformat()
        json_path = str(outdir / "accounts.json")
        with open(json_path, "w") as f:
            json_mod.dump(data, f, indent=2, ensure_ascii=False)
        console.print(f"[green]Exportado: {json_path}[/green]")


@app.command()
def dashboard():
    """Lanzar dashboard Streamlit."""
    import subprocess
    dashboard_path = str(
        Path(__file__).parent / "viz" / "dashboard.py"
    )
    console.print("[blue]Lanzando dashboard Streamlit...[/blue]")
    subprocess.run([sys.executable, "-m", "streamlit", "run", dashboard_path])


from pathlib import Path

if __name__ == "__main__":
    app()
