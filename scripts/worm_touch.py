"""Bounded structural-relay surrogate for evoked anterior-touch locomotion."""

from __future__ import annotations


MAX_RELAY_HOPS = 4
EDGE_ATTENUATION = 0.5
MOTOR_READOUT_GAIN = 0.5


def validate_touch_event(event) -> dict:
    if not isinstance(event, dict) or set(event) != {"kind"} or event["kind"] != "anterior_touch":
        raise ValueError("Only the documented anterior_touch stimulus is supported")
    return event.copy()


def _command_routes(activation: dict[str, float], parents: dict[str, str | None], edges: list[dict], command_prefix: str, motor_prefixes: tuple[str, ...]) -> list[dict]:
    routes = []
    for edge in edges:
        command = edge["source"]
        motor = edge["target"]
        if (
            edge["kind"] != "chemical"
            or not command.startswith(command_prefix)
            or not motor.startswith(motor_prefixes)
            or command not in activation
        ):
            continue
        path = [command]
        while parents.get(path[-1]) is not None:
            path.append(parents[path[-1]])
        path.reverse()
        path.append(motor)
        routes.append({
            "cells": path,
            "command_cell": command,
            "motor_cell": motor,
            "activation_score": activation[command] * MOTOR_READOUT_GAIN,
        })
    return sorted(routes, key=lambda route: (-route["activation_score"], route["cells"]))


def relay_from_cells(connectome: dict, sensory_cells: list[str]) -> dict:
    nodes = connectome["nodes"]
    node_set = set(nodes)
    if (
        not isinstance(sensory_cells, list)
        or any(not isinstance(cell, str) or cell not in node_set for cell in sensory_cells)
        or len(set(sensory_cells)) != len(sensory_cells)
    ):
        raise ValueError("Relay input cells must be unique labels present in the connectome")

    activation = {cell: 1.0 for cell in sensory_cells}
    hops = {cell: 0 for cell in sensory_cells}
    parents: dict[str, str | None] = {cell: None for cell in sensory_cells}
    parent_kinds: dict[str, str | None] = {cell: None for cell in sensory_cells}
    frontier = dict(activation)
    edges = connectome["edges"]
    for hop in range(1, MAX_RELAY_HOPS + 1):
        next_frontier: dict[str, tuple[float, str, str]] = {}
        for edge in edges:
            source = edge["source"]
            target = edge["target"]
            gain = frontier.get(source)
            if gain is not None:
                candidate = gain * EDGE_ATTENUATION
                current = next_frontier.get(target)
                if current is None or candidate > current[0]:
                    next_frontier[target] = candidate, source, edge["kind"]
            if edge["kind"] == "electrical_gap_junction":
                gain = frontier.get(target)
                if gain is not None:
                    candidate = gain * EDGE_ATTENUATION
                    current = next_frontier.get(source)
                    if current is None or candidate > current[0]:
                        next_frontier[source] = candidate, target, edge["kind"]
        next_frontier = {
            cell: item for cell, item in next_frontier.items()
            if item[0] > activation.get(cell, 0.0)
        }
        if not next_frontier:
            break
        frontier = {cell: item[0] for cell, item in next_frontier.items()}
        for cell, (level, source, kind) in next_frontier.items():
            activation[cell] = level
            hops[cell] = hop
            parents[cell] = source
            parent_kinds[cell] = kind

    backward_routes = _command_routes(activation, parents, edges, "AVD", ("VA", "DA"))
    forward_routes = _command_routes(activation, parents, edges, "AVB", ("VB", "DB"))
    backward_score = max((route["activation_score"] for route in backward_routes), default=0.0)
    forward_score = max((route["activation_score"] for route in forward_routes), default=0.0)
    if backward_score > forward_score:
        direction = "backward"
    elif forward_score > backward_score:
        direction = "forward"
    else:
        direction = "undetermined"

    displayed_routes = backward_routes[:3] + forward_routes[:3]
    selected_routes = backward_routes if direction == "backward" else forward_routes if direction == "forward" else []
    movement_hops = len(selected_routes[0]["cells"]) - 1 if selected_routes else None
    path_nodes = set(sensory_cells)
    highlighted_edges = set()
    for route in displayed_routes:
        path_nodes.update(route["cells"])
        for source, target in zip(route["cells"], route["cells"][1:]):
            for edge in edges:
                direct_match = edge["source"] == source and edge["target"] == target
                gap_match = (
                    edge["kind"] == "electrical_gap_junction"
                    and edge["source"] == target
                    and edge["target"] == source
                )
                if direct_match or gap_match:
                    highlighted_edges.add((edge["kind"], edge["source"], edge["target"]))
                    break
    return {
        "stimulus": "anterior_touch",
        "sensory_cells": sensory_cells,
        "activation": [
            {"cell": cell, "level": activation[cell], "hop": hops[cell]}
            for cell in sorted(activation, key=lambda name: (hops[name], name))
        ],
        "relay_edges": [
            {
                "source": parents[cell],
                "target": cell,
                "kind": parent_kinds[cell],
                "hop": hops[cell],
                "activation": activation[cell],
            }
            for cell in sorted(parents, key=lambda name: (hops[name], name))
            if parents[cell] is not None
        ],
        "max_hop": max(hops.values(), default=0),
        "movement_hops": movement_hops,
        "highlight_cells": sorted(path_nodes),
        "highlight_edges": [
            {"kind": kind, "source": source, "target": target}
            for kind, source, target in sorted(highlighted_edges)
        ],
        "backward_motor_routes": backward_routes[:3],
        "forward_motor_routes": forward_routes[:3],
        "backward_score": backward_score,
        "forward_score": forward_score,
        "movement_command": direction,
        "assumptions": [
            f"Structural relay is limited to {MAX_RELAY_HOPS} hops.",
            f"Every chemical edge is treated as a positive relay with gain {EDGE_ATTENUATION}; workbook counts are not used as conductances.",
            f"Electrical edges relay bidirectionally with gain {EDGE_ATTENUATION}; measured conductances are unavailable.",
            f"AVD-to-VA/DA and AVB-to-VB/DB are assumed backward/forward motor readouts with gain {MOTOR_READOUT_GAIN}.",
            "A first-arrival spanning relay edge is shown per activated cell; this is not a complete synaptic event log.",
            "The 0.12 s per-hop display timing is a UI assumption, not a biological latency.",
            "This event relay has no membrane dynamics, synaptic signs, spontaneous activity, or calibrated biological timing.",
        ],
    }


def simulate_anterior_touch(connectome: dict) -> dict:
    sensory_cells = ["ALML", "ALMR"]
    missing = [cell for cell in sensory_cells if cell not in connectome["nodes"]]
    if missing:
        raise ValueError(f"Anterior touch receptors are absent from this connectome: {missing}")
    result = relay_from_cells(connectome, sensory_cells)
    result["assumptions"].append(
        "The anterior touch pulse directly excites ALML and ALMR; AVM recruitment occurs only through recorded graph edges."
    )
    return result
