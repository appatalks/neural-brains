"""Persistent FlyWire-630 network behind a versioned JSON line interface."""

import argparse
import contextlib
import importlib.metadata
import importlib.util
import json
import math
import sys
from pathlib import Path

from datasets import CATALOG, ROOT
from run_flywire_sugar import PROTOCOL, verified_inputs
from sim_units import simulation_steps
from fly_activity import activity_packet


def request_values(request: dict) -> tuple[str, float | None, bool | None]:
    if not isinstance(request, dict):
        raise ValueError("Brain request must be a JSON object")
    operation = request.get("op")
    if operation in {"reset", "close"} and set(request) == {"op"}:
        return operation, None, None
    if operation == "step" and set(request) == {"op", "duration_ms", "sugar_contact"}:
        duration = request["duration_ms"]
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration):
            raise ValueError("Brain duration must be finite")
        if not 0 < duration <= 1000:
            raise ValueError("Brain interval must be in (0, 1000] ms")
        simulation_steps(duration, 0.1)
        if type(request["sugar_contact"]) is not bool:
            raise ValueError("Sugar contact must be a boolean")
        return operation, float(duration), request["sugar_contact"]
    raise ValueError("Unknown brain operation or invalid request fields")


class Brain:
    def __init__(self, data_dir: Path, seed_value: int, takeoff: bool = False, telemetry: bool = False,
                 disconnect_visual_output: str | None = None, dnp10_intervention: str | None = None,
                 graded_vision: bool = False):
        import pandas as pd
        from brian2 import Hz, Network, SpikeMonitor, defaultclock, ms, prefs, seed, start_scope

        if seed_value < 0:
            raise ValueError("Seed must be nonnegative")
        if type(graded_vision) is not bool or graded_vision and not takeoff:
            raise ValueError("Graded vision requires the verified takeoff populations")
        self.graded_vision = graded_vision
        self.visual_population_indices = {}
        if disconnect_visual_output is not None and not takeoff:
            raise ValueError("Visual output disconnection requires verified takeoff populations")
        if dnp10_intervention is not None and (
            not takeoff or not telemetry or dnp10_intervention not in {"sham", "silence"}
        ):
            raise ValueError("DNp10 intervention requires verified telemetry and sham or silence")
        data_dir = data_dir.expanduser().resolve()
        if data_dir == ROOT or ROOT in data_dir.parents:
            raise ValueError("Brain inputs must be outside Git")
        protocol = json.loads(PROTOCOL.read_text())
        catalog = json.loads(CATALOG.read_text())
        dataset = next(d for d in catalog["datasets"] if d["id"] == protocol["dataset_id"])
        inputs = verified_inputs(data_dir, dataset)
        comp = inputs["2023_03_23_completeness_630_final.csv"]
        con = inputs["2023_03_23_connectivity_630_final.parquet"]
        ids = pd.read_csv(comp, index_col=0).index
        if len(ids) != 127400 or not ids.is_unique or ids.dtype.kind not in "iu":
            raise ValueError("Pinned brain neuron IDs/count disagree with validated baseline")
        mapping = {int(value): index for index, value in enumerate(ids)}
        input_ids = [int(value) for value in protocol["input_ids"]]
        self.readout_index = mapping[int(protocol["readout_id"])]
        spec = importlib.util.spec_from_file_location("live_pinned_model", inputs["model.py"])
        model = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(model)
        start_scope()
        defaultclock.dt = protocol["time_step_ms"] * ms
        prefs.codegen.target = "cython"
        params = dict(model.default_params, r_poi=100 * Hz)
        neu, syn, unused_monitor = model.create_model(comp, con, params)
        if len(syn) != 14687178:
            raise ValueError("Pinned brain connection count differs from validated baseline")
        del unused_monitor
        self.stimulation, neu = model.poi(neu, [mapping[value] for value in input_ids], [], params)
        self.monitor = SpikeMonitor(neu, record=False)
        self.network = Network(neu, syn, self.monitor, *self.stimulation)
        self.visual_input = None
        self.gf_indices = {}
        self.sensorimotor_indices = {}
        sensorimotor_candidates = []
        visual_ids = []
        intervention = None
        dn_intervention = None
        if takeoff:
            import csv
            from audit_takeoff_circuit import select_neurons
            from brian2 import PoissonGroup, Synapses

            annotation_dataset = next(d for d in catalog["datasets"] if d["id"] == "flywire-annotations-630-v1.1.0")
            annotation_paths = verified_inputs(data_dir, annotation_dataset)
            with annotation_paths["Supplemental_file1_annotations.tsv"].open() as stream:
                annotation_rows = list(csv.DictReader(stream, delimiter="\t"))
            candidates = select_neurons(annotation_rows, {str(value) for value in ids})
            if telemetry:
                from audit_sensorimotor_paths import select_candidates
                from audit_flight_steering import select_dng02
                sensorimotor_candidates = select_candidates(annotation_rows, {str(value) for value in ids})
                sensorimotor_candidates.extend([
                    {**row, "population": "DNg02", "ambiguous_type_correspondence": False,
                     "evidence_scope": "flight amplitude/optomotor candidate; subtype-to-driver correspondence not established"}
                    for row in select_dng02(annotation_rows, {str(value) for value in ids})
                ])
                if any(not row["in_model"] for row in sensorimotor_candidates):
                    raise ValueError("Sensorimotor observation candidate is absent from verified network")
                self.sensorimotor_indices = {
                    row["root_id"]: mapping[int(row["root_id"])] for row in sensorimotor_candidates
                }
                if dnp10_intervention is not None:
                    from fly_leg_extension import verified_dnp10
                    targets = verified_dnp10({"sensorimotor_candidates": sensorimotor_candidates})
                    for value in targets:
                        index = mapping[int(value)]
                        clamp = neu[index:index+1].run_regularly(
                            "v = v_0; g = 0*mV" if dnp10_intervention == "silence" else "v = v; g = g",
                            when="before_thresholds",
                        )
                        self.network.add(clamp)
                    dn_intervention = {
                        "kind": "model_spike_silencing" if dnp10_intervention == "silence" else "identity_sham",
                        "neuron_ids": targets,
                        "scope": "Selected DNp10 voltage and synaptic state clamped to rest before each threshold evaluation; sham runs identity updates. Not an animal-equivalent silencing method.",
                    }
            if any(not row["in_model"] for row in candidates):
                raise ValueError("Takeoff populations have unverified model IDs")
            visual_ids = [row["root_id"] for row in candidates if row["population"] in {"LC4", "LPLC2"}]
            if graded_vision:
                self.visual_population_indices = {
                    population: [i for i, value in enumerate(visual_ids)
                                 if value in {row["root_id"] for row in candidates
                                              if row["population"] == population}]
                    for population in ("LC4", "LPLC2")
                }
                if any(not values for values in self.visual_population_indices.values()):
                    raise ValueError("Graded vision requires both exact visual populations")
            self.gf_indices = {row["root_id"]: mapping[int(row["root_id"])] for row in candidates if row["population"] == "GF"}
            # A shared PoissonGroup avoids compiling hundreds of separate input
            # objects. This encoder is not bit-identical to model.poi.
            self.visual_input = PoissonGroup(len(visual_ids), rates=100 * Hz)
            visual_synapses = Synapses(
                self.visual_input, neu, on_pre="v_post += stimulus_weight",
                namespace={"stimulus_weight": params["w_syn"] * params["f_poi"]},
            )
            visual_synapses.connect(i=list(range(len(visual_ids))), j=[mapping[int(value)] for value in visual_ids])
            for value in visual_ids:
                neu[mapping[int(value)]].rfc = 0 * ms
            self.visual_input.active = False
            self.network.add(self.visual_input, visual_synapses)
            if disconnect_visual_output is not None:
                from fly_circuit_interventions import outgoing_edge_indices, visual_output_targets
                target_ids = visual_output_targets(candidates, disconnect_visual_output)
                edges = outgoing_edge_indices(syn.i[:], [mapping[int(value)] for value in target_ids])
                if not len(edges):
                    raise ValueError("Verified population has no chemical output edges to disconnect")
                nonzero = sum(syn.w[edges] != 0 * params["w_syn"])
                syn.w[edges] = 0 * params["w_syn"]
                if any(syn.w[edges] != 0 * params["w_syn"]):
                    raise RuntimeError("Chemical-output intervention did not zero selected weights")
                intervention = {
                    "kind": "chemical_output_disconnection",
                    "population": disconnect_visual_output, "neuron_ids": target_ids,
                    "selected_aggregated_edges": int(len(edges)), "previously_nonzero_edges": int(nonzero),
                    "scope": "All selected recurrent chemical outputs zeroed before initial state storage. Incoming inputs, spikes and Poisson drive remain; not neuronal silencing or an animal-equivalent intervention.",
                }
        for stimulus in self.stimulation:
            stimulus.active = False
        self.network.store("initial")
        self.ms = ms
        self.seed = seed
        self.seed_value = seed_value
        seed(seed_value)
        self.elapsed_ms = 0.0
        self.telemetry = telemetry
        self.episode = 0
        self.sequence = 0
        self.metadata = {
            "op": "ready", "protocol_version": 1,
            "neurons": len(neu), "aggregated_connections": len(syn),
            "input_ids": protocol["input_ids"], "mn9_id": protocol["readout_id"],
            "upstream_commit": protocol["upstream_commit"],
            "brian2": importlib.metadata.version("brian2"),
            "stimulation_Hz": 100, "seed": seed_value,
            "scope": "Persistent actual FlyWire spikes. MN9 readout is not proboscis biomechanics or locomotion.",
            "takeoff_inputs_enabled": takeoff, "visual_input_ids": visual_ids,
            "gf_ids": list(self.gf_indices),
            "visual_encoder": "binary approach gates 100 Hz independent PoissonGroup inputs; not fitted LC4/LPLC2 looming responses" if takeoff else None,
        }
        if telemetry:
            from fly_connections import ensure_index
            neuron_ids = [str(value) for value in ids]
            index_directory = ensure_index(data_dir, con, neuron_ids, protocol["upstream_commit"])
            self.metadata.update({
                "neuron_activity_schema_version": 1,
                "neuron_ids": neuron_ids,
                "connection_index_dir": str(index_directory),
                "activity_scope": "Exact sparse spike-count deltas per interval; no event timestamps or anatomical coordinates.",
            })
            if takeoff:
                self.metadata["sensorimotor_candidates"] = sensorimotor_candidates
                self.metadata["sensorimotor_scope"] = "Readouts only; no steering/landing motor decoder or added stimulation."
        if intervention is not None:
            self.metadata["research_intervention"] = intervention
        if dn_intervention is not None:
            self.metadata["dnp10_intervention"] = dn_intervention
        if graded_vision:
            from fly_looming import GRADED_ENCODER
            self.metadata.update({
                "graded_vision_enabled": True, "graded_visual_encoder": GRADED_ENCODER,
                "visual_encoder": GRADED_ENCODER["scope"],
                "visual_population_ids": {
                    population: [visual_ids[i] for i in values]
                    for population, values in self.visual_population_indices.items()
                },
            })

    def reset(self):
        self.network.restore("initial")
        self.seed(self.seed_value)
        self.elapsed_ms = 0.0
        self.episode += 1
        self.sequence = 0
        response = {"op": "reset", "brain_time_ms": 0.0}
        if self.telemetry:
            response["neuron_activity"] = activity_packet([], self.episode, 0, 0, 0)
        return response

    def step(self, duration_ms: float, contact: bool, looming: bool = False, visual_rates_Hz=None):
        from fly_looming import validate_visual_rates

        if self.graded_vision:
            visual_rates_Hz = validate_visual_rates(visual_rates_Hz)
            if looming != any(visual_rates_Hz.values()):
                raise ValueError("Looming active must match graded visual rates")
        elif visual_rates_Hz is not None:
            raise ValueError("Rate input requires an explicitly enabled graded worker")
        before_counts = self.monitor.count[:].copy() if self.telemetry else None
        start_ms = self.elapsed_ms
        before_readout = int(self.monitor.count[self.readout_index])
        before_total = int(self.monitor.num_spikes)
        before_gf = {value: int(self.monitor.count[index]) for value, index in self.gf_indices.items()}
        if looming and self.visual_input is None:
            raise ValueError("Looming input requested without verified takeoff circuit enabled")
        if self.visual_input is not None:
            if self.graded_vision:
                from brian2 import Hz
                for population, indices in self.visual_population_indices.items():
                    self.visual_input.rates[indices] = visual_rates_Hz[population] * Hz
            self.visual_input.active = looming
        for stimulus in self.stimulation:
            stimulus.active = contact
        self.network.run(duration_ms * self.ms)
        self.elapsed_ms += duration_ms
        readout = int(self.monitor.count[self.readout_index]) - before_readout
        total = int(self.monitor.num_spikes) - before_total
        response = {
            "op": "step", "duration_ms": duration_ms, "sugar_contact": contact,
            "brain_time_ms": self.elapsed_ms, "mn9_spikes": readout,
            "mn9_rate_Hz": readout * 1000 / duration_ms, "network_spikes": total,
            "feeding_circuit_active": readout > 0,
            "looming_active": looming,
            "giant_fiber_spikes": {
                value: int(self.monitor.count[index]) - before_gf[value]
                for value, index in self.gf_indices.items()
            },
            "physical_takeoff_connected": False,
        }
        if self.telemetry:
            self.sequence += 1
            response["neuron_activity"] = activity_packet(
                self.monitor.count[:] - before_counts, self.episode, self.sequence,
                start_ms, self.elapsed_ms,
            )
            if self.sensorimotor_indices:
                response["sensorimotor_spikes"] = {
                    value: int(self.monitor.count[index] - before_counts[index])
                    for value, index in self.sensorimotor_indices.items()
                }
        if self.graded_vision:
            response["visual_rates_Hz"] = visual_rates_Hz
        return response


