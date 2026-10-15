import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from leakage_audit import AuditConfig,audit,read_csv
from leakage_audit.audit import correlation
from leakage_audit.benchmark import generate
from leakage_audit.cli import main
from leakage_audit.wine_validation import load_wine,split_wine

CONFIG=AuditConfig("target","entity","timestamp")

def findings(result,kind):return [f for f in result["findings"] if f["kind"]==kind]

@pytest.mark.parametrize("field,value",[("embargo_seconds",float("nan")),("embargo_seconds",float("inf")),("embargo_seconds",-1),("shift_threshold",float("nan")),("shift_threshold",float("inf")),("proxy_threshold",float("nan")),("proxy_threshold",float("-inf")),("proxy_threshold",0),("shift_threshold",1.01),("shift_threshold",".3")])
def test_invalid_config_values(field,value):
    with pytest.raises(ValueError):AuditConfig("target",**{field:value})

@pytest.mark.parametrize("kwargs",[{"target":""},{"target":" "},{"target":"target","entity":"target"},{"target":"target","entity":"x","time":"x"}])
def test_config_column_names(kwargs):
    with pytest.raises(ValueError):AuditConfig(**kwargs)

@pytest.mark.parametrize("content",["a,\n1,2\n"," ,b\n1,2\n","a,a\n1,2\n","a,b\n1,2,3\n",'a\n"unterminated\n'])
def test_invalid_csv_headers_width_and_quotes(tmp_path,content):
    path=tmp_path/"invalid.csv";path.write_text(content,encoding="utf-8")
    with pytest.raises(ValueError):read_csv(path)

def test_csv_bom_unicode_and_quoted_newlines(tmp_path):
    path=tmp_path/"valid.csv";path.write_bytes('target,caf\u00e9\n1,"line one\nline two"\n'.encode("utf-8-sig"))
    assert read_csv(path)==[{"target":"1","caf\u00e9":"line one\nline two"}]

def test_malformed_api_schema_and_nested_values():
    train,test=generate();train[0]["feature"]=[1,2]
    with pytest.raises(ValueError,match="scalar"):audit(train,test,CONFIG)
    train,test=generate();train[0][""]=train[0].pop("feature")
    with pytest.raises(ValueError,match="nonempty"):audit(train,test,CONFIG)
    with pytest.raises(ValueError,match="Missing configured"):audit(*generate(),AuditConfig("unknown"))
    with pytest.raises(ValueError,match="non-metadata"):audit([{"target":"0"}],[{"target":"1"}],AuditConfig("target"))

def test_nonfinite_features_are_quality_signal_not_category_drift():
    train,test=generate()
    for i,row in enumerate(train+test):row["feature"]=str(i%7)
    test[0]["feature"]="+inf";test[1]["feature"]="-Infinity";test[2]["feature"]="+NaN"
    result=audit(train,test,CONFIG)
    quality=findings(result,"nonfinite_values")
    assert quality[0]["evidence"]=={"column":"feature","train_rows":0,"test_rows":3}
    assert not [f for f in findings(result,"distribution_shift") if f["evidence"]["column"]=="feature"]
    assert not findings(result,"missingness_shift")
    json.dumps(result,allow_nan=False)

def test_huge_finite_values_have_finite_correct_proxy_score():
    assert correlation([1e308,-1e308,5e307,-5e307],[1.,-1.,.5,-.5])==pytest.approx(1)
    train,test=generate()
    for row in train+test:
        row["large_proxy"]="1e308" if row["target"]=="1" else "-1e308"
    matches=[f for f in findings(audit(train,test,CONFIG),"target_proxy") if f["evidence"]["column"]=="large_proxy"]
    assert matches and all(0<=f["evidence"]["score"]<=1 for f in matches)

def test_rare_category_mapping_requires_each_category_support():
    train,test=generate()
    for i,row in enumerate(train):row["rare_code"]="one-off" if i==0 else "common";row["target"]="1" if i==0 else "0"
    for row in test:row["rare_code"]="common"
    result=audit(train,test,CONFIG)
    assert not [f for f in findings(result,"target_proxy") if f["evidence"]["column"]=="rare_code"]

def test_all_unusable_feature_rows_not_structural_duplicates():
    train=[{"target":"0","feature":""} for _ in range(20)]
    test=[{"target":"1","feature":""}]
    assert not findings(audit(train,test,AuditConfig("target")),"cross_split_duplicates")

def test_duplicate_string_representation_is_deliberately_exact():
    train=[{"target":"0","feature":"1.0"} for _ in range(20)]
    test=[{"target":"1","feature":"1"}]
    assert not findings(audit(train,test,AuditConfig("target")),"cross_split_duplicates")

