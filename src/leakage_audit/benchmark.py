"""Deterministic synthetic controls with isolated injected defects."""
import argparse
import csv
import json
import random
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from .audit import AuditConfig, audit

def generate(seed=42, n=200):
    rng = random.Random(seed)
    origin = datetime(2024,1,1)
    def rows(offset):
        return [{"entity": str(i+offset), "timestamp": (origin+timedelta(days=i+offset)).isoformat(),
                 "feature": str(rng.gauss(0,1)), "category": str(i%3), "target": str(rng.randrange(2))} for i in range(n)]
    return rows(0), rows(n)

def run(output, report=None):
    base_train, base_test = generate()
    cases = {}
    for name, expected in [("clean",None),("duplicates","cross_split_duplicates"),("entities","entity_overlap"),("time","temporal_overlap"),("proxy","target_proxy"),("shift","distribution_shift")]:
        train, test = deepcopy(base_train), deepcopy(base_test)
        if name == "duplicates":
            for i in range(10):
                for c in ("feature","category"):
                    test[i][c]=train[i][c]
        elif name == "entities":
            for i in range(10): test[i]["entity"]=train[i]["entity"]
        elif name == "time":
            for i in range(10): test[i]["timestamp"]=train[i]["timestamp"]
        elif name == "proxy":
            for row in train+test: row["outcome_code"]=str(int(row["target"])*100+7)
        elif name == "shift":
            for row in test: row["feature"]=str(float(row["feature"])+8)
        folder = Path(output); folder.mkdir(parents=True, exist_ok=True)
        for split, rows in [("train",train),("test",test)]:
            with (folder/f"{name}_{split}.csv").open("w",newline="",encoding="utf-8") as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
        result=audit(train,test,AuditConfig("target","entity","timestamp"))
        detected=sorted({f["kind"] for f in result["findings"]})
        cases[name]={"expected_signal":expected,"detected_signals":detected,"passed": expected in detected if expected else not detected}
        if name == "duplicates":
            (folder/"example-report.json").write_text(json.dumps(result,indent=2)+"\n")
    summary={"benchmark":"synthetic isolated injection controls, not real-world sensitivity/specificity", "seed":42,"train_rows_per_case":200,"test_rows_per_case":200,"cases":cases,"passed":sum(c["passed"] for c in cases.values()),"total":len(cases)}
    content=json.dumps(summary,indent=2)+"\n"
    if report:
        path=Path(report);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content,encoding="utf-8")
    print(content,end="")
    return summary

def main():
    p=argparse.ArgumentParser();p.add_argument("--output",default="data/processed");p.add_argument("--report")
    args=p.parse_args(); result=run(args.output,args.report)
    if result["passed"] != result["total"]: raise SystemExit(1)
if __name__ == "__main__": main()
