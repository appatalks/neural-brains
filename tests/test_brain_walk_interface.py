import json
import math
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from fly_brain_walk import (DRIVE_KEYS, OUTPUT_IDS, WalkingControl, WalkingReference,
                            prescribed_drive, profile_metrics, validate_drive)
from fly_brain_walk import scene_drive
from fly_feeding import BrainClient


def metadata():
    return {"walking_control_enabled": True, "sensorimotor_candidates": [
        {"population": group, "side": side, "root_id": root, "in_model": True,
         "ambiguous_type_correspondence": False}
        for group, pair in OUTPUT_IDS.items() for side, root in pair.items()]}


def response(sequence=1, count=10, drive=None):
    return {"neuron_activity": {"sequence": sequence, "episode": 0,
                               "start_ms": (sequence-1)*10., "end_ms": sequence*10.},
            "brain_time_ms": sequence*10.,
            "sensorimotor_spikes": {root: count for pair in OUTPUT_IDS.values() for root in pair.values()},
            "walking_drive_Hz": drive or dict(zip(DRIVE_KEYS, (150., 0., 0., 0.)))}


class BrainWalkTests(unittest.TestCase):
    def test_exact_identities_and_explicit_enablement(self):
        for mutate in (
            lambda m: m.update(walking_control_enabled=False),
            lambda m: m["sensorimotor_candidates"].pop(),
            lambda m: m["sensorimotor_candidates"][0].update(root_id="wrong"),
            lambda m: m["sensorimotor_candidates"][0].update(ambiguous_type_correspondence=True),
        ):
            value = metadata()
            mutate(value)
            with self.assertRaises(ValueError):
                WalkingControl(value)

    def test_drive_validation_copies_and_rejects_invalid_rates(self):
        value = dict.fromkeys(DRIVE_KEYS, 0)
        self.assertEqual(validate_drive(value), value)
        self.assertIsNot(validate_drive(value), value)
        for invalid in (None, {}, {**value, "extra": 0},
                        *({**value, "BPN": rate} for rate in (-1, 151, True, math.nan, math.inf, "150"))):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_drive(invalid)

    def test_zero_packets_cannot_create_motor_commands(self):
        control = WalkingControl(metadata())
        control.turn_bias = -30
        control.accept(response(count=0))
        self.assertEqual(control.advance(.01), (0., 0.))

    def test_bounded_commands_and_reset(self):
        control = WalkingControl(metadata())
        control.accept(response())
        self.assertEqual(control.desired_speed, 2.)
        self.assertEqual(control.advance(.01), (.1, 0.))
        for dt in (0, -.01, .02, math.nan, True):
            with self.assertRaises(ValueError):
                control.advance(dt)
        control.reset()
        self.assertEqual(control.sequence, 0)
        self.assertTrue(all(rate == 0 for rate in control.rates.values()))
        self.assertEqual(control.advance(.01), (0., 0.))

    def test_neural_laterality_drives_both_turn_signs(self):
        for side, sign in (("left", 1), ("right", -1)):
            control = WalkingControl(metadata())
            packet = response(drive={"BPN": 150., "P9_left": 150., "P9_right": 0., "FG": 0.})
            for group in ("DNa02", "DNa11"):
                for local_side, root in OUTPUT_IDS[group].items():
                    packet["sensorimotor_spikes"][root] = 30 if local_side == side else 0
            control.accept(packet)
            self.assertEqual(control.desired_turn, sign*2.)
            self.assertAlmostEqual(control.advance(.01)[1], sign*.04)

    def test_invalid_packets_do_not_mutate_filters(self):
        for mutate in (
            lambda r: r["neuron_activity"].update(sequence=2),
            lambda r: r["neuron_activity"].update(episode=True),
            lambda r: r["neuron_activity"].update(start_ms=1.),
            lambda r: r["neuron_activity"].update(end_ms=math.nan),
            lambda r: r.update(brain_time_ms=11.),
            lambda r: r["sensorimotor_spikes"].update({OUTPUT_IDS["BDN2"]["left"]: True}),
            lambda r: r["walking_drive_Hz"].update(BPN=200),
        ):
            control = WalkingControl(metadata())
            packet = response()
            mutate(packet)
            before = control.snapshot()
            with self.assertRaises(ValueError):
                control.accept(packet)
            self.assertEqual(control.snapshot(), before)
        control.accept(response())
        with self.assertRaises(ValueError):
            control.accept(response())
        packet = response(2)
        packet["neuron_activity"]["episode"] = 1
        with self.assertRaises(ValueError):
            control.accept(packet)

    def test_reference_is_contiguous_and_reinitializes_at_handoff(self):
        reference = WalkingReference()
        position = [3., 4., 5.]
        reference.begin(position, 0.)
        reference.update(position, .0002, 2., 1.)
        target, velocity, yaw = reference.reference(.1002)
        self.assertAlmostEqual(yaw, .1)
        self.assertAlmostEqual(target[0], 3+2*math.sin(.1))
        self.assertAlmostEqual(velocity[0], 2*math.cos(.1))
        self.assertEqual(position, [3., 4., 5.])
        with self.assertRaises(ValueError):
            reference.update(position, 1., 2., 0.)
        reference.begin(position, 20., .5)
        reference.update(position, 20.0002, 0., 0.)
        self.assertEqual(reference.reference(20.1)[1], [0., 0., 0.])

    def test_terrain_height_is_smoothed_without_writing_physical_position(self):
        reference=WalkingReference()
        position=[0.,0.,.1478]
        reference.begin(position,0.,height=.1478)
        reference.update(position,.01,2.,0.,height=.1278)
        self.assertAlmostEqual(reference.reference(.1)[0][2],.1438)
        self.assertEqual(position,[0.,0.,.1478])
        with self.assertRaises(ValueError):
            reference.update(position,.02,2.,0.,height=.1)

    def test_fixed_profile_and_incomplete_failure(self):
        self.assertEqual(prescribed_drive(0.), dict.fromkeys(DRIVE_KEYS, 0.))
        for time, key in ((.5, "BPN"), (1.5, "P9_left"), (2.5, "P9_right"), (3.5, "FG")):
            self.assertEqual(prescribed_drive(time)[key], 150.)
        self.assertEqual(prescribed_drive(4.5), dict.fromkeys(DRIVE_KEYS, 0.))
        self.assertFalse(profile_metrics([])["passed"])

    def test_scene_cues_are_json_serializable_and_do_not_write_body_state(self):
        try:
            import mujoco as mj
        except ImportError:
            self.skipTest("MuJoCo required for actual scene cue test")
        model = mj.MjModel.from_xml_string("""<mujoco><worldbody>
          <geom name="groundplane" type="plane" size="20 20 .1"/>
          <body name="walker" pos="0 0 .2"><freejoint/>
            <geom name="walker/torso" type="sphere" size=".1" group="1"/>
          </body></worldbody></mujoco>""")
        data = mj.MjData(model)
        for x, expected in ((0., False), (9., True)):
            data.qpos[0] = x
            mj.mj_forward(model, data)
            before = data.qpos.copy()
            drive, cues = scene_drive(model, data, model.body("walker").id, 11.25, True)
            self.assertIs(cues["boundary_cue"], expected)
            json.dumps({"drive": drive, "cues": cues}, allow_nan=False)
            self.assertTrue((data.qpos == before).all())
        drive, cues = scene_drive(model, data, model.body("walker").id, 11.25, False)
        self.assertFalse(cues["active"])
        self.assertFalse(any(drive.values()))

    def test_client_copies_and_echo_checks_walking_drive(self):
        client = BrainClient.__new__(BrainClient)
        client.pending = False
        client.graded_vision = False
        client.walking_control = True
        client.send = Mock()
        drive = dict(zip(DRIVE_KEYS, (150., 0., 0., 0.)))
        client.begin_step(10., False, walking_drive_Hz=drive)
        drive["BPN"] = 0.
        self.assertEqual(client.expected_walking_drive["BPN"], 150.)
        client.receive = Mock(return_value={"duration_ms": 10., "sugar_contact": False,
                                           "looming_active": False, "walking_drive_Hz": drive})
        client.activity_reader = Mock()
        with self.assertRaisesRegex(RuntimeError, "walking drive"):
            client.finish_step()
        client.activity_reader.accept.assert_not_called()
        client.pending = False
        client.walking_control = False
        with self.assertRaises(ValueError):
            client.begin_step(10., False, walking_drive_Hz=drive)
        client.begin_step(10., False)
        self.assertNotIn("walking_drive_Hz", client.send.call_args.args[0])


