"""06 — Blockchain anchor: commit a trust anchor and verify the whole history.

Run from the repo root with the arxdb env active:

    python examples/06-blockchain-anchor/anchor.py

The anchor is a single self-describing record (Merkle root + entry count +
timestamp + roster hash) that an external party can commit to a blockchain.
From *only* that record, anyone can later verify the entire history — no trust
in the local database.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from arxdb.attestation.attest import anchor, commit_roster, verify_history
from arxdb.attestation.roster import Roster
from arxdb.storage.hashing import hash_bytes
from arxdb.storage.keys import generate_keypair
from arxdb.storage.storage import Storage
from arxdb.verification.commit import verify_and_commit
from arxdb.verification.schema import EdgeType, Node


def main() -> None:
    priv, pub = generate_keypair()
    roster = Roster(entries={"skye": pub})

    with TemporaryDirectory() as tmp:
        store = Storage(Path(tmp), priv, pub)

        # 1. Commit the roster as the genesis log entry (entry 0). The Merkle
        #    root therefore transitively commits to the roster.
        commit_roster(store, roster)

        # 2. Commit some reasoning.
        a = Node(claim="x > 0", domain="math")
        b = Node(claim="x + 1 > 0", domain="math")
        verify_and_commit(store, pub, [a], b, "add 1", EdgeType.DEDUCTION)

        # 3. Build the anchor record — the single thing to put on a blockchain.
        rec = anchor(store, roster)
        print(f"[anchor] root_hash={rec.root_hash.hex()[:16]}... "
              f"entries={rec.entry_count} roster_hash={rec.roster_hash.hex()[:16]}...")

        # 4. Verify the whole history from *only* the trusted root.
        ok = verify_history(store, rec.root_hash)
        print(f"[verify]  correct root -> {ok}")

        # 5. A forged root fails.
        forged = hash_bytes(b"a forged root")
        bad = verify_history(store, forged)
        print(f"[verify]  forged root  -> {bad}")

        store.close()


if __name__ == "__main__":
    main()
