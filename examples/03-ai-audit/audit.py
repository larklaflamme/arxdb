"""03 — AI audit: verify an AI's reasoning chain, then detect tampering.

Run from the repo root with the arxdb env active:

    python examples/03-ai-audit/audit.py

The scenario: an AI assistant produces a multi-step reasoning chain. Each step
is committed as a signed edge with its proof (the reasoning trace) bound to it.
An auditor then verifies the three guarantees:

  - provenance  — who signed it (a *named* agent via the roster)
  - integrity   — has it been altered (signature + hash chain)
  - binding     — is the proof bound to this edge and intact

Then we tamper with a proof blob and show the audit catches it.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from arxdb.attestation.attest import verify_edge_attestation
from arxdb.attestation.roster import Roster
from arxdb.storage.keys import generate_keypair
from arxdb.storage.storage import Storage
from arxdb.verification.commit import verify_and_commit
from arxdb.verification.schema import EdgeType, Node


def main() -> None:
    # The AI model holds its own keypair; the roster binds that key to a name.
    ai_priv, ai_pub = generate_keypair()
    roster = Roster(entries={"assistant-model": ai_pub})

    with TemporaryDirectory() as tmp:
        store = Storage(Path(tmp), ai_priv, ai_pub)

        # The AI's reasoning chain: A -> B -> C. Each step carries a proof
        # blob (the model's reasoning trace), bound to the edge by its hash.
        a = Node(claim="x > 0", domain="math")
        b = Node(claim="x + 1 > 0", domain="math")
        c = Node(claim="x + 2 > 0", domain="math")

        proof1 = b"step 1: add 1 to both sides of x > 0"
        proof2 = b"step 2: add 1 to both sides of x + 1 > 0"

        r1 = verify_and_commit(
            store, ai_pub, [a], b, "add 1", EdgeType.CITATION, proof_bytes=proof1,
        )
        r2 = verify_and_commit(
            store, ai_pub, [b], c, "add 1", EdgeType.CITATION, proof_bytes=proof2,
        )

        # Audit each edge: provenance + integrity + binding.
        for label, r in (("step 1", r1), ("step 2", r2)):
            att = verify_edge_attestation(r.edge, store, roster)
            print(f"[{label}] signer={att.signer_agent_id} "
                  f"signature_valid={att.signature_valid} "
                  f"proof_bound={att.proof_bound} "
                  f"proof_intact={att.proof_intact} ok={att.ok}")

        # Tamper: overwrite the proof blob for step 1 with different bytes.
        # The content address no longer matches the stored bytes, so the
        # binding check fails.
        proof_path = store.objects._path(r1.edge.proof_hash)
        proof_path.write_bytes(b"tampered proof")
        att = verify_edge_attestation(r1.edge, store, roster)
        print(f"[tampered] proof_intact={att.proof_intact} ok={att.ok}")

        store.close()


if __name__ == "__main__":
    main()
