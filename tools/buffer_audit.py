"""Read-only: list what Buffer sent (or still holds) per channel in the last N days and flag duplicates.
Run by .github/workflows/buffer_audit.yml (manual)."""
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from factory.publish import _gql  # noqa: E402

DAYS = int(os.environ.get("DAYS", "3"))
Q = """query($o: OrganizationId!, $c: [ChannelId!], $s: [PostStatus!]) {
  posts(input: {organizationId: $o, sort: [{field: createdAt, direction: desc}],
                filter: {status: $s, channelIds: $c}}, first: 40) {
    edges { node { id text createdAt dueAt sentAt status externalLink error { message } } } } }"""


def main():
    problems = []
    since = datetime.now(timezone.utc) - timedelta(days=DAYS)
    orgs = _gql("query { account { organizations { id name } } }")["account"]["organizations"]
    for org in orgs:
        chans = _gql("""query($o: OrganizationId!) { channels(input: {organizationId: $o}) {
                       id name service isLocked } }""", {"o": org["id"]})["channels"]
        for ch in chans:
            print(f"\n== {ch['service']} / {ch['name']} ({'locked' if ch['isLocked'] else 'active'})")
            for status in (["sent"], ["error"], ["scheduled", "sending"]):
                try:
                    edges = _gql(Q, {"o": org["id"], "c": [ch["id"]], "s": status})["posts"]["edges"]
                except Exception as e:  # noqa: BLE001
                    print(f"  ({status}) query failed: {e}")
                    continue
                seen = defaultdict(list)
                for e in edges:
                    n = e["node"]
                    when = datetime.fromisoformat((n.get("sentAt") or n.get("dueAt") or n["createdAt"]).replace("Z", "+00:00"))
                    if when < since:
                        continue
                    first = (n.get("text") or "").split("\n")[0][:60]
                    seen[first].append(n)
                    err = (n.get("error") or {}).get("message", "")
                    print(f"  {n['status']:9} sent {n.get('sentAt') or '-':24} created {n['createdAt'][:16]}  "
                          f"{first}  {n.get('externalLink') or ''} {err[:60]}")
                    if status == ["error"] and when > datetime.now(timezone.utc) - timedelta(hours=26):
                        problems.append(f"{ch['service']}: not posted - {first[:40]}... ({err[:70]})")
                for first, ns in seen.items():
                    if len(ns) > 1:
                        print(f"  !! DUPLICATE x{len(ns)}: {first}  ids {[x['id'] for x in ns]}")
                        if first.strip() and status == ["sent"]:  # empty text = Instagram stories, not ours
                            problems.append(f"{ch['service']}: posted {len(ns)} times - {first[:40]}...")
    if problems and os.environ.get("ALERT") == "true":
        from factory.common import load_config
        from factory.notify import send_text
        send_text(load_config(), "Monezic daily check - needs a look:\n- " + "\n- ".join(problems))
    print("\nProblems:", problems or "none")


if __name__ == "__main__":
    main()
