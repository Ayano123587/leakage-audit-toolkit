# Methodology and evidence

Data leakage depends on whether information is available at prediction time. A static CSV cannot establish that fact. Split Sentinel separates high-risk structural evidence from association/shift review signals.

Primary references researched for this implementation:

- [Scikit-learn common pitfalls: data leakage](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage): fit transformations on training data and use pipelines. This tool does not inspect estimator code and cannot verify that practice.
- [Scikit-learn TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html): forward ordering and a gap can prevent nearby observations crossing a temporal boundary. The toolkit reports a global cutoff and a time-based embargo, not sklearn's row-count gap.
- [Kapoor and Narayanan, Leakage and the Reproducibility Crisis in ML-based Science](https://arxiv.org/abs/2207.07048): leakage has multiple sources beyond row overlap.

## Synthetic benchmark protocol

Use Python `random.Random(42)`. Generate 200 training and 200 test rows with disjoint entities, chronological timestamps, Gaussian numeric features, three categories and random binary labels. Generate six independent controls: clean; ten duplicated feature rows; ten entity overlaps; ten past test timestamps; an affine encoding of the target; and numeric test features shifted by +8.

Every case is regenerated from the same original pair so defects do not accumulate. The committed JSON is the output of an actual execution. The success count is correctness on these controls, not sensitivity, specificity or AUC on production data. The random values and rows are not committed. No network or external dataset is needed to reproduce the benchmark.

## Computational and statistical limits

The empirical KS statistic uses sorted unique numeric values and exact cumulative frequencies, so tied values are handled together. It is an effect-size threshold, without a sample-size-dependent p-value. Categorical distance is half the sum of absolute probability differences over the union of observed categories. Missingness is handled separately. High cardinality can make categorical distance uninformative.

Pearson catches affine numeric proxies, including inverse relationships, but can flag valid powerful predictors and miss nonlinear proxies. Category mappings are checked only for 2�20 categories with at least five observations per category on average. Unique IDs are excluded from that check. Signals use training labels only; test labels do not drive proxy detection.

The package reads all rows into memory. Approximate matching, chunked billion-row scanning, per-entity feature availability and join lineage are future extensions, not current capabilities. Audit output omits dataset values but can contain schema names; review report access accordingly.
