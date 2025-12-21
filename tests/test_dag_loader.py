"""Tests for DAG parsing and validation helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.dag_loader import build_graph, load_dag_definitions


def _write(path: Path, payload: str) -> None:
    path.write_text(payload, encoding="utf-8")


def test_load_dag_definitions_builds_graph(tmp_path: Path) -> None:
    """Projects should render with tech and project dependencies."""

    _write(
        tmp_path / "dag.json",
        """
        {
          "techs": ["Python"],
          "projects": [
            {
              "name": "Pipeline",
              "tech_dependencies": ["Python"],
              "project_dependencies": ["Shared Library"]
            }
          ]
        }
        """,
    )
    _write(
        tmp_path / "library.json",
        """
        {
          "projects": [
            {
              "name": "Shared Library",
              "tech_dependencies": ["Python"]
            }
          ]
        }
        """,
    )

    dag_definition = load_dag_definitions(tmp_path)
    graph = build_graph(dag_definition)

    assert set(graph.nodes()) == {"Python", "Pipeline", "Shared Library"}
    assert ("Python", "Pipeline") in graph.edges
    assert ("Shared Library", "Pipeline") in graph.edges


def test_build_graph_rejects_cycles(tmp_path: Path) -> None:
    """Cycles across project dependencies should fail fast."""

    _write(
        tmp_path / "cycle.json",
        """
        {
          "projects": [
            {"name": "A", "project_dependencies": ["B"]},
            {"name": "B", "project_dependencies": ["A"]}
          ]
        }
        """,
    )

    dag_definition = load_dag_definitions(tmp_path)
    with pytest.raises(ValueError):
        build_graph(dag_definition)
