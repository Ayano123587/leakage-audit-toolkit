"""Render a compact finding histogram from a JSON report, without dependencies."""
import json
from collections import Counter
from pathlib import Path
import argparse

def main():
    parser=argparse.ArgumentParser();parser.add_argument("report");args=parser.parse_args()
    report=json.loads(Path(args.report).read_text())
    for kind,count in sorted(Counter(f["kind"] for f in report["findings"]).items()):
        print(f"{kind:26} {'#'*count} ({count})")
if __name__ == "__main__": main()
