"""Risk signals, not a proof of leakage. Never fit on the held-out split."""
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import csv
import math
from pathlib import Path

MISSING = {"", "na", "nan", "null", "none"}

@dataclass(frozen=True)
class AuditConfig:
    target: str
    entity: str | None = None
    time: str | None = None
    embargo_seconds: float = 0
    proxy_threshold: float = .98
    shift_threshold: float = .3

    def __post_init__(self):
        if self.embargo_seconds < 0:
            raise ValueError("embargo_seconds must be nonnegative")
        if not 0 < self.proxy_threshold <= 1 or not 0 < self.shift_threshold <= 1:
            raise ValueError("thresholds must be in (0, 1]")

def missing(value):
    return value is None or str(value).strip().lower() in MISSING

def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("CSV requires unique column names")
        rows = list(reader)
        if any(None in r or any(v is None for v in r.values()) for r in rows):
            raise ValueError("CSV row width differs from header")
        return rows

def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None

def correlation(x, y):
    mx, my = sum(x)/len(x), sum(y)/len(y)
    vx, vy = sum((v-mx)**2 for v in x), sum((v-my)**2 for v in y)
    return sum((a-mx)*(b-my) for a,b in zip(x,y))/math.sqrt(vx*vy) if vx and vy else 0.

def ks_distance(x, y):
    """Exact empirical CDF distance (effect size, not a p-value)."""
    a, b = Counter(x), Counter(y)
    ca = cb = 0
    distance = 0.
    for value in sorted(a.keys() | b.keys()):
        ca += a[value]
        cb += b[value]
        distance = max(distance, abs(ca/len(x)-cb/len(y)))
    return distance

def parse_time(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    # Naive input is explicitly interpreted as UTC.
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)

def audit(train, test, config):
    if not train or not test:
        raise ValueError("Both splits must contain rows")
    columns = set(train[0])
    if any(set(r) != columns for r in train + test):
        raise ValueError("Splits must have identical schemas")
    required = {config.target} | {c for c in (config.entity, config.time) if c}
    if not required <= columns:
        raise ValueError(f"Missing configured columns: {sorted(required-columns)}")
    findings = []
    def add(kind, severity, **evidence):
        findings.append(dict(kind=kind, severity=severity, evidence=evidence))
    features = sorted(columns - required)
    if not features:
        raise ValueError("At least one non-metadata feature is required")
    signature = lambda row: tuple(row[c] for c in features)
    signatures = {signature(r) for r in train}
    duplicates = sum(signature(r) in signatures for r in test)
    if duplicates:
        add("cross_split_duplicates", "high", test_rows=duplicates, test_fraction=duplicates/len(test), columns=features)
    if config.entity:
        entities = {r[config.entity] for r in train if not missing(r[config.entity])}
        overlap = sum(not missing(r[config.entity]) and r[config.entity] in entities for r in test)
        if overlap:
            add("entity_overlap", "review", test_rows=overlap, test_fraction=overlap/len(test))
    if config.time:
        try:
            train_times = [parse_time(r[config.time]) for r in train]
            test_times = [parse_time(r[config.time]) for r in test]
        except (ValueError, TypeError) as e:
            raise ValueError("Every configured timestamp must be a valid ISO-8601 datetime") from e
        cutoff = max(train_times) + timedelta(seconds=config.embargo_seconds)
        overlap = sum(t <= cutoff for t in test_times)
        if overlap:
            add("temporal_overlap", "high", test_rows=overlap, cutoff=cutoff.isoformat(), embargo_seconds=config.embargo_seconds)
    # Train-only associations avoid selecting features using test labels.
    for col in features:
        pairs = [(r[col], r[config.target]) for r in train if not missing(r[col]) and not missing(r[config.target])]
        if len(pairs) >= 20:
            x, y = zip(*pairs)
            nx, ny = [number(v) for v in x], [number(v) for v in y]
            if all(v is not None for v in nx + ny):
                corr = abs(correlation(nx, ny))
                if corr >= config.proxy_threshold:
                    add("target_proxy", "review", column=col, method="absolute_pearson", score=corr, rows=len(pairs))
            # Restrict mapping checks to repeated, low-cardinality categories.
            counts = Counter(x)
            mapping = {}
            for a,b in pairs:
                mapping.setdefault(a, set()).add(b)
            if 1 < len(counts) <= min(20, len(pairs)//5) and len(set(y)) > 1 and all(len(v)==1 for v in mapping.values()):
                add("target_proxy", "review", column=col, method="deterministic_category_mapping", score=1., rows=len(pairs))
        a = [r[col] for r in train if not missing(r[col])]
        b = [r[col] for r in test if not missing(r[col])]
        ma, mb = 1-len(a)/len(train), 1-len(b)/len(test)
        if abs(ma-mb) >= config.shift_threshold:
            add("missingness_shift", "review", column=col, train_fraction=ma, test_fraction=mb)
        if not a or not b:
            continue
        na, nb = [number(v) for v in a], [number(v) for v in b]
        if all(v is not None for v in na + nb):
            distance, method = ks_distance(na, nb), "empirical_ks"
        else:
            ca, cb = Counter(a), Counter(b)
            distance = .5*sum(abs(ca[k]/len(a)-cb[k]/len(b)) for k in ca.keys() | cb.keys())
            method = "total_variation"
        if distance >= config.shift_threshold:
            add("distribution_shift", "review", column=col, method=method, score=distance, train_nonmissing=len(a), test_nonmissing=len(b))
    return {"schema_version": 1, "rows": {"train": len(train), "test": len(test)}, "findings": findings,
            "limitations": ["Signals require domain review; distribution shift is not proof of leakage.", "Cannot detect preprocessing fit on test data, label availability or semantic duplicates.", "Exact feature-row comparisons exclude configured target/entity/time; missing tokens are documented.", "Numeric proxy detection uses train-only linear association; nonlinear proxies may be missed."]}
