"""Risk signals, not a proof of leakage. Never fit on the held-out split."""
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import csv
import math
from decimal import Decimal, InvalidOperation
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
    numeric_duplicate_columns: tuple[str, ...] = ()
    check_target_quality: bool = False
    check_near_duplicates: bool = False

    def __post_init__(self):
        names=[name for name in (self.target,self.entity,self.time) if name is not None]
        if any(not isinstance(name,str) or not name.strip() for name in names):
            raise ValueError("Configured column names must be nonempty strings")
        if len(names)!=len(set(names)):
            raise ValueError("Target, entity and time columns must be distinct")
        if not isinstance(self.numeric_duplicate_columns, tuple) or any(not isinstance(c, str) or not c.strip() for c in self.numeric_duplicate_columns) or len(set(self.numeric_duplicate_columns)) != len(self.numeric_duplicate_columns):
            raise ValueError("Numeric duplicate columns must be a tuple of distinct nonempty names")
        if not isinstance(self.check_target_quality, bool):
            raise ValueError("check_target_quality must be boolean")
        if not isinstance(self.check_near_duplicates, bool):
            raise ValueError("check_near_duplicates must be boolean")
        values=(self.embargo_seconds,self.proxy_threshold,self.shift_threshold)
        if any(not isinstance(v,(int,float)) for v in values):
            raise ValueError("Embargo and thresholds must be numeric")
        try:
            finite=all(math.isfinite(v) for v in values)
        except OverflowError:
            finite=False
        if not finite:
            raise ValueError("Embargo and thresholds must be finite")
        if self.embargo_seconds < 0:
            raise ValueError("embargo_seconds must be finite and nonnegative")
        if not 0 < self.proxy_threshold <= 1 or not 0 < self.shift_threshold <= 1:
            raise ValueError("thresholds must be in (0, 1]")

def missing(value):
    return value is None or str(value).strip().lower() in MISSING

def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f,strict=True)
        if not reader.fieldnames or any(not name.strip() for name in reader.fieldnames) or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("CSV requires nonempty, unique column names")
        try:
            rows = list(reader)
        except csv.Error as error:
            raise ValueError(f"Malformed CSV: {error}") from error
        if any(None in r or any(v is None for v in r.values()) for r in rows):
            raise ValueError("CSV row width differs from header")
        return rows

def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError, OverflowError):
        return None

def nonfinite(value):
    """Recognized missing markers stay missing; other nonfinite numbers are invalid."""
    if missing(value): return False
    try:
        return not math.isfinite(float(value))
    except (ValueError, TypeError):
        return False
    except OverflowError:
        return True

def usable(value):
    return not missing(value) and not nonfinite(value)

def correlation(x, y):
    # Scale finite values first to avoid overflow in means, squares and products.
    sx,sy=max(abs(v) for v in x),max(abs(v) for v in y)
    if not sx or not sy: return 0.
    x,y=[v/sx for v in x],[v/sy for v in y]
    mx,my=math.fsum(x)/len(x),math.fsum(y)/len(y)
    vx,vy=math.fsum((v-mx)**2 for v in x),math.fsum((v-my)**2 for v in y)
    denominator=math.sqrt(vx)*math.sqrt(vy)
    result=math.fsum((a-mx)*(b-my) for a,b in zip(x,y))/denominator if denominator else 0.
    return max(-1.,min(1.,result))

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

def at_least(value, threshold):
    """Inclusive thresholds with a tiny tolerance for empirical-fraction rounding."""
    return value >= threshold or math.isclose(value,threshold,rel_tol=0,abs_tol=1e-12)

def parse_time(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    # Naive input is explicitly interpreted as UTC.
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)

