# One-feature near-duplicate audit protocol

Prespecified before implementation or scoring: add an explicit opt-in audit for
cross-split feature vectors that differ in exactly one feature. This complements
exact matching without floating-point tolerances, learned embeddings, or target
access. Preserve existing numeric-normalization semantics. Exclude exact matches
and all-missing vectors. Report aggregate counts and differing column only, never
row values, row identifiers, or labels. A near match is a review signal, not proof
of shared identity or harmful leakage. Low-dimensional tables can match by chance.

Use projection hashing rather than an all-pairs scan. Bound feature count at64
when enabled; report unique heldout rows and per-column counts (which can overlap).
Validate against an independent brute-force oracle on small fixtures, target-label
invariance, numeric formatting, missingness, and source-preserving CLI execution.
Evaluate the unmodified official UCI Adult split and retain observed counts,
source hashes and elapsed time. Do not inject synthetic rows into the real study
or claim sensitivity/precision without ground-truth duplication labels.

Follow-up review: inspect projection collision behavior and repeated signatures;
check package/CLI output and unchanged default audit results. No trained-model
score applies to this deterministic diagnostic tool.