def emit(value):
    print(json.dumps(value, allow_nan=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=420)
    parser.add_argument("--takeoff-circuit", action="store_true")
    parser.add_argument("--neuron-telemetry", action="store_true")
    parser.add_argument("--disconnect-visual-output", choices=["LC4", "LPLC2", "both"],
                        help="Explicit isolated research intervention, not a normal habitat control")
    parser.add_argument("--dnp10-intervention", choices=["sham", "silence"],
                        help="Isolated model voltage-clamp intervention, not a browser control")
    parser.add_argument("--graded-vision", action="store_true",
                        help="Explicit continuous LC4/LPLC2 rate interface; not fitted physiology")
    args = parser.parse_args()
    try:
        with contextlib.redirect_stdout(sys.stderr):
            brain = Brain(args.data_dir, args.seed, args.takeoff_circuit, args.neuron_telemetry,
                          args.disconnect_visual_output, args.dnp10_intervention, args.graded_vision)
        emit(brain.metadata)
        for line in sys.stdin:
            request = json.loads(line)
            looming = request.pop("looming_active", False)
            if type(looming) is not bool:
                raise ValueError("Looming input must be a boolean")
            has_rates = "visual_rates_Hz" in request
            rates = request.pop("visual_rates_Hz") if has_rates else None
            if has_rates:
                from fly_looming import validate_visual_rates
                rates = validate_visual_rates(rates)
            operation, duration, contact = request_values(request)
            if operation != "step" and (has_rates or looming):
                raise ValueError("Visual input is only valid for step requests")
            with contextlib.redirect_stdout(sys.stderr):
                if operation == "step":
                    response = brain.step(duration, contact, looming, rates)
                elif operation == "reset":
                    response = brain.reset()
                else:
                    response = {"op": "closed"}
            emit(response)
            if operation == "close":
                return 0
        return 0
    except Exception as error:
        emit({"op": "error", "type": type(error).__name__, "message": str(error)})
        print(f"ERROR: brain worker failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