def test_exact_threshold_rounding_is_inclusive():
    train=[{"target":"0","feature":"" if i<4 else "observed"} for i in range(10)]
    test=[{"target":"1","feature":"" if i<7 else "observed"} for i in range(10)]
    assert findings(audit(train,test,AuditConfig("target",shift_threshold=.3)),"missingness_shift")

def test_timezone_equality_and_embargo_boundary():
    train,test=generate();train[-1]["timestamp"]="2024-07-18T00:00:00Z"
    test[0]["timestamp"]="2024-07-18T05:30:01+05:30"
    assert not findings(audit(train,test,CONFIG),"temporal_overlap")
    match=findings(audit(train,test,AuditConfig("target","entity","timestamp",1)),"temporal_overlap")
    assert match[0]["evidence"]["test_rows"]==1
    test[0]["timestamp"]="2024-07-18T05:30:00+05:30"
    assert findings(audit(train,test,CONFIG),"temporal_overlap")

def test_cutoff_and_timezone_overflow_raise_validation_error():
    train,test=generate()
    with pytest.raises(ValueError,match="cutoff"):audit(train,test,AuditConfig("target","entity","timestamp",1e100))
    test[0]["timestamp"]="9999-12-31T23:59:59-14:00"
    with pytest.raises(ValueError,match="ISO-8601"):audit(train,test,CONFIG)

def test_heldout_labels_are_never_used_even_when_missing_or_nonfinite():
    train,test=generate();before=audit(train,test,CONFIG)
    for i,row in enumerate(test):row["target"]=[None,"unknown","nan","+inf"][i%4]
    assert audit(train,test,CONFIG)==before

def test_report_is_stable_across_hash_seeds_and_column_order():
    script="""import json
from leakage_audit import audit,AuditConfig
train=[{'target':'0','category':str(i%7)} for i in range(100)]
test=[{'category':str(i%11),'target':'1'} for i in range(30)]
print(json.dumps(audit(train,test,AuditConfig('target')),sort_keys=True,allow_nan=False))
"""
    outputs=[]
    for seed in ["1","2","99"]:
        env={**os.environ,"PYTHONHASHSEED":seed}
        outputs.append(subprocess.check_output([sys.executable,"-c",script],env=env,text=True))
    assert len(set(outputs))==1

def write_csv(path,rows):
    with path.open("w",newline="",encoding="utf-8") as file:
        writer=csv.DictWriter(file,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def test_cli_output_exit_and_input_overwrite_protection(tmp_path,capsys):
    train,test=generate();a,b=tmp_path/"train.csv",tmp_path/"test.csv"
    write_csv(a,train);write_csv(b,test);original=a.read_bytes()
    common=[str(a),str(b),"--target","target","--entity","entity","--time","timestamp"]
    assert main(common)==0
    assert json.loads(capsys.readouterr().out)["findings"]==[]
    with pytest.raises(SystemExit) as error:main(common+["--output",str(a)])
    assert error.value.code==2 and a.read_bytes()==original
    with pytest.raises(SystemExit) as error:main(common+["--embargo-seconds","nan"])
    assert error.value.code==2
    with pytest.raises(SystemExit) as error:main(common+["--output",str(tmp_path)])
    assert error.value.code==2

def test_wine_split_conserves_rows_and_is_reproducible():
    rows=[{"target":str(i%3),"feature":str(i)} for i in range(60)]
    first=split_wine(rows,42);assert first==split_wine(rows,42)
    assert len(first[0])==45 and len(first[1])==15
    assert not {r["feature"] for r in first[0]}&{r["feature"] for r in first[1]}
    assert len(rows)==60

def test_wine_hash_rejects_corrupted_download_without_network(tmp_path):
    (tmp_path/"wine.zip").write_bytes(b"corrupted")
    with pytest.raises(ValueError,match="SHA256 mismatch"):load_wine(tmp_path)


def test_strong_predictor_is_review_not_automatic_leakage_verdict():
    train,test=generate()
    for row in train+test:
        row["strong_measurement"]=str(10*int(row["target"])+2)
    proxies=findings(audit(train,test,CONFIG),"target_proxy")
    assert proxies and all(f["severity"]=="review" for f in proxies)


def test_extreme_integer_embargo_is_validation_error():
    with pytest.raises(ValueError,match="finite"):
        AuditConfig("target",embargo_seconds=10**1000)


@pytest.mark.parametrize("invalid",[None,1,[None],[[1,2]],"not rows"])
def test_nonmapping_api_inputs_are_validation_errors(invalid):
    with pytest.raises(ValueError):
        audit(invalid,[{"target":"0","feature":"x"}],AuditConfig("target"))


def test_iterable_splits_match_list_reports():
    train,test=generate()
    assert audit(iter(train),tuple(test),CONFIG)==audit(train,test,CONFIG)
