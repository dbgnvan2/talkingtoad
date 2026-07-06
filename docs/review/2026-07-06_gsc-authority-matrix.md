---
status: validation report (V4 — GSC Authority-Matrix)
date: 2026-07-06
site: https://livingsystems.ca/
window_days: 30
data_source: SYNTHETIC FIXTURE (no live GSC)
---

# V4 — GSC Authority-Matrix (HealthScore x GSC clicks)

> **NOTE:** This report was rendered from a SYNTHETIC fixture to demonstrate the quadrant/correlation logic. No live GSC data was available in this session (creds absent). Re-run per the header steps once the owner connects Search Console for real numbers.

## Split thresholds (median)

- Health median: 67.5
- Clicks median: 155.0
- Health↔clicks Pearson correlation: 0.283

## Quadrant counts

| Quadrant | Meaning | Pages |
|---|---|---|
| healthy_and_found | high health · high clicks (as expected) | 2 |
| healthy_but_unfound | high health · LOW clicks (**disagree**) | 1 |
| unhealthy_but_found | LOW health · high clicks (**disagree**) | 1 |
| unhealthy_and_unfound | low health · low clicks (as expected) | 2 |

## Disagreement pages (calibration signal — R3 §6, AC V4.2)

Pages where structural health and real search performance strongly disagree.

| Page | Health | Clicks | Quadrant |
|---|---|---|---|
| https://x/underrated | 40 | 420 | unhealthy_but_found |
| https://x/hidden-gem | 88 | 5 | healthy_but_unfound |
