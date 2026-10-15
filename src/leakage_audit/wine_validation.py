"""Authentic UCI Wine controls with separately labeled controlled defect injections."""
from collections import Counter,defaultdict
from copy import deepcopy
import csv
from datetime import datetime,timedelta
import hashlib
import io
import json
import math
from pathlib import Path
import random
import urllib.request
import zipfile
from .audit import AuditConfig,audit

URL="https://archive.ics.uci.edu/static/public/109/wine.zip"
ZIP_SHA256="2bae62c4481220623579d4c4fb36b55652b6b75e06e49fa1981b8198362dfdab"
DATA_SHA256="6be6b1203f3d51df0b553a70e57b8a723cd405683958204f96d23d7cd6aea659"
COLUMNS=["target","alcohol","malic_acid","ash","alcalinity_of_ash","magnesium","total_phenols","flavanoids","nonflavanoid_phenols","proanthocyanins","color_intensity","hue","od280_od315","proline"]

def load_wine(directory,download=False):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);path=directory/"wine.zip"
    if download or not path.exists():
        request=urllib.request.Request(URL,headers={"User-Agent":"split-sentinel/0.1-research"})
        with urllib.request.urlopen(request,timeout=60) as response:content=response.read()
        if hashlib.sha256(content).hexdigest()!=ZIP_SHA256:raise ValueError("UCI archive changed; review provenance before updating hashes")
        path.write_bytes(content)
    content=path.read_bytes()
    if hashlib.sha256(content).hexdigest()!=ZIP_SHA256:raise ValueError("UCI archive SHA256 mismatch")
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        raw=archive.read("wine.data")
        if hashlib.sha256(raw).hexdigest()!=DATA_SHA256:raise ValueError("Wine data SHA256 mismatch")
        (directory/"wine.names").write_bytes(archive.read("wine.names"))
    lines=list(csv.reader(io.StringIO(raw.decode("ascii"))))
    if len(lines)!=178 or any(len(row)!=14 for row in lines):raise ValueError("Unexpected UCI Wine shape")
    return [dict(zip(COLUMNS,row)) for row in lines],{"source":URL,"source_page":"https://archive.ics.uci.edu/dataset/109/wine","doi":"https://doi.org/10.24432/C5PC7J","attribution":"Aeberhard, S. & Forina, M. (1992). Wine [Dataset]. UCI Machine Learning Repository.","license":"CC BY 4.0","license_url":"https://creativecommons.org/licenses/by/4.0/","archive_sha256":ZIP_SHA256,"data_sha256":DATA_SHA256,"rows":178,"features":13}

def split_wine(rows,seed):
    """Stratify benchmark partitions by class; audit checks themselves never use test labels."""
    by_class=defaultdict(list)
    for row in rows:by_class[row["target"]].append(row)
    rng=random.Random(seed);train=[];test=[]
    for label in sorted(by_class):
        group=deepcopy(by_class[label]);rng.shuffle(group);cut=math.floor(.75*len(group))
        train.extend(group[:cut]);test.extend(group[cut:])
    rng.shuffle(train);rng.shuffle(test)
    return train,test

