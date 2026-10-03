# AnnotationOps Metrics & Statistical Formulation Reference

This document details the mathematical formulations, business interpretations, operational targets, and reconciliation proofs implemented across the AnnotationOps metrics engine (`pipeline/metrics.py`).

> [!NOTE]
> **Synthetic Portfolio Simulation:** All operational SLAs, target thresholds, and benchmark baselines described herein are project-defined simulation standards established for portfolio demonstration. They do not represent internal proprietary metrics of any external corporation.

---

## 1. Operational & Throughput Metrics

### 1.1 Completion Rate & Workload Velocity
- **Formula:**
  $$\text{Completion Rate (\%)} = \left( \frac{\text{Distinct Completed Assets}}{\text{Total Ingested Assets}} \right) \times 100$$
- **Business Interpretation:** Measures the proportion of the catalog workload that has completed at least one verified annotation pass.
- **Simulation Target:** $\ge 85.0\%$

### 1.2 Backlog Waterfall Reconciliation
- **Mathematical Identity:**
  $$\text{Closing Backlog}_{t} = \text{Opening Backlog}_{t} + \text{New Tasks Ingested}_{t} - \text{Completed Tasks}_{t}$$
- **Invariant:**
  $$\text{Total Catalog Tasks} = \text{Completed Tasks} + \text{Pending Backlog}$$
- **Status Model:** Every task in the queue occupies exactly one mutually exclusive status:
  - `COMPLETED`: Passed validation and archived in warehouse.
  - `PENDING`: In queue awaiting annotator pickup.
  - `REWORK`: Flagged during audit for secondary re-annotation.
  - `ESCALATED`: Flagged for specialist or supervisor review.
- **Verification:** Tested by `tests/unit/test_backlog_reconciliation.py`.

### 1.3 Cycle Time & Pacing
- **Average Duration:** $\bar{t} = \frac{1}{N} \sum_{i=1}^N t_i$
- **Median Duration:** Ordered 50th percentile duration value (robust against long-tail pauses).
- **Simulation Target:** Average cycle time $\le 12.0\text{ seconds}$.
- **Anomaly Detection:**
  - $\text{Duration} < 3.0\text{s}$: Flagged with `WARN_SPEED_ANOMALY_FAST` (operator rushed review).
  - $\text{Duration} < 0.5\text{s}$ or $> 1800\text{s}$: Hard rejection at Stage 4 (`ERR_IMPOSSIBLE_TIME`).

### 1.4 Pipeline Rejection Rate
- **Formula:**
  $$\text{Rejection Rate (\%)} = \left( \frac{\text{Blocked Submissions}}{\text{Valid Submissions} + \text{Blocked Submissions}} \right) \times 100$$
- **Business Interpretation:** Measures upstream guideline friction or schema defects caught by the validation firewall before entering clean warehouse tables.
- **Simulation Target:** $\le 3.0\%$

### 1.5 Rework & Escalation Rates
- **Rework Rate:** $\left(\frac{\text{Rework Submissions}}{\text{Completed Submissions}}\right) \times 100$ (Simulation Target: $\le 5.0\%$).
- **Escalation Rate:** $\left(\frac{\text{Escalated Submissions}}{\text{Total Workload}}\right) \times 100$ (Simulation Target: $\le 3.0\%$).

---

## 2. Quality Science & Statistical Reliability Metrics

### 2.1 Cohen's Kappa Coefficient ($\kappa$)
Evaluates agreement between annotators or against verified ground truth, corrected for hypothetical chance concordance.

- **Formula:**
  $$\kappa = \frac{P_o - P_e}{1 - P_e}$$
  where:
  - $P_o$: Observed proportional agreement across all evaluated items:
    $$P_o = \frac{1}{N} \sum_{i=1}^N \mathbb{I}(y_i = \hat{y}_i)$$
  - $P_e$: Expected agreement by chance under independent marginal label distributions:
    $$P_e = \sum_{c \in \mathcal{C}} P(y = c) \cdot P(\hat{y} = c)$$
- **Scale:**
  - $\kappa \ge 0.85$: Strong / Near-Perfect Agreement (Target Envelope)
  - $0.70 \le \kappa < 0.85$: Moderate Agreement
  - $\kappa < 0.70$: Guideline Ambiguity / Calibration Priority

### 2.2 Per-Class Precision, Recall, and F1-Score
For each primary product condition $c \in \{\text{NEW}, \text{OPEN\_BOX}, \text{DAMAGED}\}$:

- **Precision ($P_c$):** $\frac{\text{TP}_c}{\text{TP}_c + \text{FP}_c}$
  *Measures label purity: what fraction of items labeled as condition $c$ actually possessed condition $c$.*
- **Recall ($R_c$):** $\frac{\text{TP}_c}{\text{TP}_c + \text{FN}_c}$
  *Measures defect coverage: what fraction of actual condition $c$ items were correctly identified.*
- **F1-Score ($F1_c$):**
  $$F1_c = 2 \times \frac{P_c \times R_c}{P_c + R_c}$$
- **Macro-Averaged F1:**
  $$\text{Macro F1} = \frac{1}{|\mathcal{C}|} \sum_{c \in \mathcal{C}} F1_c$$

---

## 3. Simulated SLA Attainment & Variance Analysis

### 3.1 Variance Formulation
- **Absolute Variance:**
  $$\Delta_{\text{abs}} = \text{Actual Result} - \text{Simulated Target}$$
- **Percentage Variance:**
  $$\Delta_{\%} = \left( \frac{\text{Actual Result} - \text{Simulated Target}}{\text{Simulated Target}} \right) \times 100$$

### 3.2 Evaluation Rules
| Metric Key | Benchmark Rule | Target Value | Unit | Success Condition |
| :--- | :--- | :--- | :--- | :--- |
| `quality_accuracy_pct` | `MINIMUM` | 95.0 | % | $\text{Actual} \ge \text{Target}$ |
| `rejection_rate_pct` | `MAXIMUM` | 3.0 | % | $\text{Actual} \le \text{Target}$ |
| `avg_processing_time_sec` | `MAXIMUM` | 12.0 | s | $\text{Actual} \le \text{Target}$ |
| `cohens_kappa` | `MINIMUM` | 0.85 | score | $\text{Actual} \ge \text{Target}$ |
| `completion_rate_pct` | `MINIMUM` | 85.0 | % | $\text{Actual} \ge \text{Target}$ |

---

## 4. Multi-Rater Inter-Annotator Agreement (IAA)

On tasks assigned to $K \ge 2$ distinct annotators:
- **Pairwise Concordance:** Proportion of multi-annotated task assets where all assigned annotators agreed unanimously on the primary condition classification.
- **Cross-Calibration:** Disagreements trigger supervisory arbitration and automated rework routing.
