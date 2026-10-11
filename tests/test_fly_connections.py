import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fly_connections import ConnectionIndex, write_index


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name)
        self.ids = ["900719925474099300", "900719925474099301", "900719925474099302"]
        self.table = {
            "Presynaptic_ID": [int(self.ids[1]), int(self.ids[0]), int(self.ids[0])],
            "Postsynaptic_ID": [int(self.ids[2]), int(self.ids[2]), int(self.ids[1])],
            "Presynaptic_Index": [1, 0, 0], "Postsynaptic_Index": [2, 2, 1],
            "Connectivity": [7, 3, 2], "Excitatory x Connectivity": [-7, 3, 2],
        }
        write_index(self.path, self.table, self.ids, "commit", "source")
        self.index = ConnectionIndex(self.path, self.ids, "commit")

    def test_exact_incoming_outgoing_and_pagination(self):
        incoming = self.index.lookup(self.ids[2], "incoming", limit=1)
        self.assertEqual(incoming["total"], 2)
        self.assertEqual(incoming["edges"], [{
            "source_id": self.ids[0], "target_id": self.ids[2], "contacts": 3, "signed_contacts": 3,
        }])
        second = self.index.lookup(self.ids[2], "incoming", offset=1, limit=1)
        self.assertEqual(second["edges"][0]["signed_contacts"], -7)
        self.assertEqual(self.index.lookup(self.ids[0], "outgoing")["total"], 2)
        self.assertEqual(self.index.lookup(self.ids[2], "outgoing")["edges"], [])
        self.assertEqual(self.index.lookup(self.ids[0], "outgoing", offset=100)["edges"], [])

    def test_invalid_ids_limits_and_directions(self):
        for args in [("missing", "incoming"), (self.ids[0], "electrical"), (self.ids[0], "incoming", -1),
                     (self.ids[0], "incoming", 0, 101), (self.ids[0], "incoming", True)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.index.lookup(*args)

    def test_snapshot_and_checksums_rejected(self):
        with self.assertRaises(ValueError):
            ConnectionIndex(self.path, self.ids[::-1], "commit")
        with self.assertRaises(ValueError):
            ConnectionIndex(self.path, self.ids, "other")
        with (self.path / "edges.npy").open("ab") as stream:
            stream.write(b"corruption")
        with self.assertRaisesRegex(ValueError, "checksum"):
            ConnectionIndex(self.path, self.ids, "commit")

    def test_source_index_identity_mismatch_rejected(self):
        self.table["Presynaptic_ID"][0] = int(self.ids[0])
        with self.assertRaisesRegex(ValueError, "identities"):
            write_index(self.path, self.table, self.ids, "commit", "source")


if __name__ == "__main__":
    unittest.main()
