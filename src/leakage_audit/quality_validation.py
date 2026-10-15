"""Real Wine controls and explicitly injected representation/label-quality defects."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
from .audit import AuditConfig, audit
from .wine_validation import load_wine, split_wine, COLUMNS


def validate(directory='data/external/wine', report='docs/quality-validation-results.json'):
    rows, provenance = load_wine(directory)
    config = AuditConfig('target', numeric_duplicate_columns=tuple(COLUMNS[1:]), check_target_quality=True)
    controls = []
    for seed in range(20):
        train, test = split_wine(rows, seed)
        findings = audit(train, test, config)['findings']
        controls.append({'seed': seed, 'finding_count': len(findings), 'kinds': sorted({f['kind'] for f in findings})})
    train, test = split_wine(rows, 42)
    for index in range(5):
        for column in COLUMNS[1:]:
            test[index][column] = format(Decimal(train[index][column]), 'E')
    exact = audit(train, test, AuditConfig('target'))
    normalized = audit(train, test, config)
    duplicate_rows = lambda result: next((f['evidence']['test_rows'] for f in result['findings'] if f['kind'] == 'cross_split_duplicates'), 0)
    tr, te = split_wine(rows, 42)
    repeated = deepcopy(tr[0])
    repeated['target'] = 'deliberately_conflicting_label'
    tr.append(repeated)
    conflicting = audit(tr, te, config)
    tr, te = split_wine(rows, 42)
    tr[0]['target'], te[0]['target'] = None, 'Infinity'
    quality = audit(tr, te, config)
    result = {'dataset': provenance, 'controls': controls,
              'unmodified_controls_flagged': sum(bool(x['finding_count']) for x in controls),
              'controlled_injections': [
                  {'case': 'five training feature vectors copied into test with scientific numeric formatting',
                   'expected_rows': 5, 'default_exact_detected': duplicate_rows(exact),
                   'explicit_numeric_detected': duplicate_rows(normalized)},
                  {'case': 'one repeated training feature vector with a contradictory label',
                   'detected': any(f['kind'] == 'within_train_label_conflicts' for f in conflicting['findings'])},
                  {'case': 'one missing training label and one nonfinite test label',
                   'detected': any(f['kind'] == 'target_quality' for f in quality['findings'])}],
              'limitations': ['Controlled defects on authentic source rows are not naturally occurring leakage cases or production sensitivity estimates.',
                              'Numeric normalization is explicit; do not enable it on categorical identifiers with significant formatting.',
                              'Label-quality opt-in consults heldout labels for diagnostics only; default audit remains invariant to heldout labels.',
                              'Conflicting labels may be legitimate stochastic outcomes; review signals are not proof of leakage.']}
    destination = Path(report)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
    return result


if __name__ == '__main__':
    print(json.dumps(validate(), indent=2))
