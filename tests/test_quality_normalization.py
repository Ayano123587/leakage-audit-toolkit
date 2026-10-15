import pytest
import hashlib
import json
from leakage_audit.audit import AuditConfig, audit
from leakage_audit.cli import main
from leakage_audit.adult_validation import parse


def kinds(result):
    return {finding['kind']: finding for finding in result['findings']}


def test_numeric_duplicate_normalization_is_explicit_and_decimal_exact():
    train = [{'x': '1.00', 'target': 'a'}, {'x': '9007199254740992', 'target': 'b'}]
    test = [{'x': '1e0', 'target': 'a'}, {'x': '9007199254740993', 'target': 'b'}]
    assert 'cross_split_duplicates' not in kinds(audit(train, test, AuditConfig('target')))
    result = kinds(audit(train, test, AuditConfig('target', numeric_duplicate_columns=('x',))))
    assert result['cross_split_duplicates']['evidence']['test_rows'] == 1
    assert result['cross_split_duplicates']['evidence']['numeric_normalization_columns'] == ['x']


def test_categorical_leading_zeros_remain_distinct_by_default():
    result = audit([{'x': '01', 'target': 0}], [{'x': '1', 'target': 0}], AuditConfig('target'))
    assert 'cross_split_duplicates' not in kinds(result)


def test_target_quality_and_label_conflicts_do_not_disclose_values():
    train = [{'x': 1, 'target': 'a'}, {'x': 1, 'target': 'b'}, {'x': 2, 'target': None}]
    test = [{'x': 1, 'target': 'a'}, {'x': 3, 'target': float('inf')}]
    result = kinds(audit(train, test, AuditConfig('target', check_target_quality=True)))
    assert result['target_quality']['evidence']['splits']['train']['missing'] == 1
    assert result['target_quality']['evidence']['splits']['test']['nonfinite'] == 1
    assert result['within_train_label_conflicts']['evidence']['feature_groups'] == 1
    assert result['cross_split_label_conflicts']['evidence']['test_rows'] == 1
    assert all(f['severity'] == 'review' for k, f in result.items() if k != 'cross_split_duplicates')


@pytest.mark.parametrize('columns', [('target',), ('unknown',), ('x', 'x'), ['x']])
def test_invalid_numeric_configuration(columns):
    with pytest.raises(ValueError):
        config = AuditConfig('target', numeric_duplicate_columns=columns)
        audit([{'x': 1, 'target': 0}], [{'x': 2, 'target': 0}], config)


@pytest.mark.parametrize('value', ['oops', 'inf', '-Infinity'])
def test_invalid_numeric_data_fails_closed(value):
    with pytest.raises(ValueError, match='numeric'):
        audit([{'x': value, 'target': 0}], [{'x': 1, 'target': 0}],
              AuditConfig('target', numeric_duplicate_columns=('x',)))


def test_cli_numeric_flag_detects_formatting_variants(tmp_path):
    train, test = tmp_path/'train.csv', tmp_path/'test.csv'
    train.write_text('x,target\n1.00,a\n', encoding='utf-8')
    test.write_text('x,target\n1e0,a\n', encoding='utf-8')
    assert main([str(train), str(test), '--target', 'target', '--numeric-duplicate-columns', 'x', '--fail-on-high']) == 1


def test_official_adult_parser_handles_documented_test_format():
    content = b'|1x3 Cross validator\n39, ?, 77516, Bachelors, 13, Never-married, Adm-clerical, Not-in-family, White, Male, 2174, 0, 40, United-States, <=50K.\n'
    rows = parse(content)
    assert len(rows) == 1 and rows[0]['target'] == '<=50K' and rows[0]['workclass'] is None


def test_official_adult_parser_rejects_changed_schema():
    with pytest.raises(ValueError, match='width'):
        parse(b'1,2,3\n')


def test_cli_attests_exact_source_bytes_without_absolute_paths(tmp_path, capsys):
    train, test = tmp_path/'train.csv', tmp_path/'test.csv'
    train.write_bytes(b'x,target\n1,a\n')
    test.write_bytes(b'x,target\n2,a\n')
    assert main([str(train), str(test), '--target', 'target']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['inputs']['train'] == {'filename': 'train.csv', 'sha256': hashlib.sha256(train.read_bytes()).hexdigest()}


def test_cli_rejects_source_mutation_instead_of_false_attestation(tmp_path, monkeypatch):
    import leakage_audit.cli as cli
    train, test = tmp_path/'train.csv', tmp_path/'test.csv'
    train.write_bytes(b'x,target\n1,a\n')
    test.write_bytes(b'x,target\n2,a\n')
    original = cli.audit
    def mutate(*args):
        result = original(*args)
        test.write_bytes(b'x,target\n3,a\n')
        return result
    monkeypatch.setattr(cli, 'audit', mutate)
    with pytest.raises(SystemExit) as error:
        cli.main([str(train), str(test), '--target', 'target'])
    assert error.value.code == 2
