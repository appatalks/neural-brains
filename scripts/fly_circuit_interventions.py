"""Explicit chemical-output disconnection; never described as spike silencing."""


def visual_output_targets(candidates, population):
    if population not in {"LC4", "LPLC2", "both"}:
        raise ValueError("Chemical-output disconnection requires LC4, LPLC2 or both")
    requested = {"LC4", "LPLC2"} if population == "both" else {population}
    rows = [row for row in candidates if row["population"] in requested]
    if {row["population"] for row in rows} != requested:
        raise ValueError("Requested verified visual population is absent")
    ids = [row["root_id"] for row in rows]
    if len(set(ids)) != len(ids) or any(not row["in_model"] for row in rows):
        raise ValueError("Intervention requires unique verified model identities")
    return ids


def outgoing_edge_indices(presynaptic_indices, targets):
    import numpy as np

    sources = np.asarray(presynaptic_indices)
    selected = np.asarray(targets)
    if (
        sources.ndim != 1 or selected.ndim != 1
        or sources.dtype.kind not in "iu" or selected.dtype.kind not in "iu"
        or selected.size == 0 or np.any(sources < 0) or np.any(selected < 0)
        or len(np.unique(selected)) != len(selected)
    ):
        raise ValueError("Chemical edge selection requires distinct nonnegative integer neuron indices")
    return np.flatnonzero(np.isin(sources, selected))
