# Representation and label-quality checks

Exact string duplicate matching can miss the same numeric value serialized as `1.00`
and `1e0`. Explicitly identify numeric feature columns to compare with exact decimal
arithmetic; large integers remain distinct rather than collapsing through float64.
The default stays exact because leading zeros may carry meaning in categorical IDs.

```sh
leakage-audit train.csv test.csv --target target --numeric-duplicate-columns alcohol ash
leakage-audit train.csv test.csv --target target --check-target-quality
python -m leakage_audit.quality_validation
```

The Python configuration accepts `numeric_duplicate_columns=('alcohol', 'ash')` and
`check_target_quality=True`. Declared numeric columns reject nonnumeric/nonfinite
values; documented missing tokens receive a shared missing signature. Unusable rows
still do not create duplicate findings. Column names must identify actual features,
not the target, entity or time metadata.

Label-quality checking is separately opt-in. It reports missing/nonfinite target
counts, contradictory labels within training feature groups, and cross-split feature
matches with contradictory labels. It consults heldout labels for these diagnostics,
so do not use the output to tune a model against final test labels. Default auditing
remains invariant to heldout label changes, and all target-proxy associations remain
training-only. Contradictory outcomes can be legitimate: the new signals require review.

[Executed authentic UCI Wine controls](quality-validation-results.json) use the same
hash-pinned 178 source rows as the earlier validation. None of 20 unmodified stratified
controls was flagged. In a separately declared injection, five training vectors were
copied into test with scientific numeric formatting: default exact matching detected
zero, while explicit numeric normalization detected all five. Separate contradictory
label and missing/nonfinite-label injections were detected. These are controlled
defects on real rows, not naturally occurring leakage cases or production detection rates.

The full suite passes 73 tests, including unchanged heldout-label invariance, decimal
precision, categorical leading zeros, malformed numeric data and the actual CLI flag.
An initial implementation exposed label-quality findings by default; the existing
invariance test rejected that regression. The final implementation requires explicit
opt-in and preserves the original contract.

Remaining scope includes semantic/near-duplicate detection and multivariate distribution
shift. Those require additional assumptions and stronger natural-case benchmarks; these
changes do not claim to solve them.

## Larger unmodified natural-data audit

[UCI Adult](https://archive.ics.uci.edu/dataset/2/adult) is a48842-row census-income
dataset, licensed CC BY4.0 by UCI and attributed to Becker and Kohavi. The official
32561/16281 split was retained, with only documented whitespace, `?` missing values
and the test-label terminal period normalized. Archive and source files are hash-pinned.

```sh
python -m leakage_audit.adult_validation
```

[The executed report](adult-validation-results.json) finds **26 matching heldout feature
vectors across26 groups**,24 repeated training feature groups and25 extra training
copies. Independent Counter-based counts agree with the toolkit. Conflicting-label
signals also occur naturally and are retained as review findings. No row was injected,
removed or resplit. Exact feature matches do not prove identical people or harmful
leakage: person IDs and expert leakage ground truth are unavailable. These findings
establish real-data signal behavior, not detector sensitivity or a false-positive rate.

The default Makefile, data entry point and README now use this real official split.
CSV copies remain under ignored data/. CI uses offline unit fixtures rather than a
synthetic dataset benchmark. Historical constructed reports remain labeled historical;
they are not the primary performance evidence.

## Input provenance

The CLI hashes each source CSV before and after its audit. A changed file prevents
report output; unchanged reports identify exact SHA256 source bytes and basenames,
without exposing absolute local paths or raw rows. This improves reproducibility but
does not authenticate the original collection process or prove an absence of leakage.