@unittest.skipUnless(os.environ.get("FLY_ACTIVITY_DATA_DIR") and os.environ.get("FLY_ACTIVITY_OUTPUT_DIR"),
                     "Explicit external data/output required for actual neural walking regression")
class ActualBrainWalkTests(unittest.TestCase):
    def test_silent_control_and_exact_seeded_reset(self):
        from datasets import ROOT
        from fly_walking import external_output
        base = Path(os.environ["FLY_ACTIVITY_OUTPUT_DIR"])
        output = external_output(base.with_name(base.name+"-brain-walking"))
        output.mkdir(parents=True)
        client = BrainClient(ROOT/".venv/bin/python", Path(os.environ["FLY_ACTIVITY_DATA_DIR"]),
                             output, 420, takeoff=True, telemetry=True, walking_control=True)
        try:
            self.assertEqual(len(client.metadata["sensorimotor_candidates"]), 71)
            (output/"metadata.json").write_text(json.dumps(client.metadata)+"\n")
            trials = []
            for run in range(2):
                client.reset()
                control = WalkingControl(client.metadata)
                packets = []
                with (output/f"replay-{run}.jsonl").open("x") as log:
                    for step in range(80):
                        drive = dict.fromkeys(DRIVE_KEYS, 0.)
                        if step >= 20:
                            drive["BPN"] = 150.
                        client.begin_step(10., False, walking_drive_Hz=drive)
                        reply = client.finish_step()
                        control.accept(reply)
                        control.advance(.01)
                        if step < 20:
                            self.assertEqual(reply["network_spikes"], 0)
                        log.write(json.dumps(reply)+"\n")
                        packets.append((reply["neuron_activity"]["indices"],reply["neuron_activity"]["counts"],
                                        reply["sensorimotor_spikes"],control.snapshot()))
                self.assertGreater(control.speed, .5)
                trials.append(packets)
            self.assertEqual(trials[0],trials[1])
            (output/"summary.json").write_text(json.dumps({"status":"passed","zero_input_silent":True,
                                                         "exact_seeded_replay":True,"readouts":71})+"\n")
        finally:
            client.close()
