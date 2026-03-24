"""Entry point for Streamlit Cloud."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from bodegas.viz.dashboard import main

main()
