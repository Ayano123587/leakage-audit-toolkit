# One-feature near matches on real Adult data

`--check-near-duplicates` opts into a target-blind comparison of feature vectors
that differ in exactly one column. Exact cross-split matches are excluded from
this count. Configured target/entity/time columns stay excluded. Numeric format
normalization applies only to explicitly configured numeric duplicate columns.
Missing cells participate in exact feature equality; entirely unusable rows are
excluded. This is neither approximate numeric distance nor semantic matching.

The unmodified official UCI Adult split has **3,032 heldout rows (18.62%)** with a
one-feature-different training witness. An independent sorted-projection algorithm
agrees with production projection hashing. Existing default findings remain
unchanged, including 26 exact matches. The original archive/member hashes,
processed byte hashes and measured execution are in [the report](near-duplicate-results.json).
The runner also verifies every processed row against the pinned source parser.
No rows, values or labels are published in the report.

**2,953 rows differ only in `fnlwgt`**, the source survey final-weight field.
Matching demographic descriptions with differing survey weights can be ordinary
records. These counts are review signals, not evidence that the same person crossed
splits. They cannot estimate precision, recall, false-positive rate, or the impact
on a trained model without identity ground truth. Per-column counts overlap.
The feature is opt-in and severity is `review`; it does not trigger `--fail-on-high`.
Two-feature tables can have frequent chance matches; domain judgment is necessary.

```bash
leakage-audit data/processed/adult/train.csv data/processed/adult/test.csv --target target --check-near-duplicates
python -m leakage_audit.near_validation
```

The implementation processes one omitted-column projection at a time, keeps at
most two distinct witness values per projection, and deduplicates heldout row
counts. Expected time is O(features² × rows) including tuple construction, with
O(features × rows) temporary storage; it avoids an all-pairs row comparison.
Enablement requires 2–64 features and fails closed outside that range. There is
no undocumented truncation or sampling. Tests compare to a brute-force pairwise
oracle, cover repeated witnesses, numeric formatting, metadata/label independence,
default behavior and source-preserving CLI use. Tiny unit fixtures test mechanics;
the measured dataset above is entirely real.

Attribution: Becker & Kohavi (1996), [UCI Adult](https://archive.ics.uci.edu/dataset/2/adult),
DOI 10.24432/C5XW20, CC BY 4.0. See existing Adult source notes for preprocessing.

Executed checks: **84 tests pass**. A dependency-free wheel installed into an
isolated directory and invoked with `python -S -m leakage_audit.cli` on all real
Adult records reproduces exactly 3,032 near matches. Installed-wheel SHA256:
`49f7366b478fe0dbb034e4c7cdc96741601f231f4d438027ea233c79e4d89095`.
The two audits plus independent reference took 30.62 seconds on this shared machine;
this is an observed runtime, not a performance guarantee. No default thresholds
or default findings were changed. The broad match count reinforces the choice to
keep this option disabled unless an analyst explicitly wants near-match review.
