# /// script
# requires-python = ">=3.9"
# dependencies = ["nameparser==1.4.*"]
# ///
"""v1 worker: reads JSON name strings on stdin (one per line), writes
the 1.4 component dict per line. Run ONLY via:

    uv run --no-project tools/differential/worker_v1.py

--no-project is load-bearing: without it uv installs the working tree
and shadows the 1.4 pin from PyPI.
"""
import json
import sys

from nameparser import HumanName

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    name = json.loads(line)
    n = HumanName(name)
    print(json.dumps({k: v or "" for k, v in n.as_dict().items()},
                      ensure_ascii=False), flush=True)
