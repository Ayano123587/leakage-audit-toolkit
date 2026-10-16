"""Real Adult near-match diagnostics with an independent sorted-group oracle."""
import hashlib
import itertools
import json
from pathlib import Path
import time
import zipfile
from .audit import AuditConfig, audit, read_csv
from .adult_validation import ARCHIVE_SHA256, SOURCE_HASHES, parse


def validate(directory='data/processed/adult', report='docs/near-duplicate-results.json'):
    paths = [Path(directory)/(name+'.csv') for name in ('train', 'test')]
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    train, test = [read_csv(p) for p in paths]
    archive_path = Path('data/external/adult/adult.zip')
    if hashlib.sha256(archive_path.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise ValueError('Adult source archive checksum mismatch')
    with zipfile.ZipFile(archive_path) as archive:
        for member, actual in zip(('adult.data', 'adult.test'), (train, test)):
            content = archive.read(member)
            if hashlib.sha256(content).hexdigest() != SOURCE_HASHES[member]:
                raise ValueError('Adult member checksum mismatch')
            reference = [{key: '' if value is None else value for key, value in row.items()}
                         for row in parse(content)]
            if actual != reference:
                raise ValueError('Processed rows differ from pinned original source and documented parser')
    if (len(train), len(test)) != (32561, 16281):
        raise ValueError('Expected unchanged official Adult split')
    start = time.perf_counter()
    baseline = audit(train, test, AuditConfig('target'))
    result = audit(train, test, AuditConfig('target', check_near_duplicates=True))
    audit_seconds = time.perf_counter()-start
    assert [f for f in result['findings'] if f['kind'] != 'cross_split_near_duplicates'] == baseline['findings']
    columns = sorted(set(train[0])-{'target'})
    training = {tuple(row[c] for c in columns) for row in train}
    heldout = [tuple(row[c] for c in columns) for row in test]
    # Independent algorithm: sort all projections, then scan contiguous groups.
    # Exact-match rows excluded before grouping; row numbers stay private in RAM.
    expected, matched = {}, set()
    for i, column in enumerate(columns):
        entries = [(values[:i]+values[i+1:], 0, values[i], -1) for values in training]
        entries += [(values[:i]+values[i+1:], 1, values[i], index)
                    for index, values in enumerate(heldout) if values not in training]
        entries.sort(key=lambda item: item[0])
        count = 0
        for _, group in itertools.groupby(entries, key=lambda item: item[0]):
            group = list(group)
            values = {entry[2] for entry in group if entry[1] == 0}
            for entry in group:
                if entry[1] == 1 and values-{entry[2]}:
                    count += 1
                    matched.add(entry[3])
        if count:
            expected[column] = count
    near = next(f['evidence'] for f in result['findings'] if f['kind'] == 'cross_split_near_duplicates')
    assert near['test_rows'] == len(matched) and near['differing_column_counts'] == expected
    assert before == [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    output = {'source': 'https://archive.ics.uci.edu/dataset/2/adult',
              'attribution': 'Becker & Kohavi (1996), UCI Adult, CC BY 4.0, DOI 10.24432/C5XW20',
              'original_archive_sha256': ARCHIVE_SHA256, 'original_source_sha256': SOURCE_HASHES,
              'processed_sha256': dict(zip(('train', 'test'), before)),
              'rows': result['rows'], 'near_matches': near,
              'independent_sorted_reference_agrees': True, 'default_findings_unchanged': True,
              'two_audits_seconds': audit_seconds, 'total_seconds': time.perf_counter()-start,
              'limits': ['No identity/duplication ground truth; not precision, recall or a leakage verdict.',
                         'Differences are exact strings, no implicit numeric tolerance or semantic similarity.',
                         'Per-column counts may overlap; unique test rows counted once.',
                         'Sources retained unchanged; no synthetic rows or labels injected.']}
    Path(report).write_text(json.dumps(output, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps(output, indent=2))
    return output


if __name__ == '__main__':
    validate()
