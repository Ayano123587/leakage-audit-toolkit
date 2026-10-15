# Authentic UCI Wine validation

Source: [UCI Wine](https://archive.ics.uci.edu/dataset/109/wine). Citation: Aeberhard, S. & Forina, M. (1992). Wine [Dataset]. UCI Machine Learning Repository. [DOI 10.24432/C5PC7J](https://doi.org/10.24432/C5PC7J). The UCI page explicitly licenses it under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

Run `python -m leakage_audit.wine_validation --download`. The official 6,038-byte ZIP and its wine.data member are checked against pinned SHA256 hashes in wine-dataset-provenance.json. The loader reads members directly without extracting arbitrary ZIP paths, validates 178 records with 13 features and one label, and creates ignored CSV partitions. Cached archives are also verified. No runtime dependency was added.

## Controls and actual observations

Seeds 0–19 construct stratified 75/25 partitions: 133 training and 45 heldout rows. No measurement values are modified. At default shift threshold .3 and proxy threshold .98, all 20 partitions have zero findings. These dependent partitions of one small dataset are not verified leakage-free ground truth, so they do not estimate production specificity or sensitivity.

At shift threshold .1, 20/20 unmodified partitions trigger drift reviews; at .2, 7/20; at .3/.5, 0/20. These fixed threshold diagnostics illustrate sampling variation and warning tradeoffs. An unmodified first-133/last-45 source-order partition produces 10 drift reviews. The file is cultivar ordered, so composition changes are expected; drift does not prove leakage. Source order is not presented as observation chronology.

## Separately injected controls

Every injection starts from the same seed-42 stratified split, whose baseline has zero findings. Defects do not accumulate.

| Case | Deliberate change | Expected signal observed |
| --- | --- | --- |
| Duplicate | Replace five heldout chemical vectors with training vectors; preserve test targets | Five duplicate rows |
| Proxy | Add a categorical encoding of the cultivar target | Train-only deterministic mapping |
| Shift | Add 30 to all heldout alcohol values | Empirical KS distance 1 |
| Missingness | Empty alcohol in 27 of 45 heldout rows | Missing fraction difference .6 |
| Entity | Manufacture disjoint row IDs, then overwrite five | Five entity overlaps |
| Time | Manufacture forward timestamps, then overwrite five with past dates | Five temporal overlaps |

All six expected signals were detected. They are constructed injections, **not naturally discovered Wine leakage**. Wine has no genuine entity/time fields. Distribution and missingness shifts remain review signals, not leakage verdicts.

[Executed results](wine-validation-results.json) retain control seeds, thresholds, findings and caveats. The six original synthetic controls also still pass. This exercise does not guarantee detection of preprocessing leakage, semantic duplicates, nonlinear proxies or feature-availability errors.
