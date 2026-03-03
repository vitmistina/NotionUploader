"""Streamlit app that visualizes technology/project DAG definitions from ``inputs/``."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import streamlit as st
from pyvis.network import Network

from src.domain.dag import NodeType
from src.services.dag_loader import build_graph, load_dag_definitions


TECH_COLOR = "#0ea5e9"
PROJECT_COLOR = "#a855f7"


def _project_root() -> Path:
    """Return the repository root assuming this file lives under ``src/``."""

    return Path(__file__).resolve().parent.parent


def _build_network(graph: nx.DiGraph) -> Network:
    """Convert a NetworkX graph into a PyVis network with typed styling."""

    network = Network(height="720px", width="100%", directed=True)
    for node, attributes in graph.nodes(data=True):
        node_type: NodeType = attributes.get("node_type", NodeType.PROJECT)
        color = TECH_COLOR if node_type is NodeType.TECH else PROJECT_COLOR
        shape = "dot" if node_type is NodeType.TECH else "box"
        network.add_node(node, label=node, color=color, shape=shape)

    for source, target in graph.edges:
        network.add_edge(source, target, arrows="to")

    return network


def main() -> None:
    """Render the DAG in a Streamlit page."""

    st.set_page_config(page_title="Tech/Project DAG", layout="wide")
    st.title("Tech & Project DAG Visualizer")
    st.caption("Dependencies flow from technologies to projects.")

    inputs_dir = _project_root() / "inputs"
    if not inputs_dir.exists():
        st.error(f"No inputs directory found at {inputs_dir}.")
        return

    dag_definition = load_dag_definitions(inputs_dir)
    if not dag_definition.nodes:
        st.info("No DAG definitions discovered. Add JSON files under the inputs/ directory.")
        return

    graph = build_graph(dag_definition)
    pyvis_network = _build_network(graph)
    html = pyvis_network.generate_html(notebook=False)

    st.subheader("Interactive graph")
    st.components.v1.html(html, height=750, scrolling=True)

    st.subheader("Node summary")
    st.write(
        {
            "techs": len([node for node in graph.nodes(data=True) if node[1]["node_type"] is NodeType.TECH]),
            "projects": len(
                [node for node in graph.nodes(data=True) if node[1]["node_type"] is NodeType.PROJECT]
            ),
            "dependencies": graph.size(),
        }
    )


if __name__ == "__main__":
    main()
