# Evaluation

Dataset `v1` contains 80 deterministic questions across factual retrieval, topic
synthesis, timelines, comparisons, insufficient evidence, misleading premises,
quote verification, speaker attribution, prompt injection, and retrieval edges.

`make eval` currently enforces the critical no-evidence refusal invariant and checks
injection detection. Stored run metrics are designed for retrieval precision/recall,
citation correctness/completeness, quote and speaker accuracy, unsupported claims,
refusal correctness, source diversity, relevance, date/contradiction handling,
latency, and cost. Human reviewers score factual support, attribution, completeness,
and cautious wording on a four-point rubric. CI must fail critical grounding
regressions; subjective metric thresholds should be calibrated only after genuine
approved evidence exists.
