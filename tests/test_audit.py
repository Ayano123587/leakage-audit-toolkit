import pytest
from leakage_audit import AuditConfig, audit, read_csv
from leakage_audit.audit import ks_distance
from leakage_audit.benchmark import generate, run
from leakage_audit.cli import main

CONFIG=AuditConfig("target","entity","timestamp")
def kinds(result): return {f["kind"] for f in result["findings"]}

def test_clean_control():
    assert not audit(*generate(),CONFIG)["findings"]

def test_duplicate_ignores_label_and_metadata():
    train,test=generate();test[0]["feature"]=train[0]["feature"];test[0]["category"]=train[0]["category"]
    test[0]["target"]=str(1-int(train[0]["target"]))
    assert "cross_split_duplicates" in kinds(audit(train,test,CONFIG))

def test_missing_entities_do_not_overlap():
    train,test=generate()
    for row in train+test: row["entity"]=""
    assert "entity_overlap" not in kinds(audit(train,test,CONFIG))

def test_embargo_and_timezone():
    train,test=generate()
    train[-1]["timestamp"]="2024-07-18T01:00:00+01:00"
    test[0]["timestamp"]="2024-07-18T00:00:01Z"
    assert "temporal_overlap" not in kinds(audit(train,test,CONFIG))
    assert "temporal_overlap" in kinds(audit(train,test,AuditConfig("target","entity","timestamp",2)))

def test_proxy_train_only_and_identifier_not_proxy():
    train,test=generate()
    for i,row in enumerate(train): row["unique_id"]=f"id-{i}"
    for i,row in enumerate(test): row["unique_id"]=f"test-{i}"
    report=audit(train,test,CONFIG)
    assert not [f for f in report["findings"] if f["kind"]=="target_proxy"]
    for row in train+test: row["proxy"]=str(3*int(row["target"])+2)
    assert "target_proxy" in kinds(audit(train,test,CONFIG))

def test_constant_numeric_target_not_proxy():
    train,test=generate()
    for row in train+test: row["target"]="1"
    assert "target_proxy" not in kinds(audit(train,test,CONFIG))

def test_missingness_shift_and_nonfinite():
    train,test=generate()
    for row in test: row["feature"]="NaN"
    assert "missingness_shift" in kinds(audit(train,test,CONFIG))

def test_ks_ties():
    assert ks_distance([1,1,2],[1,2,2])==pytest.approx(1/3)
    assert ks_distance([1,2],[1,2])==0

def test_schema_empty_and_invalid_time():
    train,test=generate()
    with pytest.raises(ValueError): audit([],test,CONFIG)
    test[0]["extra"]="x"
    with pytest.raises(ValueError): audit(train,test,CONFIG)
    del test[0]["extra"];test[0]["timestamp"]="bad"
    with pytest.raises(ValueError,match="ISO-8601"): audit(train,test,CONFIG)

@pytest.mark.parametrize("kwargs",[{"embargo_seconds":-1},{"proxy_threshold":0},{"shift_threshold":2}])
def test_config_validation(kwargs):
    with pytest.raises(ValueError): AuditConfig("target",**kwargs)

def test_benchmark_and_cli(tmp_path):
    result=run(tmp_path)
    assert result["passed"]==6
    output=tmp_path/"out.json"
    assert main([str(tmp_path/"duplicates_train.csv"),str(tmp_path/"duplicates_test.csv"),"--target","target","--entity","entity","--time","timestamp","--output",str(output),"--fail-on-high"])==1
    assert output.exists()
    assert len(read_csv(tmp_path/"clean_train.csv"))==200

def test_malformed_csv(tmp_path):
    path=tmp_path/"bad.csv";path.write_text("a,a\n1,2\n")
    with pytest.raises(ValueError): read_csv(path)
    path.write_text("a,b\n1\n")
    with pytest.raises(ValueError): read_csv(path)


def test_categorical_shift_and_category_proxy():
    train,test=generate()
    for row in train: row["status"]="approved" if row["target"]=="1" else "rejected"
    for row in test: row["status"]="new-system"
    findings=audit(train,test,CONFIG)["findings"]
    assert any(f["kind"]=="target_proxy" and f["evidence"].get("method")=="deterministic_category_mapping" for f in findings)
    assert any(f["kind"]=="distribution_shift" and f["evidence"].get("method")=="total_variation" for f in findings)

def test_target_changes_in_test_do_not_change_findings():
    train,test=generate()
    before=audit(train,test,CONFIG)["findings"]
    for row in test: row["target"]="changed"
    assert audit(train,test,CONFIG)["findings"]==before
