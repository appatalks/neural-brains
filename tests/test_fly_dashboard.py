import copy
import http.client
import io
import json
import shutil
import socket
import subprocess
import sys
import threading
import time
import unittest
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fly_dashboard


class DashboardTests(unittest.TestCase):
    def test_observed_fly_change_resets_activity_totals_not_brain_episode(self):
        packet=self.packet()
        packet["observed_fly_id"]=1
        self.dashboard.publish(packet)
        other=self.packet()
        other["observed_fly_id"]=2
        other["neuron_activity"].update(counts=[1,1],network_spikes=2)
        other.update(network_spikes=2,mn9_spikes=1)
        self.dashboard.publish(other)
        summary=json.loads(self.request("/api/activity-summary")[2])
        self.assertEqual(summary["observed_fly_id"],2)
        self.assertEqual(summary["episode"],0)
        self.assertEqual(summary["episode_spikes"],2)
        self.assertEqual(summary["active_intervals"],1)
    def setUp(self):
        self.output = Path(__file__).resolve().parent / (".dashboard-test-" + uuid.uuid4().hex)
        self.metadata = {
            "neuron_ids": ["9007199254740993001", "9007199254740993002", "MN9-ID"],
            "input_ids": ["9007199254740993001"],
            "visual_input_ids": ["9007199254740993001"],
            "mn9_id": "MN9-ID",
            "gf_ids": ["9007199254740993002"],
            "snapshot": {"upstream_commit": "abc123"},
        }
        self.dashboard = fly_dashboard.Dashboard(self.output, self.metadata)
        self.addCleanup(shutil.rmtree, self.output, True)
        self.addCleanup(self.dashboard.close)

    def packet(self, sequence=1):
        return {
            "neuron_activity": {
                "schema_version": 1, "episode": 0, "sequence": sequence,
                "start_ms": 0.0, "end_ms": 10.0, "indices": [0, 2],
                "counts": [2, 1], "network_spikes": 3,
            },
            "network_spikes": 3, "mn9_spikes": 1,
            "giant_fiber_spikes": {"9007199254740993002": 0},
            "brain_time_ms": 10.0, "habitat_time_s": 0.1, "paused": False,
        }

    def request(self, path, method="GET", headers=None, body=None):
        address = urlsplit(self.dashboard.url)
        connection = http.client.HTTPConnection(address.hostname, address.port, timeout=2)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_routes_and_manifest(self):
        self.assertEqual(urlsplit(self.dashboard.url).hostname, "127.0.0.1")
        manifest = json.loads((self.output / "dashboard.json").read_text())
        self.assertEqual(manifest, {"url": self.dashboard.url, "status": "running", "session_id": self.dashboard.session_id})
        status, headers, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b"NOT anatomy", body)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertNotIn(b"https://", body)
        status, headers, body = self.request("/api/metadata")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), self.metadata)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Fly-Session"], self.dashboard.session_id)
        self.assertEqual(int(headers["Content-Length"]), len(body))

    def test_unavailable_before_publish(self):
        for path in ("/api/state", "/api/eyes"):
            status, _, body = self.request(path)
            self.assertEqual(status, 503)
            self.assertFalse(json.loads(body)["available"])
        self.assertEqual(json.loads(self.request("/api/status")[2]), {
            "status": "running", "state_available": False,
            "eyes_available": False, "eyes_revision": 0,
            "habitat_status": None, "paused": None,
            "session_id": self.dashboard.session_id, "connections_available": False,
            "world_available": False, "world_revision": 0, "world_time_s": None, "interactive": False,
        })

    def test_status_heartbeat_preserves_sequence_and_eye_clock(self):
        packet = self.packet(64)
        packet.update(status="paused", paused=True, eye_time_s=0.025)
        self.dashboard.publish(packet)
        self.assertEqual(json.loads(self.request("/api/state")[2]), packet)
        packet.update(status="finished", habitat_time_s=5.0)
        self.dashboard.publish(packet)
        self.assertEqual(json.loads(self.request("/api/state")[2]), packet)
        status = json.loads(self.request("/api/status")[2])
        self.assertEqual(status["habitat_status"], "finished")
        self.assertTrue(status["paused"])
        self.assertEqual(status["status"], "running")

    def test_activity_summary_captures_firing_missed_between_polls(self):
        self.dashboard.publish(self.packet(1))
        self.dashboard.publish(self.packet(1))
        silent=self.packet(2)
        silent["neuron_activity"].update(indices=[],counts=[],network_spikes=0,start_ms=10,end_ms=20)
        silent.update(network_spikes=0,mn9_spikes=0,brain_time_ms=20)
        self.dashboard.publish(silent)
        summary=json.loads(self.request("/api/activity-summary")[2])
        self.assertEqual(summary["episode_spikes"],3)
        self.assertEqual(summary["active_intervals"],1)
        self.assertEqual(summary["last_firing"]["counts"],[2,1])
        self.assertEqual(summary["last_firing"]["sequence"],1)
        self.assertEqual(json.loads(self.request("/api/state")[2])["network_spikes"],0)
        reset={"op":"reset","brain_time_ms":0,"neuron_activity":{
            "schema_version":1,"episode":1,"sequence":0,"start_ms":0,"end_ms":0,
            "indices":[],"counts":[],"network_spikes":0,
        }}
        self.dashboard.publish(reset)
        summary=json.loads(self.request("/api/activity-summary")[2])
        self.assertEqual(summary["episode_spikes"],0)
        self.assertIsNone(summary["last_firing"])

    def test_no_mutable_aliases_and_no_renumbering(self):
        original_metadata = copy.deepcopy(self.metadata)
        self.metadata["neuron_ids"][0] = "changed"
        packet = self.packet(sequence=72)
        original = copy.deepcopy(packet)
        self.dashboard.publish(packet)
        packet["neuron_activity"]["counts"][0] = 999
        packet["giant_fiber_spikes"]["new"] = 50
        self.assertEqual(json.loads(self.request("/api/metadata")[2]), original_metadata)
        received = json.loads(self.request("/api/state")[2])
        self.assertEqual(received, original)
        received["neuron_activity"]["indices"].clear()
        self.assertEqual(json.loads(self.request("/api/state")[2]), original)
        self.dashboard.publish(self.packet(sequence=73))
        self.assertEqual(json.loads(self.request("/api/state")[2])["neuron_activity"]["sequence"], 73)

    def test_reset_and_rgb_image_snapshot(self):
        import numpy as np
        from PIL import Image

        eyes = np.zeros((4, 8, 3), dtype=np.uint8)
        eyes[:, :4] = [255, 0, 0]
        eyes[:, 4:] = [0, 255, 0]
        original_eyes = eyes.copy()
        self.dashboard.publish(self.packet(), eyes)
        eyes[:] = 0
        status, headers, body = self.request("/api/eyes")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "image/png")
        self.assertTrue(body.startswith(b"\x89PNG\r\n\x1a\n"))
        with Image.open(io.BytesIO(body)) as image:
            self.assertEqual(image.size, (8, 4))
            self.assertEqual(image.getpixel((0, 0)), (255, 0, 0))
            self.assertEqual(image.getpixel((7, 0)), (0, 255, 0))
            self.assertEqual(json.loads(self.request("/api/status")[2])["eyes_revision"], 1)
            self.dashboard.publish(self.packet(2))
            self.assertEqual(self.request("/api/eyes")[2], body)

            self.assertEqual(json.loads(self.request("/api/status")[2])["eyes_revision"], 1)
            self.dashboard.publish(self.packet(3), eyes)
            self.assertEqual(json.loads(self.request("/api/status")[2])["eyes_revision"], 2)
            self.dashboard.publish(self.packet(4), original_eyes)
            self.assertEqual(json.loads(self.request("/api/status")[2])["eyes_revision"], 3)
        reset = {
            "op": "reset", "brain_time_ms": 0,
            "neuron_activity": {
                "schema_version": 1, "episode": 1, "sequence": 0,
                "start_ms": 0, "end_ms": 0, "indices": [], "counts": [], "network_spikes": 0,
            },
        }
        self.dashboard.publish(reset)
        self.assertEqual(json.loads(self.request("/api/state")[2]), reset)
        self.assertEqual(self.request("/api/eyes")[0], 200)
        self.assertEqual(self.request("/api/eyes")[2], body)

    def test_world_image_and_session_scoped_bounded_inputs(self):
        import queue
        import numpy as np

        inputs = queue.Queue(maxsize=1)
        with patch("fly_dashboard.DEFAULT_PORT",0):
            dashboard = fly_dashboard.Dashboard(self.output / "app", self.metadata, inputs=inputs)
        self.addCleanup(dashboard.close)
        self.dashboard = dashboard
        dashboard.publish_world(np.zeros((6, 8, 3), dtype=np.uint8), 1.5)
        status, headers, body = self.request("/api/world")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "image/jpeg")
        self.assertTrue(body.startswith(b"\xff\xd8"))
        state = json.loads(self.request("/api/status")[2])
        self.assertTrue(state["interactive"])
        self.assertEqual(state["world_revision"], 1)
        self.assertEqual(state["world_time_s"], 1.5)
        headers = {
            "Origin": dashboard.url.rstrip("/"), "X-Fly-Session": dashboard.session_id,
            "Content-Type": "application/json",
        }
        event = {"kind": "key", "key": "P"}
        self.assertEqual(self.request("/api/input", "POST", headers, json.dumps(event))[0], 202)
        self.assertEqual(self.request("/api/input", "POST", headers, json.dumps(event))[0], 429)
        self.assertEqual(inputs.get_nowait(), event)
        for invalid in [{"kind": "key", "key": "W"}, {"kind": "pointer", "x": 2, "y": 0}]:
            self.assertEqual(self.request("/api/input", "POST", headers, json.dumps(invalid))[0], 400)
        wrong = {**headers, "X-Fly-Session": "stale"}
        self.assertEqual(self.request("/api/input", "POST", wrong, json.dumps(event))[0], 403)
        self.assertTrue(inputs.empty())

    def test_invalid_packets_leave_previous_state(self):
        self.dashboard.publish(self.packet())
        changes = [
            ("counts", [0, 3]), ("counts", [True, 2]),
            ("indices", [2, 0]), ("indices", [0, 0]), ("indices", [0, 3]),
            ("counts", [3]), ("network_spikes", 99), ("sequence", -1),
            ("episode", True), ("schema_version", True),
            ("start_ms", float("nan")), ("end_ms", -1), ("sequence", 2**53),
        ]
        for field, value in changes:
            with self.subTest(field=field, value=value):
                packet = self.packet()
                packet["neuron_activity"][field] = value
                with self.assertRaises(ValueError):
                    self.dashboard.publish(packet)
        for field, value in (
            ("brain_time_ms", float("inf")), ("habitat_time_s", -1), ("paused", 1),
            ("eye_time_s", float("nan")), ("status", 123), ("status", "x" * 129),
            ("brain_time_ms", 10**400),
        ):
            packet = self.packet()
            packet[field] = value
            with self.assertRaises(ValueError):
                self.dashboard.publish(packet)
        with patch.object(fly_dashboard, "MAX_STATE_BYTES", 100):
            with self.assertRaises(ValueError):
                self.dashboard.publish(self.packet())
        self.assertEqual(json.loads(self.request("/api/state")[2]), self.packet())

    def test_invalid_images_are_atomic(self):
        import numpy as np

        self.dashboard.publish(self.packet())
        for image in (np.zeros((2, 2)), np.zeros((2, 2, 4), dtype=np.uint8)):
            with self.assertRaises(ValueError):
                self.dashboard.publish(self.packet(2), image)
        with patch.object(fly_dashboard, "MAX_EYES_PIXELS", 1):
            with self.assertRaises(ValueError):
                self.dashboard.publish(self.packet(2), np.zeros((2, 2, 3), dtype=np.uint8))
        with patch.object(fly_dashboard, "MAX_EYES_BYTES", 1):
            with self.assertRaises(ValueError):
                self.dashboard.publish(self.packet(2), np.zeros((1, 1, 3), dtype=np.uint8))
        self.assertEqual(json.loads(self.request("/api/state")[2]), self.packet())
        self.assertEqual(self.request("/api/eyes")[0], 503)

    def test_read_only_routes_and_no_file_exposure(self):
        for path in (
            "/dashboard.json", "/dashboard.html", "/api", "/metadata",
            "/../README.md", "/%2e%2e/README.md", "/api/eyes/../../README.md",
            "//evil.example/api/state", "/favicon.ico", "/api/state%00",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 404)
        for method in ("POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE", "CONNECT"):
            with self.subTest(method=method):
                self.assertEqual(self.request("/api/state", method)[0], 405)
        self.assertEqual(self.request("/" + "a" * 2048)[0], 414)

    def test_rebinding_and_cross_origin_rejected(self):
        for headers in (
            {"Host": "evil.example"},
            {"Origin": "https://evil.example"},
            {"Origin": "null"},
            {"Sec-Fetch-Site": "cross-site"},
            {"Sec-Fetch-Site": "same-site"},
        ):
            with self.subTest(headers=headers):
                self.assertEqual(self.request("/api/metadata", headers=headers)[0], 403)
        self.assertEqual(
            self.request("/api/metadata", headers={"Origin": self.dashboard.url.rstrip("/")})[0],
            200,
        )

    def test_concurrent_latest_state_and_close(self):
        errors = []
        def producer():
            try:
                for sequence in range(30):
                    self.dashboard.publish(self.packet(sequence))
            except Exception as error:
                errors.append(error)
        thread = threading.Thread(target=producer)
        thread.start()
        for _ in range(10):
            status, _, body = self.request("/api/state")
            if status == 200:
                self.assertEqual(json.loads(body)["neuron_activity"]["counts"], [2, 1])
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        address = urlsplit(self.dashboard.url)
        # An incomplete client must not prevent shutdown.
        with socket.create_connection((address.hostname, address.port), timeout=2) as idle:
            idle.sendall(b"GET / HTTP/1.1\r\n")
            start = time.monotonic()
            self.dashboard.close()
            self.assertLess(time.monotonic() - start, 2)
        self.assertFalse(self.dashboard._thread.is_alive())
        self.dashboard.close()
        self.assertEqual(
            json.loads((self.output / "dashboard.json").read_text()),
            {"url": self.dashboard.url, "status": "closed", "session_id": self.dashboard.session_id},
        )
        with self.assertRaises(RuntimeError):
            self.dashboard.publish(self.packet())
        with self.assertRaises(OSError):
            socket.create_connection((address.hostname, address.port), timeout=0.2)

    def test_context_exception_closes(self):
        with self.assertRaisesRegex(RuntimeError, "caller failure"):
            with self.dashboard as dashboard:
                self.assertIs(dashboard, self.dashboard)
                raise RuntimeError("caller failure")
        self.assertEqual(json.loads((self.output / "dashboard.json").read_text())["status"], "closed")
        with self.assertRaises(RuntimeError):
            self.dashboard.__enter__()

    def test_metadata_validation_and_bounds(self):
        for change in (
            {"neuron_ids": [123]}, {"neuron_ids": ["a", "a"]},
            {"input_ids": [123]}, {"mn9_id": 123}, {"other": float("nan")},
        ):
            metadata = {**self.metadata, **change}
            with self.assertRaises(ValueError):
                fly_dashboard.Dashboard(self.output, metadata)
        with patch.object(fly_dashboard, "MAX_METADATA_BYTES", 10):
            with self.assertRaises(ValueError):
                fly_dashboard.Dashboard(self.output, self.metadata)

    def test_explicit_port_conflict_never_selects_another_port(self):
        port = urlsplit(self.dashboard.url).port
        with self.assertRaisesRegex(RuntimeError, "already in use"):
            fly_dashboard.Dashboard(self.output / "second", self.metadata, port=port)
        for invalid in [True, -1, 65536, 1.5]:
            with self.assertRaises(ValueError):
                fly_dashboard.Dashboard(self.output / "invalid", self.metadata, port=invalid)
        self.assertFalse((self.output / "second").exists())

    def test_restarting_reuses_address_with_new_session_identity(self):
        old_url, old_session = self.dashboard.url, self.dashboard.session_id
        port = urlsplit(old_url).port
        self.dashboard.close()
        self.dashboard = fly_dashboard.Dashboard(self.output / "restarted", self.metadata, port=port)
        self.addCleanup(self.dashboard.close)
        self.assertEqual(self.dashboard.url, old_url)
        self.assertNotEqual(self.dashboard.session_id, old_session)
        self.assertEqual(json.loads(self.request("/api/status")[2])["session_id"], self.dashboard.session_id)

    def test_verified_connection_endpoint_and_invalid_queries(self):
        from fly_connections import ConnectionIndex, write_index

        ids = ["9007199254740993001", "9007199254740993002"]
        directory = self.output / "index"
        directory.mkdir()
        table = {
            "Presynaptic_ID": [int(ids[0])], "Postsynaptic_ID": [int(ids[1])],
            "Presynaptic_Index": [0], "Postsynaptic_Index": [1],
            "Connectivity": [7], "Excitatory x Connectivity": [-7],
        }
        write_index(directory, table, ids, "verified", "source")
        index = ConnectionIndex(directory, ids, "verified")
        metadata = {"neuron_ids": ids, "upstream_commit": "verified"}
        dashboard = fly_dashboard.Dashboard(self.output / "connections", metadata, connections=index)
        self.addCleanup(dashboard.close)
        self.dashboard = dashboard
        status, _, body = self.request("/api/connections?id=" + ids[1] + "&direction=incoming")
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["edges"][0], {
            "source_id": ids[0], "target_id": ids[1], "contacts": 7, "signed_contacts": -7,
        })
        self.assertTrue(json.loads(self.request("/api/status")[2])["connections_available"])
        for query in ["", "id=missing&direction=incoming", f"id={ids[1]}&direction=incoming&limit=101",
                      f"id={ids[1]}&direction=incoming&id={ids[0]}", f"id={ids[1]}&direction=incoming&file=secret"]:
            with self.subTest(query=query):
                self.assertEqual(self.request("/api/connections?" + query)[0], 400)

    def test_constructor_failure_releases_socket(self):
        servers = []
        original = fly_dashboard.ThreadingHTTPServer
        def server(*args, **kwargs):
            result = original(*args, **kwargs)
            servers.append(result)
            return result
        with patch.object(fly_dashboard, "ThreadingHTTPServer", side_effect=server):
            with patch.object(fly_dashboard.Dashboard, "_write_status", side_effect=OSError("disk")):
                with self.assertRaises(OSError):
                    fly_dashboard.Dashboard(self.output, self.metadata)
        self.assertEqual(servers[0].fileno(), -1)

    def test_closed_manifest_can_retry_after_disk_failure(self):
        with patch.object(self.dashboard, "_write_status", side_effect=OSError("disk")):
            with self.assertRaises(OSError):
                self.dashboard.close()
        self.assertFalse(self.dashboard._thread.is_alive())
        self.dashboard.close()
        self.assertEqual(json.loads((self.output / "dashboard.json").read_text())["status"], "closed")

    @unittest.skipUnless(shutil.which("node"), "Node is optional for browser logic tests")
    def test_browser_activity_history_selection_gaps_and_reset(self):
        html = Path(fly_dashboard.__file__).with_name("dashboard.html").read_text()
        script = html.split("<script>", 1)[1].split("</script>", 1)[0]
        harness = r"""
const vm = require('node:vm'), assert = require('node:assert/strict');
const nodes = new Map();
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {
    textContent:'', value:id==='filter'?'all':'', children:[], hidden:false, style:{},
    clientWidth:800,clientHeight:490,
    attributes:{},setAttribute(name,value){this.attributes[name]=value;},
    classList:{values:new Set(),contains(name){return this.values.has(name);},
      add(name){this.values.add(name);},remove(...names){for(const name of names)this.values.delete(name);},
      toggle(name,force){const enabled=force===undefined?!this.values.has(name):force;
        if(enabled)this.values.add(name);else this.values.delete(name);return enabled;}},
    replaceChildren(){this.children=[];},append(child){this.children.push(child);},
    listeners:{},addEventListener(name,handler){this.listeners[name]=handler;},removeAttribute(){},focus(){},
    getBoundingClientRect(){return {left:0,top:0,width:800,height:490};},
    getContext(){return new Proxy({}, {get:(obj,key)=>obj[key]||(()=>{})});}
  });
  return nodes.get(id);
}
const sandbox = {
  console,process,Map,Set,Blob,TextDecoder,AbortController,
  document:{listeners:{},addEventListener(name,fn){this.listeners[name]=fn;},getElementById:node,createElement:()=>({textContent:'',children:[],append(child){this.children.push(child);}})},
  window:{devicePixelRatio:1,addEventListener(){}},
  ResizeObserver:class {observe(){}},performance:{now:()=>0},
  requestAnimationFrame:fn=>fn(),
  setTimeout:()=>1,clearTimeout(){},
  fetch:()=>new Promise(()=>{}),
  URL:{createObjectURL:()=>'blob:eye-test',revokeObjectURL(){}},
  assert
};
vm.createContext(sandbox);
vm.runInContext(SOURCE, sandbox);
vm.runInContext(`
const neuronIDs=Array.from({length:127400},(_,i)=>String(9007199254740993001n+BigInt(i)));
loadMetadata({neuron_ids:neuronIDs,mn9_id:neuronIDs[0],gf_ids:[neuronIDs[1]],input_ids:[neuronIDs[2]],visual_input_ids:[],snapshot:{upstream_commit:'real-commit'}});
assert.equal(ids.length,127400);
function packet(seq,ep=0,indices=[0,2],counts=[2,1]) {
  return {neuron_activity:{schema_version:1,episode:ep,sequence:seq,start_ms:seq*10,end_ms:seq*10+10,indices,counts,network_spikes:counts.reduce((a,b)=>a+b,0)},
    brain_time_ms:seq*10+10,habitat_time_s:1,eye_time_s:.75,paused:false,status:'running'};
}
receive(packet(1));choose(0);
assert.match($('connection-status').textContent,/index unavailable/);
assert.match($('count-scale').textContent,/Maximum interval count 2/);
assert.ok($('count-scale').textContent.includes('31+ = brightest mint'));
assert.equal($('selected-id').textContent,neuronIDs[0]);
assert.equal($('selected-labels').textContent,'MN9');
assert.equal($('selected-count').textContent,'2');
assert.equal(history.length,1);
receive(packet(1));assert.equal(history.length,1);
receive(packet(4,0,[1],[9]));
assert.match($('count-scale').textContent,/Maximum interval count 9/);
assert.equal(history.length,2);assert.equal(skipped,2);
assert.match($('gap-status').textContent,/Skipped sequences since joining this episode at #1: 2/);
assert.match($('history').children[0].textContent,/GAP: 2/);
assert.equal($('selected-count').textContent,'0');
choose(1);assert.equal($('selected-count').textContent,'9');
assert.match($('history').children[0].textContent,/: 9/);
assert.match($('history').children[1].textContent,/: 0/);
receive({...packet(4,0,[1],[9]),status:'finished',paused:true});
assert.equal(history.length,2);
assert.match($('pause-status').textContent,/finished.*paused/);
assert.match($('eye-clock').textContent,/0.750 s/);
$('neuron-id').value=neuronIDs[2];$('search').onsubmit({preventDefault(){}});
assert.equal(selected,2);assert.equal($('selected-labels').textContent,'input');
assert.equal($('selected-count').textContent,'0');
assert.match($('history').children[1].textContent,/: 1/);
receive({op:'reset',brain_time_ms:0,neuron_activity:{schema_version:1,episode:1,sequence:0,start_ms:0,end_ms:0,indices:[],counts:[],network_spikes:0}});
assert.equal(history.length,0);assert.equal(skipped,0);assert.equal($('selected-count').textContent,'0');
assert.match($('count-scale').textContent,/Maximum interval count 0/);
assert.match($('eye-clock').textContent,/0.750 s/);
receive({op:'reset',brain_time_ms:0,neuron_activity:{schema_version:1,episode:1,sequence:0,start_ms:0,end_ms:0,indices:[],counts:[],network_spikes:0}});
assert.equal(history.length,0);
for(let i=1;i<=50;i++) receive(packet(i,1));
assert.equal(history.length,40);assert.equal(history[0].sequence,11);
choose(0);unavailable('disconnected');
assert.equal($('selected-count').textContent,'unavailable');
assert.equal($('network-count').textContent,'unavailable');
assert.match($('count-scale').textContent,/Maximum interval count unavailable/);
assert.equal(history.length,40);
assert.match($('interval-label').textContent,/previously received data/);
receive(packet(50,1));assert.equal(history.length,40);
assert.equal($('selected-count').textContent,'2');
assert.equal(idIndex.get(neuronIDs[127399]),127399);
const late=packet(166,2);
late.neuron_activity.start_ms=2755.4999999999964;
late.neuron_activity.end_ms=2772.199999999996;
receive(late);choose(0);
assert.equal(skipped,0);assert.equal(history[0].gap,0);
assert.match($('gap-status').textContent,/joining this episode at #166: 0/);
assert.match($('interval-label').textContent,/2755\.5–2772\.2 ms/);
assert.match($('history').children[0].textContent,/2755\.5–2772\.2 ms/);
receive(late);assert.equal(history.length,1);assert.equal(skipped,0);
receive(packet(169,2));assert.equal(skipped,2);
assert.match($('gap-status').textContent,/joining this episode at #166: 2/);
assert.match($('history').children[0].textContent,/GAP: 2/);
receive(packet(99,3));assert.equal(skipped,0);assert.equal(joinedAt,99);
adoptSession('new-session');
assert.equal(history.length,0);assert.equal(latest,null);assert.equal(selected,null);
assert.equal(metadataReady,false);assert.equal(eyeTime,null);assert.equal($('selected-id').textContent,'—');
loadMetadata({neuron_ids:neuronIDs,mn9_id:neuronIDs[0],gf_ids:[],input_ids:[],visual_input_ids:[],upstream_commit:'real-commit'});
$('filter').value='circuit';choose(1);assert.equal($('filter').value,'all');
receive(packet(1));adoptSession('new-session');assert.equal(history.length,1);
adoptSession('another-session');assert.equal(history.length,0);assert.equal(metadataReady,false);
loadMetadata({neuron_ids:neuronIDs,mn9_id:neuronIDs[0],gf_ids:[],input_ids:[],visual_input_ids:[],upstream_commit:'real-commit'});
let pointerSchedules=0;
setTimeout=()=>{pointerSchedules++;return pointerSchedules;};
pointerTimer=null;inputBusy=false;pendingPointer=null;worldDrag=null;
for(let i=0;i<100;i++) ground.listeners.pointermove({clientX:i,clientY:100});
assert.equal(pointerSchedules,1,'Continuous motion must not postpone the scheduled update');
assert.equal(pendingPointer.x,99/800);
shell.classList.add('immersive');
$('world').naturalWidth=1280;$('world').naturalHeight=960;
const covered=groundImageRect();
assert.equal(covered.width,800);assert.equal(covered.height,600);
assert.equal(covered.left,0);assert.equal(covered.top,-55);
pendingPointer=null;
ground.listeners.pointermove({clientX:-10,clientY:100});
assert.equal(pendingPointer,null,'Outside-image coordinates cannot move the physical pointer');
ground.listeners.pointermove({clientX:0,clientY:0});
assert.equal(pendingPointer.x,0);assert.equal(pendingPointer.y,55/600,'Crop must preserve source-image coordinates');
ground.listeners.pointermove({clientX:covered.left+covered.width/2,clientY:245});
assert.equal(pendingPointer.x,.5);assert.equal(pendingPointer.y,.5);
document.fullscreenElement=shell;document.listeners.fullscreenchange();
assert.equal($('app-fullscreen').textContent,'Exit fullscreen');
assert.equal($('overlay-eyes').attributes['aria-pressed'],'true');
assert.equal($('overlay-neural').attributes['aria-pressed'],'true');
$('overlay-inspect').onclick();assert.ok(shell.classList.contains('inspect-neural'));
assert.equal($('overlay-inspect').attributes['aria-pressed'],'true');
fit();assert.equal(autoFit,true);
canvas.clientHeight=240;resize();
assert.ok(Math.abs(view.scale-Math.min(800/400,240/319)*.94)<1e-9,'Fitted map follows panel resizing');
zoom(2);const userScale=view.scale;
canvas.clientHeight=300;resize();assert.equal(view.scale,userScale,'User zoom is preserved across resizes');
canvas.clientHeight=0;resize();assert.equal(view.scale,userScale,'Hidden map cannot reset a valid view');
canvas.clientHeight=490;
$('overlay-eyes').onclick();assert.ok(shell.classList.contains('hide-eyes'));
assert.equal($('overlay-eyes').attributes['aria-pressed'],'false');
$('overlay-eyes').onclick();assert.ok(!shell.classList.contains('hide-eyes'));
document.fullscreenElement=null;document.listeners.fullscreenchange();
assert.ok(!shell.classList.contains('immersive'));
loadMetadata({neuron_ids:neuronIDs,mn9_id:neuronIDs[0],gf_ids:[],input_ids:[],visual_input_ids:[],upstream_commit:'real-commit',fly_count:3});
assert.equal($('fly-count').value,'3');assert.equal($('observed-fly').children.length,3);
assert.equal($('fly-observer').hidden,false);
receive({...packet(10),observed_fly_id:1});receive({...packet(10),observed_fly_id:2});
assert.equal(observedFly,2);assert.equal(history.length,1,'Switching fly cannot mix histories');
assert.match($('eyes-heading').textContent,/Fly 2/);
activitySummary({episode:0,observed_fly_id:1,episode_spikes:999,active_intervals:1,last_firing:null});
assert.equal(lastFiring,null,'Other fly summaries cannot appear in selected fly');
loadMetadata({neuron_ids:neuronIDs,mn9_id:neuronIDs[0],gf_ids:[],input_ids:[],visual_input_ids:[],upstream_commit:'real-commit'});
receive({...packet(1),status:'safety stopped',interaction_error:'Boundary safety stop. Reset to restart.'});
assert.match($('input-status').textContent,/Simulation safety stop/);
assert.ok(!$('input-status').textContent.includes('Edit rejected'));
receive(packet(2));
activitySummary({episode:0,episode_spikes:12,active_intervals:1,last_firing:{
  episode:0,sequence:1,start_ms:0,end_ms:10,indices:[0,2],counts:[9,3]}});
assert.match($('activity-summary').textContent,/12 network spikes/);
$('activity-last').onclick();
choose(0);assert.equal($('selected-count').textContent,'9');
assert.match($('activity-display-status').textContent,/HISTORICAL.*not current/);
$('activity-live').onclick();assert.equal($('selected-count').textContent,'2');
loadMetadata({neuron_ids:neuronIDs,mn9_id:neuronIDs[0],gf_ids:[],input_ids:[],visual_input_ids:[],upstream_commit:'real-commit',
  sensorimotor_candidates:[{root_id:neuronIDs[2],population:'DNa04',cell_type:'DNae004',hemibrain_type:'DNa04',side:'left',ambiguous_type_correspondence:true}]});
receive(packet(3));choose(2);
assert.equal($('sensorimotor-panel').hidden,false);
assert.match($('selected-labels').textContent,/AMBIGUOUS/);
assert.equal($('selected-count').textContent,'1');
assert.match($('sensorimotor-cells').children[0].children[0].textContent,/1 displayed spikes.*AMBIGUOUS/);
loadMetadata({neuron_ids:neuronIDs,mn9_id:neuronIDs[0],gf_ids:[],input_ids:[],visual_input_ids:[],upstream_commit:'real-commit',
  walking_readouts_enabled:true,
  sensorimotor_candidates:[{root_id:neuronIDs[2],population:'BDN2',cell_type:'DNge162',hemibrain_type:'',side:'left',ambiguous_type_correspondence:false}]});
receive(packet(4));choose(2);
assert.match($('sensorimotor-title').textContent,/Walking, stopping/);
assert.match($('selected-labels').textContent,/BDN2/);
assert.equal($('selected-count').textContent,'1');
loadMetadata({neuron_ids:neuronIDs,mn9_id:neuronIDs[0],gf_ids:[],input_ids:[],visual_input_ids:[],upstream_commit:'real-commit'});
assert.match($('sensorimotor-title').textContent,/^Steering and landing/);
`,sandbox);
vm.runInContext(`
(async()=>{
  const originalFetchBounded=fetchBounded;
  let imageRequests=0,revision=0,available=false;
  json=async()=>({eyes_available:available,eyes_revision:revision});
  fetchBounded=async()=>{
    imageRequests++;
    return new Blob(['png'],{type:'image/png'});
  };
  for(let i=0;i<5;i++) await refreshEyes();
  assert.equal(imageRequests,0);
  assert.equal($('eyes').hidden,true);
  available=true;revision=1;eyeTime=null;
  await refreshEyes();
  assert.equal(imageRequests,1);
  assert.equal($('eyes').hidden,false);
  for(let i=0;i<5;i++) await refreshEyes();
  assert.equal(imageRequests,1);
  revision=2;await refreshEyes();
  assert.equal(imageRequests,2);
  clearEyes('disconnected');await refreshEyes();
  assert.equal(imageRequests,3);
  selected=0;connectionsAvailable=true;
  json=async(path)=>{
    const direction=path.includes('direction=incoming')?'incoming':'outgoing';
    return {neuron_id:ids[0],direction,upstream_commit:'real-commit',offset:0,total:1,
      edges:[{source_id:ids[0],target_id:ids[1],contacts:7,signed_contacts:-7}]};
  };
  await inspectConnections();
  assert.equal(connectionPages.incoming.edges[0].contacts,7);
  assert.match($('outgoing-edges').children[0].children[0].textContent,/7 contacts.*signed -7/);
  assert.equal($('outgoing-next').disabled,true);
  unavailable('closed');assert.equal(connectionPages.incoming,null);
  const previousRequest=connectionRequest;
  receive(packet(2));assert.ok(connectionRequest>previousRequest);
  await inspectConnections();
  assert.equal(connectionPages.incoming.edges[0].contacts,7);
  fetch=async()=>({ok:true,headers:{get:()=> 'different-session'}});
  await assert.rejects(()=>originalFetchBounded('/api/state',1024),/Session changed during request/);
})().catch(error=>{console.error(error);process.exitCode=1;});
`,sandbox);
"""
        result = subprocess.run(
            ["node", "-"], input=harness.replace("SOURCE", json.dumps(script)),
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
