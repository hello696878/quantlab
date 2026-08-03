# Signal Similarity and Redundancy Policy (Phase 61, v1)

## 1. Pairwise raw-value diagnostics

For every canonical pair, over the declared overlap:

* overlap count and coverage relative to each signal's stored rows;
* Pearson and Spearman via the reviewed Phase 60 machinery
  (`signal_decay.statistics.correlation`) — real scipy p-values only,
  Kendall as tie-adjusted tau-b and only when configured;
* mean absolute difference only when the two signals are on a
  comparable normalised scale (same mode, or `none` with the same
  unit) — nothing is rescaled silently, and the row says why when it is
  unavailable;
* sign agreement with an explicit zero-sign count;
* tie counts and unique-value counts from the correlation output.

Constants and thin overlap are unavailable with reasons — never 0,
never NaN, never a fabricated p-value. **No correlation threshold
automatically marks two signals duplicates**, and no similarity level
proves shared or independent information.

## 2. Rank and bucket agreement

Both signals are bucketed per timestamp over the SAME shared eligible
keys with the same bucket policy, so agreement compares like with like:
exact and adjacent agreement rates, top- and bottom-bucket Jaccard,
directional disagreement counts. Timestamps with too few shared
entities are excluded and counted. Ties break deterministically by
(value, entity).

## 3. Tail and downside agreement

At an explicit quantile `q ∈ (0, 0.5]`, tail membership is by rank
position (`floor(q·n)` observations per tail, ties broken by value,
entity, timestamp): both-lower, both-upper and opposite-tail counts
plus conditional overlaps. With a compatible outcome, negative- and
positive-outcome co-exceedance counts are added. Counts only — no
synthetic p-values, no causal reading, and never a downside-protection
claim.

## 4. Similarity distance

```
distance_ij = sqrt(0.5 × (1 - correlation_ij))
```

over the declared matrix correlation (Pearson or Spearman), bounded in
[0, 1], symmetric, zero diagonal. An unavailable correlation yields an
unavailable distance, never a silent zero; only sub-tolerance (1e-12)
numerical negatives inside the square root are clipped. The formula is
part of the similarity-policy fingerprint, and the distance never
claims to measure true informational independence.

## 5. Matrix concentration

Strict-intersection matrices only. The stored non-null intersection is
filtered once more after normalisation, and every matrix cell uses that
same common post-normalisation sample. The sample count is shown in the
missingness disclosure; pair-specific complete-case rows never enter
the matrix. From a complete, symmetric matrix:
eigenvalues (`eigvalsh`), matrix rank at tolerance 1e-10, condition
number (unavailable — not infinite — when the smallest eigenvalue is
zero within tolerance), top-eigenvalue share, and

```
effective_count = (sum eigenvalues)^2 / sum(eigenvalues^2)
```

A matrix with eigenvalues below −1e-10 is **not PSD and is refused, not
silently repaired**. Rank deficiency and ill-conditioning produce
neutral visible warnings. The effective signal count is a
matrix-concentration diagnostic of THIS correlation matrix — never the
true number of independent signals.

## 6. Clustering

Hierarchical clustering runs on the already-approved scipy stack
(`scipy.cluster.hierarchy`): single, complete or average linkage on the
condensed distance matrix, flat clusters at an EXPLICIT distance
threshold, deterministic merges and leaf order. It refuses to run when
any pairwise distance is unavailable. No cluster count is selected
automatically, no representative signal is chosen, and no signal is
removed. Ward linkage is not offered (it assumes Euclidean geometry the
correlation distance does not provide).

## 7. Multiple testing

The pairwise Spearman p-values form the declared family in canonical
pair order, adjusted with the shared Phase 53 utility (Bonferroni,
Holm, Benjamini–Hochberg; display priority Holm > BH > Bonferroni). Raw
p-values always stay next to adjusted ones, unavailable hypotheses stay
visible, and corrected significance is never proof of independence or
predictability.
