"""Parse DAG definitions from disk and build validated graph structures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping

import networkx as nx

from src.domain.dag import DagDefinition, DagNode, NodeType


def load_dag_definitions(inputs_dir: Path) -> DagDefinition:
    """Read every JSON file in ``inputs_dir`` and return a consolidated DAG definition."""

    dag_definition = DagDefinition()
    json_files = sorted(inputs_dir.glob("*.json"))
    for json_file in json_files:
        dag_definition = _merge_definition(dag_definition, json_file)
    return dag_definition


def _merge_definition(dag_definition: DagDefinition, json_file: Path) -> DagDefinition:
    """Merge a single JSON DAG definition file into the aggregate definition."""

    if not json_file.is_file():
        return dag_definition

    with json_file.open("r", encoding="utf-8") as stream:
        payload: Mapping[str, object] = json.load(stream)

    for tech_name in _normalize_names(payload.get("techs", []), NodeType.TECH):
        dag_definition.ensure_node(tech_name, NodeType.TECH)

    dependencies: list[tuple[DagNode, DagNode]] = []
    for project in payload.get("projects", []):
        project_name = _extract_name(project)
        project_node = dag_definition.ensure_node(project_name, NodeType.PROJECT)

        tech_dependencies = _normalize_names(
            _extract_list(project, "tech_dependencies"), NodeType.TECH
        )
        for tech_name in tech_dependencies:
            tech_node = dag_definition.ensure_node(tech_name, NodeType.TECH)
            dependencies.append((tech_node, project_node))

        project_dependencies = _normalize_names(
            _extract_list(project, "project_dependencies"), NodeType.PROJECT
        )
        for dependency_name in project_dependencies:
            dependency_node = dag_definition.ensure_node(dependency_name, NodeType.PROJECT)
            dependencies.append((dependency_node, project_node))

    dag_definition.add_edges(dependencies)
    return dag_definition


def _normalize_names(values: Iterable[object], node_type: NodeType) -> list[str]:
    """Extract node names from heterogeneous iterable values."""

    normalized: list[str] = []
    for value in values:
        normalized.append(_extract_name(value, node_type))
    return normalized


def _extract_name(value: object, expected_type: NodeType | None = None) -> str:
    """Return the ``name`` string from supported value shapes."""

    if isinstance(value, str):
        return value

    if isinstance(value, Mapping):
        name = value.get("name")
        if isinstance(name, str):
            return name

    type_hint = f" for {expected_type.value}" if expected_type else ""
    raise ValueError(f"Unable to extract name{type_hint} from value: {value!r}")


def _extract_list(obj: object, key: str) -> Iterable[object]:
    """Return a list-like attribute from a mapping or an empty list when missing."""

    if not isinstance(obj, Mapping):
        raise ValueError("Project definitions must be mapping objects.")

    value = obj.get(key, [])
    if value is None:
        return []
    if isinstance(value, list):
        return value

    raise ValueError(f"Expected list for '{key}' but received {type(value)}")


def build_graph(dag_definition: DagDefinition) -> nx.DiGraph:
    """Create a validated NetworkX DAG from a ``DagDefinition`` instance."""

    graph = nx.DiGraph()
    for node in dag_definition.nodes.values():
        graph.add_node(node.name, node_type=node.node_type)

    for source, target in dag_definition.edges:
        graph.add_edge(source.name, target.name)

    if not nx.is_directed_acyclic_graph(graph):
        raise ValueError("The supplied definitions include a cyclic dependency.")

    return graph
