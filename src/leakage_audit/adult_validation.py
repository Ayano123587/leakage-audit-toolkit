"""Unmodified official UCI Adult split integrity audit; no leakage ground-truth claim."""
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
from urllib.request import urlopen
import zipfile
from .audit import AuditConfig, audit

URL = 'https://archive.ics.uci.edu/static/public/2/adult.zip'
ARCHIVE_SHA256 = '7537312dd56c2b98035880805ce99e68183a30ee468aa5329d6df0fbb3cc21bb'
SOURCE_HASHES = {'adult.data': '5b00264637dbfec36bdeaab5676b0b309ff9eb788d63554ca0a249491c86603d',
                 'adult.test': 'a2a9044bc167a35b2361efbabec64e89d69ce82d9790d2980119aac5fd7e9c05'}
COLUMNS = ['age', 'workclass', 'fnlwgt', 'education', 'education_num', 'marital_status',
           'occupation', 'relationship', 'race', 'sex', 'capital_gain', 'capital_loss',
           'hours_per_week', 'native_country', 'target']


def parse(content):
    rows = []
    for row in csv.reader(io.StringIO(content.decode('ascii')), skipinitialspace=True):
        if not row or row[0].startswith('|'):
            continue
        if len(row) != len(COLUMNS):
            raise ValueError('Unexpected Adult source row width')
        values = [value.strip() for value in row]
        values[-1] = values[-1].removesuffix('.')
        if values[-1] not in {'<=50K', '>50K'}:
            raise ValueError('Unexpected Adult income label')
        rows.append(dict(zip(COLUMNS, [None if v == '?' else v for v in values])))
    return rows


def validate(directory='data/external/adult', report='docs/adult-validation-results.json', processed='data/processed/adult'):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory/'adult.zip'
    if not path.exists():
        with urlopen(URL, timeout=60) as response:
            path.write_bytes(response.read())
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != ARCHIVE_SHA256:
        raise ValueError('UCI Adult archive checksum changed')
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        sources = {name: archive.read(name) for name in SOURCE_HASHES}
        for name, data in sources.items():
            if hashlib.sha256(data).hexdigest() != SOURCE_HASHES[name]:
                raise ValueError('UCI Adult source checksum mismatch')
        (directory/'adult.names').write_bytes(archive.read('adult.names'))
    train, test = parse(sources['adult.data']), parse(sources['adult.test'])
    if (len(train), len(test)) != (32561, 16281):
        raise ValueError('Official Adult split size changed')
    processed = Path(processed)
    processed.mkdir(parents=True, exist_ok=True)
    for name, rows in [('train', train), ('test', test)]:
        with (processed/(name+'.csv')).open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
    result = audit(train, test, AuditConfig('target', check_target_quality=True))
    # Independent exact-vector reference counts; no injected or resplit observations.
    signature = lambda row: tuple(row[c] for c in COLUMNS[:-1])
    training = Counter(signature(r) for r in train)
    heldout = Counter(signature(r) for r in test)
    overlap = sum(count for key, count in heldout.items() if key in training)
    detected = next((f['evidence']['test_rows'] for f in result['findings'] if f['kind'] == 'cross_split_duplicates'), 0)
    if detected != overlap:
        raise AssertionError('Audit differs from independent exact-vector overlap count')
    report_data = {'provenance': {'source': URL, 'source_page': 'https://archive.ics.uci.edu/dataset/2/adult',
                                 'attribution': 'Becker, B. & Kohavi, R. (1996). Adult. UCI Machine Learning Repository.',
                                 'doi': 'https://doi.org/10.24432/C5XW20', 'license': 'CC BY 4.0',
                                 'archive_sha256': ARCHIVE_SHA256, 'source_sha256': SOURCE_HASHES},
                   'preprocessing': 'Strip field whitespace, remove documented test-label terminal period, map ? to None; no row removal or resplitting.',
                   'audit': result, 'independent_reference': {'cross_split_matching_test_rows': overlap,
                         'cross_split_matching_feature_groups': len(set(training) & set(heldout)),
                         'repeated_training_feature_groups': sum(count > 1 for count in training.values()),
                         'extra_training_copies': sum(count - 1 for count in training.values() if count > 1)},
                   'interpretation': 'Unmodified official records contain repeated feature vectors. This is an observed integrity signal, not proof the same individual crossed splits; no person IDs are available.',
                   'limitations': ['No expert natural-leakage labels, so sensitivity/false-positive rate cannot be estimated.',
                                   'Demographic features are used only for split diagnostics; no income model or fairness claim is made.',
                                   'Target-quality option consults heldout labels for diagnostics, never for model fitting.']}
    destination = Path(report)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report_data, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'rows': result['rows'], 'reference': report_data['independent_reference'], 'finding_kinds': [f['kind'] for f in result['findings']]}, indent=2))
    return report_data


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', default='data/external/adult')
    parser.add_argument('--processed', default='data/processed/adult')
    parser.add_argument('--report', default='docs/adult-validation-results.json')
    args = parser.parse_args()
    validate(args.directory, args.report, args.processed)
