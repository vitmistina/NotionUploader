"""Lightweight structures for modeling project/tech directed acyclic graphs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class NodeType(str, Enum):
    """Enumeration of supported DAG node types."""

    TECH = "tech"
    PROJECT = "project"


@dataclass(frozen=True, slots=True)
class DagNode:
    """A node in the project/technology dependency DAG."""

    name: str
    node_type: NodeType


@dataclass(slots=True)
class DagDefinition:
    """Collection of DAG nodes and edges for validation and visualization."""

    nodes: dict[tuple[str, NodeType], DagNode] = field(default_factory=dict)
    edges: set[tuple[DagNode, DagNode]] = field(default_factory=set)

    def ensure_node(self, name: str, node_type: NodeType) -> DagNode:
        """Register a node if missing and return the canonical instance."""

        key = (name, node_type)
        if key not in self.nodes:
            self.nodes[key] = DagNode(name=name, node_type=node_type)
        return self.nodes[key]

    def add_edges(self, dependencies: Iterable[tuple[DagNode, DagNode]]) -> None:
        """Add dependency edges between existing nodes."""

        self.edges.update(dependencies)
