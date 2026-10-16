import argparse
import json
import hashlib
from pathlib import Path
from .audit import AuditConfig, audit, read_csv

def source_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()

def main(argv=None):
    p = argparse.ArgumentParser(description="Audit train/test CSV split integrity")
    p.add_argument("train")
    p.add_argument("test")
    p.add_argument("--target", required=True)
    p.add_argument("--entity")
    p.add_argument("--time")
    p.add_argument("--numeric-duplicate-columns", nargs='+', default=[],
                   help="Explicit numeric features to normalize for duplicate comparison; categorical IDs stay exact")
    p.add_argument("--check-target-quality", action='store_true',
                   help="Opt in to missing/conflicting label diagnostics, including heldout labels; never fits proxy scores")
    p.add_argument("--check-near-duplicates", action='store_true',
                   help="Review feature vectors differing in exactly one feature (2 to 64 features); excludes exact matches")
    p.add_argument("--embargo-seconds", type=float, default=0)
    p.add_argument("--output")
    p.add_argument("--fail-on-high", action="store_true")
    args = p.parse_args(argv)
    try:
        before = {name: source_hash(path) for name, path in [('train', args.train), ('test', args.test)]}
        result = audit(read_csv(args.train), read_csv(args.test), AuditConfig(args.target,args.entity,args.time,args.embargo_seconds,
                       numeric_duplicate_columns=tuple(args.numeric_duplicate_columns), check_target_quality=args.check_target_quality,
                       check_near_duplicates=args.check_near_duplicates))
        after = {name: source_hash(path) for name, path in [('train', args.train), ('test', args.test)]}
        if before != after:
            raise ValueError('Input source changed during audit; no report emitted')
        result['inputs'] = {name: {'filename': Path(path).name, 'sha256': before[name]}
                            for name, path in [('train', args.train), ('test', args.test)]}
    except (ValueError, OSError) as e:
        p.error(str(e))
    content = json.dumps(result, indent=2, allow_nan=False)+"\n"
    if args.output:
        destination = Path(args.output)
        try:
            if any(destination.resolve()==Path(source).resolve() or (destination.exists() and destination.samefile(source)) for source in (args.train,args.test)):
                p.error("Output path must not overwrite either input dataset")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")
        except OSError as error:
            p.error(str(error))
    else:
        print(content, end="")
    return 1 if args.fail_on_high and any(f["severity"]=="high" for f in result["findings"]) else 0

if __name__ == "__main__":
    raise SystemExit(main())
