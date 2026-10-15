# Confirmed edge-case corrections

- Nonfinite embargo values previously passed the nonnegative-only guard. Configuration now rejects them; datetime cutoff and timezone overflow become clear validation errors.
- Empty/whitespace headers, duplicate names, malformed quotes, row-width mismatches, nested values and aliased metadata columns are rejected. UTF-8 BOMs, Unicode names and quoted newlines remain supported.
- Near-maximum finite values previously overflowed Pearson calculations or silently lost correlations. Scaling and accurate summation now produce bounded finite scores.
- Infinities previously forced otherwise numeric columns into categorical drift. They now receive separate quality findings and are excluded from proxy/drift distributions. Recognized NaN markers remain missing.
- A rare singleton category could satisfy an average-support mapping heuristic. Every category now requires at least five training observations.
- Unordered categorical summation could change the last bits across Python hash seeds. Sorted keys and accurate summation make report scores reproducible.
- Inclusive empirical thresholds now allow 1e-12 absolute rounding tolerance; exact fraction differences can otherwise fall just below a threshold.
- Entirely unusable feature rows no longer become high-severity duplicate evidence. Other comparisons deliberately preserve raw representations: `1` and `1.0` are not semantic duplicates.
- The CLI rejects output paths that would overwrite either source dataset, and reports output I/O failures as exit-2 diagnostics.

Tests cover these regressions, timezone/embargo boundaries, label independence, JSON finiteness, deterministic reports and CLI behavior. Strong legitimate predictors can still produce proxy reviews; group overlap can be valid; global temporal ordering cannot establish per-entity availability. No automatic cleaning, feature deletion or artificial model training is performed.
