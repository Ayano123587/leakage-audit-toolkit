"""Run reproducible real-data diagnostics; this toolkit does not train a model."""
import argparse
from pathlib import Path
from leakage_audit.adult_validation import validate as adult
from leakage_audit.near_validation import validate as near


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='data/interim/evaluation/adult-audit.json')
    parser.add_argument('--near-duplicates',action='store_true',
                        help='Validate one-feature near matches after the official Adult data workflow')
    args=parser.parse_args()
    output=Path(args.output)
    if output.exists():parser.error('Preserve existing evidence; choose a new --output path')
    output.parent.mkdir(parents=True,exist_ok=True)
    if args.near_duplicates:near(report=output)
    else:adult(report=output)


if __name__=='__main__':main()