def audit(train, test, config):
    try:
        train,test=list(train),list(test)
    except TypeError as error:
        raise ValueError("Splits must be iterables of row mappings") from error
    if not train or not test:
        raise ValueError("Both splits must contain rows")
    if any(not isinstance(row,Mapping) for row in train+test):
        raise ValueError("Every row must be a mapping of column names to scalar values")
    columns = set(train[0])
    if any(not isinstance(c,str) or not c.strip() for c in columns):
        raise ValueError("Column names must be nonempty strings")
    if any(set(r) != columns for r in train + test):
        raise ValueError("Splits must have identical schemas")
    if any(not isinstance(v,(str,int,float,bool,type(None))) for row in train+test for v in row.values()):
        raise ValueError("Tabular values must be scalar strings, numbers, booleans or None")
    required = {config.target} | {c for c in (config.entity, config.time) if c}
    if not required <= columns:
        raise ValueError(f"Missing configured columns: {sorted(required-columns)}")
    findings = []
    def add(kind, severity, **evidence):
        findings.append(dict(kind=kind, severity=severity, evidence=evidence))
    features = sorted(columns - required)
    if not features:
        raise ValueError("At least one non-metadata feature is required")
    if not set(config.numeric_duplicate_columns) <= set(features):
        raise ValueError("Numeric duplicate columns must be non-metadata feature columns")
    if config.check_near_duplicates and not 2 <= len(features) <= 64:
        raise ValueError("Near-duplicate audit requires between 2 and 64 features")
    def signature(row):
        values = []
        for col in features:
            value = row[col]
            if col in config.numeric_duplicate_columns:
                if missing(value):
                    value = ('missing',)
                else:
                    try:
                        normalized = Decimal(str(value).strip())
                    except InvalidOperation as error:
                        raise ValueError(f"Configured numeric duplicate column contains nonnumeric data: {col}") from error
                    if not normalized.is_finite():
                        raise ValueError(f"Configured numeric duplicate column contains nonfinite data: {col}")
                    value = ('numeric', normalized)
            values.append(value)
        return tuple(values)
    # Validate explicitly numeric columns even on otherwise unusable rows.
    if config.numeric_duplicate_columns:
        for row in train + test:
            signature(row)
    signatures = {signature(r) for r in train if any(usable(r[c]) for c in features)}
    duplicates = sum(any(usable(r[c]) for c in features) and signature(r) in signatures for r in test)
    if duplicates:
        add("cross_split_duplicates", "high", test_rows=duplicates, test_fraction=duplicates/len(test), columns=features,
            numeric_normalization_columns=list(config.numeric_duplicate_columns))
    if config.check_near_duplicates:
        # Process one projection at a time to bound memory. Keep at most two
        # distinct omitted values: sufficient to establish an unequal witness.
        eligible_test = [(index, signature(row)) for index, row in enumerate(test)
                         if any(usable(row[c]) for c in features)]
        matched_rows, by_column = set(), {}
        for position, column in enumerate(features):
            projections = {}
            for values in signatures:
                key = values[:position] + values[position+1:]
                bucket = projections.setdefault(key, set())
                if len(bucket) < 2:
                    bucket.add(values[position])
            count = 0
            for index, values in eligible_test:
                if values in signatures:
                    continue
                key = values[:position] + values[position+1:]
                witnesses = projections.get(key, ())
                if any(value != values[position] for value in witnesses):
                    matched_rows.add(index)
                    count += 1
            if count:
                by_column[column] = count
        if matched_rows:
            add('cross_split_near_duplicates', 'review', test_rows=len(matched_rows),
                test_fraction=len(matched_rows)/len(test), differing_column_counts=by_column,
                excluded_exact_matches=True,
                interpretation='Exactly one feature differs; chance matches and legitimate repeated measurements are possible.')
    if config.check_target_quality:
        target_quality = {}
        for name, rows in [('train', train), ('test', test)]:
            absent = sum(missing(r[config.target]) for r in rows)
            invalid = sum(nonfinite(r[config.target]) for r in rows)
            if absent or invalid:
                target_quality[name] = {'missing': absent, 'nonfinite': invalid, 'rows': len(rows)}
        if target_quality:
            add('target_quality', 'review', splits=target_quality)
        # Explicit opt-in: consults heldout labels for quality, never fits proxy scores.
        labels_by_signature = {}
        for row in train:
            if usable(row[config.target]) and any(usable(row[c]) for c in features):
                labels_by_signature.setdefault(signature(row), set()).add(row[config.target])
        conflicts = sum(len(labels) > 1 for labels in labels_by_signature.values())
        if conflicts:
            add('within_train_label_conflicts', 'review', feature_groups=conflicts)
        cross_conflicts = sum(usable(r[config.target]) and any(usable(r[c]) for c in features)
                              and signature(r) in labels_by_signature
                              and any(label != r[config.target] for label in labels_by_signature[signature(r)]) for r in test)
        if cross_conflicts:
            add('cross_split_label_conflicts', 'review', test_rows=cross_conflicts,
                interpretation='Matching feature vectors have contradictory labels; legitimate stochastic outcomes are possible.')
    if config.entity:
        entities = {r[config.entity] for r in train if not missing(r[config.entity])}
        overlap = sum(not missing(r[config.entity]) and r[config.entity] in entities for r in test)
        if overlap:
            add("entity_overlap", "review", test_rows=overlap, test_fraction=overlap/len(test))
    if config.time:
        try:
            train_times = [parse_time(r[config.time]) for r in train]
            test_times = [parse_time(r[config.time]) for r in test]
        except (ValueError, TypeError, OverflowError) as e:
            raise ValueError("Every configured timestamp must be a valid ISO-8601 datetime") from e
        try:
            cutoff = max(train_times) + timedelta(seconds=config.embargo_seconds)
        except (OverflowError,ValueError) as error:
            raise ValueError("Temporal cutoff exceeds the supported datetime range") from error
        overlap = sum(t <= cutoff for t in test_times)
        if overlap:
            add("temporal_overlap", "high", test_rows=overlap, cutoff=cutoff.isoformat(), embargo_seconds=config.embargo_seconds)
    # Train-only associations avoid selecting features using test labels.
    for col in features:
        invalid_train=sum(nonfinite(r[col]) for r in train)
        invalid_test=sum(nonfinite(r[col]) for r in test)
        if invalid_train or invalid_test:
            add("nonfinite_values", "review", column=col, train_rows=invalid_train, test_rows=invalid_test)
        pairs = [(r[col], r[config.target]) for r in train if usable(r[col]) and usable(r[config.target])]
        if len(pairs) >= 20:
            x, y = zip(*pairs)
            nx, ny = [number(v) for v in x], [number(v) for v in y]
            if all(v is not None for v in nx + ny):
                corr = abs(correlation(nx, ny))
                if at_least(corr,config.proxy_threshold):
                    add("target_proxy", "review", column=col, method="absolute_pearson", score=corr, rows=len(pairs))
            # Restrict mapping checks to repeated, low-cardinality categories.
            counts = Counter(x)
            mapping = {}
            for a,b in pairs:
                mapping.setdefault(a, set()).add(b)
            if 1 < len(counts) <= min(20, len(pairs)//5) and min(counts.values()) >= 5 and len(set(y)) > 1 and all(len(v)==1 for v in mapping.values()):
                add("target_proxy", "review", column=col, method="deterministic_category_mapping", score=1., rows=len(pairs))
        a = [r[col] for r in train if usable(r[col])]
        b = [r[col] for r in test if usable(r[col])]
        ma=sum(missing(r[col]) for r in train)/len(train)
        mb=sum(missing(r[col]) for r in test)/len(test)
        if at_least(abs(ma-mb),config.shift_threshold):
            add("missingness_shift", "review", column=col, train_fraction=ma, test_fraction=mb)
        if not a or not b:
            continue
        na, nb = [number(v) for v in a], [number(v) for v in b]
        if all(v is not None for v in na + nb):
            distance, method = ks_distance(na, nb), "empirical_ks"
        else:
            ca, cb = Counter(a), Counter(b)
            keys=sorted(ca.keys() | cb.keys(),key=lambda value:(type(value).__name__,repr(value)))
            distance = min(1.,.5*math.fsum(abs(ca[k]/len(a)-cb[k]/len(b)) for k in keys))
            method = "total_variation"
        if at_least(distance,config.shift_threshold):
            add("distribution_shift", "review", column=col, method=method, score=distance, train_nonmissing=len(a), test_nonmissing=len(b))
    return {"schema_version": 1, "rows": {"train": len(train), "test": len(test)}, "findings": findings,
            "configuration": {'numeric_duplicate_columns': list(config.numeric_duplicate_columns),
                              'check_target_quality': config.check_target_quality,
                              'check_near_duplicates': config.check_near_duplicates},
            "limitations": ["Signals require domain review; distribution shift is not proof of leakage.", "Cannot detect preprocessing fit on test data, label availability or semantic duplicates.", "Exact feature-row comparisons exclude configured target/entity/time; missing tokens are documented.", "Numeric proxy detection uses train-only linear association; nonlinear proxies may be missed."]}
