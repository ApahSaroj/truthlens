# testset_v041_heldout.jsonl: live run first

- Correct: **22/25 = 88.0%**
- Unsafe SUPPORTED: 0
- Contradictions caught: 5/6
- Wall time: 41 s (run in chunks: scripts/run_live_chunks.py)

| id | expected | got | method | sentence |
|---|---|---|---|---|
| 701 | SUPPORTED | SUPPORTED | deterministic-numeric | In our view, CPI inflation fell to 2.1 per cent in 2025-26. |
| 702 | SUPPORTED | SUPPORTED | deterministic-change | Arguably, retail inflation has fallen every year since 2023-24. |
| 703 | CONTRADICTED | CONTRADICTED | deterministic-change | I think the unemployment rate has been rising every year since 2017-18. |
| 704 | SKIPPED | SKIPPED | skipped | We believe the government should raise spending on rural water supply. |
| 705 | CONTRADICTED | CONTRADICTED | deterministic-numeric | Headline retail inflation averaged 2.0 per cent in 2025-26. |
| 706 | SUPPORTED | SUPPORTED | deterministic-numeric | Real GDP grew about 8 per cent in 2025-26. |
| 707 | SUPPORTED | SUPPORTED | deterministic-numeric | Real GDP grew 7.8% in 2025-26, up from 7.2% in 2024-25. |
| 708 | SUPPORTED | SUPPORTED | deterministic-change | Real GDP growth dipped from 7.3 per cent in 2023-24 to 7.2 per cent in 2024-25. |
| 709 | SUPPORTED | SUPPORTED | deterministic-change | WPI inflation turned positive in 2024-25, rising by 3 percentage points from the previous year. |
| 710 | SUPPORTED | SUPPORTED | deterministic-change | The fiscal deficit fell from 6.4 per cent of GDP in 2022-23 to 5.6 per cent in 2023-24. |
| 711 | CONTRADICTED | CONTRADICTED | deterministic-change | The fiscal deficit rose by 0.4 percentage points in 2025-26 compared with 2024-25. |
| 712 | SUPPORTED | SUPPORTED | deterministic-numeric | According to MoSPI's PLFS, the usual-status unemployment rate was 3.2% in 2023-24. |
| 713 | SUPPORTED | SUPPORTED | deterministic-numeric | NFHS-5 found that 35.5% of children under five were stunted. |
| 714 | CONTRADICTED | CONTRADICTED | deterministic-numeric | Under NFHS-5, child wasting was 21.0%. |
| 715 | SUPPORTED | SUPPORTED | live-official-data | The RBI's policy repo rate is 5.5 per cent. |
| 716 | SUPPORTED | UNVERIFIED ✗ | heuristic | The CRR currently stands at 3 per cent. |
| 717 | SUPPORTED | CONTRADICTED ✗ | deterministic-change | Female LFPR on usual status rose from 37.0% in 2022-23 to 41.7% in 2023-24, a rise of 4.7 percentage points. |
| 718 | SUPPORTED | SUPPORTED | deterministic-change | IIP growth slowed by 1.4 percentage points in 2025-26 compared with 2024-25. |
| 719 | SUPPORTED | SUPPORTED | deterministic-numeric | Nominal GDP reached ₹345 lakh crore in 2025-26. |
| 720 | SUPPORTED | SUPPORTED | deterministic-numeric | India's population was 121 crore in the 2011 Census. |
| 721 | SUPPORTED | SUPPORTED | heuristic | The Jal Jeevan Mission (JJM) is run by the Ministry of Jal Shakti. |
| 722 | CONTRADICTED | CONTRADICTED | deterministic-numeric | Arguably, India's real GDP growth in 2024-25 was 6.5 per cent. |
| 723 | CONTRADICTED | UNVERIFIED ✗ | heuristic | Peak power demand met in August 2026 was higher than in July 2026. |
| 724 | SUPPORTED | SUPPORTED | live-official-data | In my opinion, tap water now reaches 100% of rural households in Goa. |
| 725 | SUPPORTED | SUPPORTED | heuristic | Array programming with NumPy is described in a Nature paper (doi:10.1038/s41586-020-2649-2). |