def write_split(directory,name,train,test):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    for split,rows in [("train",train),("test",test)]:
        with (directory/f"{name}_{split}.csv").open("w",newline="",encoding="utf-8") as output:
            writer=csv.DictWriter(output,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def validate(directory="data/external/wine",processed="data/processed/wine",report="docs/wine-validation-results.json",download=False):
    rows,provenance=load_wine(directory,download)
    controls=[];control_counts=Counter()
    for seed in range(20):
        train,test=split_wine(rows,seed);result=audit(train,test,AuditConfig("target"))
        kinds=sorted({f["kind"] for f in result["findings"]});control_counts.update(kinds)
        controls.append({"seed":seed,"rows":result["rows"],"finding_count":len(result["findings"]),"signal_kinds":kinds,"findings":result["findings"]})
    threshold_diagnostics=[]
    for threshold in [.1,.2,.3,.5]:
        flagged=0;signal_counts=Counter()
        for seed in range(20):
            tr,te=split_wine(rows,seed);findings=audit(tr,te,AuditConfig("target",shift_threshold=threshold))["findings"]
            flagged+=bool(findings);signal_counts.update(f["kind"] for f in findings)
        threshold_diagnostics.append({"shift_threshold":threshold,"unmodified_splits_flagged":flagged,"total_splits":20,"finding_counts":dict(sorted(signal_counts.items()))})
    ordered=audit(rows[:133],rows[133:],AuditConfig("target"))
    train,test=split_wine(rows,42);base=audit(train,test,AuditConfig("target"))
    write_split(processed,"clean",train,test)
    injected=[]
    cases=[("duplicates","cross_split_duplicates",None),("proxy","target_proxy","label_copy"),("shift","distribution_shift","alcohol"),("missingness","missingness_shift","alcohol"),("entities","entity_overlap",None),("time","temporal_overlap",None)]
    for name,expected,column in cases:
        tr,te=deepcopy(train),deepcopy(test);config=AuditConfig("target");description=""
        if name=="duplicates":
            for i in range(5):
                for feature in COLUMNS[1:]:te[i][feature]=tr[i][feature]
            description="Five heldout feature vectors replaced with training vectors; original test labels retained."
        elif name=="proxy":
            for row in tr+te:row["label_copy"]="cultivar_"+row["target"]
            description="Deliberate categorical encoding of labels, not a naturally observed Wine feature."
        elif name=="shift":
            for row in te:row["alcohol"]=str(float(row["alcohol"])+30)
            description="Artificial +30 shift to heldout alcohol; distribution shift is not itself leakage."
        elif name=="missingness":
            for row in te[:math.ceil(.6*len(te))]:row["alcohol"]=""
            description="Artificial missingness in60% of heldout alcohol measurements."
        elif name=="entities":
            for i,row in enumerate(tr):row["entity"]=f"train-row-{i}"
            for i,row in enumerate(te):row["entity"]=f"test-row-{i}"
            for i in range(5):te[i]["entity"]=tr[i]["entity"]
            config=AuditConfig("target",entity="entity")
            description="Manufactured disjoint row IDs with five overwritten overlaps; Wine has no natural entity field."
        else:
            origin=datetime(2024,1,1)
            for i,row in enumerate(tr):row["timestamp"]=(origin+timedelta(hours=i)).isoformat()
            for i,row in enumerate(te):row["timestamp"]=(origin+timedelta(hours=len(tr)+i)).isoformat()
            for i in range(5):te[i]["timestamp"]=tr[i]["timestamp"]
            config=AuditConfig("target",time="timestamp")
            description="Manufactured chronology with five past heldout timestamps; Wine provides no observation dates."
        result=audit(tr,te,config);matches=[f for f in result["findings"] if f["kind"]==expected and (column is None or f["evidence"].get("column")==column)]
        injected.append({"case":name,"description":description,"expected_signal":expected,"expected_column":column,"detected":bool(matches),"matching_findings":matches,"all_findings":result["findings"]})
        write_split(processed,name,tr,te)
    summary={"benchmark":"authentic UCI Wine measurements; unmodified controls versus separately labeled artificial defects","provenance":provenance,"thresholds":{"proxy":.98,"shift":.3},"control_protocol":"20seeded stratified75/25partitions, no defects injected. Repeated splits are dependent and not20independent datasets.","controls":controls,"threshold_diagnostics":threshold_diagnostics,"source_order_partition":{"description":"Unmodified first133/last45rows; original file is class-ordered, so legitimate cultivar composition shift is expected. No leakage is injected and no observation-time claim is made.","findings":ordered["findings"]},"control_signal_split_counts":dict(sorted(control_counts.items())),"unmodified_control_flag_fraction":sum(bool(c["findings"]) for c in controls)/len(controls),"seed42_unmodified_findings":base["findings"],"controlled_injections":injected,"injected_cases_detected":sum(c["detected"] for c in injected),"injected_cases_total":len(injected),"interpretation":["Injected defects are constructed controls, not discovered natural Wine leakage.","A review signal on an unmodified partition can arise from sample variation or target predictiveness; it is not proof of leakage.","No verified leakage-free ground truth is available, so unmodified-control flags are not an estimated real-world false positive rate.","This small dataset has no genuine group/time metadata; those injections use explicitly manufactured metadata.","Correctness on six injected cases and synthetic controls does not guarantee finding all leakage or estimate production sensitivity."]}
    destination=Path(report);destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(json.dumps(summary,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    destination.with_name("wine-dataset-provenance.json").write_text(json.dumps(provenance,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"controls":len(controls),"flagged_controls":sum(bool(c["findings"]) for c in controls),"control_signal_split_counts":summary["control_signal_split_counts"],"seed42_unmodified_findings":base["findings"],"injected_cases_detected":summary["injected_cases_detected"],"injected_cases_total":len(injected)},indent=2))
    return summary

def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--directory",default="data/external/wine");parser.add_argument("--processed",default="data/processed/wine");parser.add_argument("--report",default="docs/wine-validation-results.json");parser.add_argument("--download",action="store_true")
    args=parser.parse_args();validate(args.directory,args.processed,args.report,args.download)
if __name__=="__main__":main()
