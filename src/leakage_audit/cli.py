import argparse
import json
from pathlib import Path
from .audit import AuditConfig, audit, read_csv

def main(argv=None):
    p = argparse.ArgumentParser(description="Audit train/test CSV split integrity")
    p.add_argument("train")
    p.add_argument("test")
    p.add_argument("--target", required=True)
    p.add_argument("--entity")
    p.add_argument("--time")
    p.add_argument("--embargo-seconds", type=float, default=0)
    p.add_argument("--output")
    p.add_argument("--fail-on-high", action="store_true")
    args = p.parse_args(argv)
    try:
        result = audit(read_csv(args.train), read_csv(args.test), AuditConfig(args.target,args.entity,args.time,args.embargo_seconds))
    except (ValueError, OSError) as e:
        p.error(str(e))
    content = json.dumps(result, indent=2, allow_nan=False)+"\n"
    if args.output:
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 1 if args.fail_on_high and any(f["severity"]=="high" for f in result["findings"]) else 0

if __name__ == "__main__":
    raise SystemExit(main())
