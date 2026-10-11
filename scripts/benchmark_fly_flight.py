"""Run fixed published-policy tracking cases; preserve and report failures."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from datasets import ROOT


CONFIG = ROOT / "experiments/fly-flight/benchmark.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.expanduser().resolve()
    if output == ROOT or ROOT in output.parents or output.exists():
        parser.error("Choose a new output directory outside Git")
    output.mkdir(parents=True)
    config = json.loads(CONFIG.read_text())
    if config.get("schema_version") != 1 or not isinstance(config.get("cases"), list) or not config["cases"]:
        parser.error("Benchmark needs a nonempty version-1 case list")
    (output / "benchmark.json").write_text(json.dumps(config, indent=2) + "\n")
    (output / "status.json").write_text('{"status": "running"}\n')
    results = []
    try:
        for index, case in enumerate(config["cases"]):
            run = output / f"case-{index:02d}"
            command = [
                sys.executable, str(ROOT / "scripts/fly_flight.py"), "--headless",
                "--controller", "trained", "--data-dir", str(args.data_dir),
                "--output-dir", str(run), "--seconds", str(case["seconds"]),
                "--seed", str(case["seed"]), "--trajectory", str(case["trajectory"]),
                "--gust-uN", str(case["gust_uN"]),
            ]
            with (output / f"case-{index:02d}.log").open("w") as log:
                completed = subprocess.run(
                    command, stdout=log, stderr=subprocess.STDOUT,
                    env={**os.environ, "MUJOCO_GL": "egl"}, check=False,
                )
            summary_path = run / "summary.json"
            summary = json.loads(summary_path.read_text()) if summary_path.exists() else None
            parameters_match = summary is not None and (
                summary["seed"] == case["seed"] and summary["trajectory"] == case["trajectory"]
                and summary["requested_simulated_seconds"] == case["seconds"]
                and summary["gust"]["lateral_force_uN"] == case["gust_uN"]
                and summary["controller"] == "trained"
            )
            result = {
                "case": case, "exit_code": completed.returncode,
                "passed": completed.returncode == 0 and parameters_match
                    and summary["tracking_validation"]["passed"],
                "parameters_match": parameters_match,
                "tracking": summary["tracking_validation"] if summary is not None else None,
                "status": summary["status"] if summary is not None else "missing_summary",
                "runner_sha256": summary["runner_sha256"] if summary is not None else None,
                "policy_module_sha256": summary["policy_module_sha256"] if summary is not None else None,
                "unit_module_sha256": summary["unit_module_sha256"] if summary is not None else None,
                "initial_wing_phase_index": summary["initial_wing_phase_index"] if summary is not None else None,
            }
            results.append(result)
            print(json.dumps(result), flush=True)
        consistent = all(
            len({result[field] for result in results}) == 1 and results[0][field] is not None
            for field in ["runner_sha256", "policy_module_sha256", "unit_module_sha256"]
        )
        all_passed = consistent and all(result["passed"] for result in results)
        summary = {
            "passed": all_passed, "cases_passed": sum(r["passed"] for r in results),
            "cases_total": len(results), "results": results,
            "benchmark_sha256": hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
            "code_provenance_consistent": consistent,
            "scope": config["description"],
        }
        (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        (output / "status.json").write_text(json.dumps({"status": "passed" if all_passed else "failed"}) + "\n")
        if not all_passed:
            print("ERROR: benchmark has failed cases; inspect individual summaries and logs", file=sys.stderr)
        return 0 if all_passed else 1
    except (OSError, ValueError, KeyError) as error:
        (output / "status.json").write_text(json.dumps({"status": "failed", "error": str(error)}) + "\n")
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
