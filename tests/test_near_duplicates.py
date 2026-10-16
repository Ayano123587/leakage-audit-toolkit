import itertools
import json
import pytest
from leakage_audit.audit import AuditConfig, audit
from leakage_audit.cli import main


def evidence(train, test, **kwargs):
    result = audit(train, test, AuditConfig('target', check_near_duplicates=True, **kwargs))
    return next((f['evidence'] for f in result['findings']
                 if f['kind'] == 'cross_split_near_duplicates'), None)


def test_projection_matches_independent_pairwise_oracle():
    columns = ('a', 'b', 'c')
    vectors = list(itertools.product(('0', '1', '2'), repeat=3))
    train_vectors, test_vectors = vectors[::4], vectors[1::3]
    rows = lambda values: [dict(zip(columns, v), target='private-label') for v in values]
    exact = set(train_vectors)
    expected = {c: 0 for c in columns}
    matched = 0
    for vector in test_vectors:
        if vector in exact:
            continue
        positions = {next(i for i in range(3) if vector[i] != other[i])
                     for other in train_vectors
                     if sum(a != b for a, b in zip(vector, other)) == 1}
        matched += bool(positions)
        for i in positions:
            expected[columns[i]] += 1
    observed = evidence(rows(train_vectors), rows(test_vectors))
    assert observed['test_rows'] == matched
    assert observed['differing_column_counts'] == {k: v for k, v in expected.items() if v}
    assert 'private-label' not in json.dumps(observed)


def test_exact_matches_and_all_missing_rows_are_excluded():
    train = [dict(a='x', b='y', target=0), dict(a=None, b=None, target=0)]
    test = [dict(a='x', b='y', target=1), dict(a=None, b=None, target=1),
            dict(a='x', b='z', target=1), dict(a='q', b='z', target=1)]
    assert evidence(train, test)['test_rows'] == 1


def test_multiple_train_witnesses_count_test_row_once():
    train = [dict(a=str(i), b='x', target=0) for i in range(8)]
    test = [dict(a='new', b='x', target=1)] * 3
    assert evidence(train, test)['differing_column_counts'] == {'a': 3}


def test_explicit_decimal_normalization_and_target_invariance():
    train = [dict(a='1.00', b='left', target=0)]
    test = [dict(a='1e0', b='right', target=1)]
    assert evidence(train, test) is None
    expected = evidence(train, test, numeric_duplicate_columns=('a',))
    test[0]['target'] = 'different-private-label'
    assert evidence(train, test, numeric_duplicate_columns=('a',)) == expected
    assert expected['differing_column_counts'] == {'b': 1}


@pytest.mark.parametrize('count', [1, 65])
def test_feature_budget_fails_closed(count):
    row = {str(i): 'x' for i in range(count)} | {'target': 0}
    with pytest.raises(ValueError, match='2 and 64'):
        evidence([row], [row])


def test_nonboolean_configuration_rejected():
    with pytest.raises(ValueError, match='boolean'):
        AuditConfig('target', check_near_duplicates=1)


def test_cli_opt_in_preserves_sources_and_hides_values(tmp_path, capsys):
    train, test = tmp_path/'train.csv', tmp_path/'test.csv'
    train.write_text('a,b,target\nsecretA,secretB,0\n', encoding='utf-8')
    test.write_text('a,b,target\nsecretA,secretC,1\n', encoding='utf-8')
    original = train.read_bytes(), test.read_bytes()
    assert main([str(train), str(test), '--target', 'target', '--check-near-duplicates']) == 0
    result = capsys.readouterr().out
    assert 'cross_split_near_duplicates' in result and 'secret' not in result
    assert (train.read_bytes(), test.read_bytes()) == original


def test_default_does_not_enable_near_matching():
    result = audit([dict(a=1, b=2, target=0)], [dict(a=1, b=3, target=1)], AuditConfig('target'))
    assert all(f['kind'] != 'cross_split_near_duplicates' for f in result['findings'])


def test_two_differing_column_witnesses_deduplicate_rows():
    train = [dict(a=1, b=2, target=0), dict(a=2, b=1, target=0)]
    result = evidence(train, [dict(a=1, b=1, target=1)])
    assert result['test_rows'] == 1
    assert result['differing_column_counts'] == {'a': 1, 'b': 1}


def test_metadata_excluded_and_heldout_labels_do_not_change_report():
    train = [dict(a=1, b=2, id='personA', target=0)]
    test = [dict(a=1, b=3, id='personB', target=1)]
    config = AuditConfig('target', entity='id', check_near_duplicates=True)
    expected = audit(train, test, config)
    test[0]['target'] = None
    assert audit(train, test, config) == expected
    near = next(f for f in expected['findings'] if f['kind'] == 'cross_split_near_duplicates')
    assert near['evidence']['differing_column_counts'] == {'b': 1}
