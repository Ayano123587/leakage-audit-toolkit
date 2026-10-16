# Checks and source

The real-data workflow uses [UCI Adult](https://archive.ics.uci.edu/dataset/2/adult),
Becker and Kohavi (1996), DOI 10.24432/C5XW20, CC BY 4.0. Preparation strips field
whitespace, removes the test-label terminal period and maps `?` to missing. It
neither removes observations nor changes the official split.

Exact matches compare feature strings after excluding configured target, entity
and time fields. Optional one-feature near matching uses projection hashing,
requires 2–64 features and excludes exact matches. Per-field counts can overlap;
unique heldout rows are counted once. Numeric duplicate normalization uses exact
Decimal comparisons only for explicitly named columns.

Numeric drift is an empirical KS distance; categorical drift is total variation.
Both use effect-size thresholds, not significance tests. Missingness is checked
separately. Numeric target proxies use training-only absolute Pearson correlation;
category proxies require low cardinality and at least five observations per group.
A strong predictor can be legitimate, and nonlinear proxies can be missed.

Entity overlap checks membership. Time overlap compares the heldout timestamp
with the global training cutoff plus an explicit embargo. Naive timestamps mean
UTC; aware timestamps are converted to UTC. The check is not per-entity ordering.

Nonfinite numeric values are reported and excluded from statistics. Duplicate
comparisons preserve string identity. Default auditing ignores heldout labels;
label-quality inspection is a separate opt-in. Reports omit row values but include
schema names, so reports still need appropriate access controls.

The package reads the input into memory. It does not inspect preprocessing code,
feature-availability contracts, join lineage, semantic identity or deployment
conditions. Domain review is required before treating a finding as leakage.

Background: [scikit-learn leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage)
and [Kapoor & Narayanan](https://arxiv.org/abs/2207.07048).
