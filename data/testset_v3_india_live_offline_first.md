# testset_v3_india_live.jsonl: offline run first

- Correct: **10/25 = 40.0%**
- Unsafe SUPPORTED: 0
- Contradictions caught: 1/6
- Wall time: 0 s

| id | expected | got | method | sentence |
|---|---|---|---|---|
| 501 | SUPPORTED | UNVERIFIED ✗ | heuristic | Average monthly per capita consumption expenditure in rural India was ₹4,122 in 2023-24. |
| 502 | SUPPORTED | UNVERIFIED ✗ | heuristic | Average monthly per capita consumption expenditure in urban India was ₹6,996 in 2023-24. |
| 503 | CONTRADICTED | UNVERIFIED ✗ | heuristic | Average monthly per capita consumption expenditure in rural India was ₹5,122 in 2023-24. |
| 504 | SUPPORTED | UNVERIFIED ✗ | heuristic | India's sex ratio was 943 females per 1,000 males in the 2011 Census. |
| 505 | SUPPORTED | UNVERIFIED ✗ | heuristic | Kerala's sex ratio was 1,084 in 2011. |
| 506 | CONTRADICTED | UNVERIFIED ✗ | heuristic | Bihar's sex ratio was 950 in 2011. |
| 507 | SUPPORTED | UNVERIFIED ✗ | heuristic | India had 1,168 universities in 2021-22. |
| 508 | CONTRADICTED | UNVERIFIED ✗ | heuristic | India had 1,500 universities in 2021-22. |
| 509 | SUPPORTED | SUPPORTED | deterministic-numeric | Industrial production (IIP) grew 4.3% in 2025-26. |
| 510 | SUPPORTED | SUPPORTED | deterministic-numeric | In NFHS-5, 35.5% of children under five were stunted. |
| 511 | CONTRADICTED | CONTRADICTED | deterministic-numeric | Child stunting in NFHS-5 was 38.4%. |
| 512 | SUPPORTED | UNVERIFIED ✗ | heuristic | In a Lok Sabha answer on 6 August 2026, the Ministry of Jal Shakti addressed the extension of the Jal Jeevan Mission. |
| 513 | SUPPORTED | UNVERIFIED ✗ | heuristic | The Rajya Sabha took up a question on the Jal Jeevan Mission in Tamil Nadu in March 2025. |
| 514 | SUPPORTED | SUPPORTED | heuristic | The Jal Jeevan Mission was launched in August 2019. |
| 515 | CONTRADICTED | UNVERIFIED ✗ | heuristic | The Jal Jeevan Mission is implemented by the Ministry of Education. |
| 516 | SUPPORTED | SUPPORTED | deterministic-numeric | India's population in the 2011 Census was 121.09 crore. |
| 517 | SUPPORTED | SUPPORTED | deterministic-numeric | The PLFS unemployment rate on usual status was 3.2% in 2023-24. |
| 518 | SUPPORTED | SUPPORTED | deterministic-numeric | Wholesale price inflation was 2.3% in 2024-25. |
| 519 | SUPPORTED | SUPPORTED | deterministic-numeric | CPI inflation was 2.1% in 2025-26. |
| 520 | SUPPORTED | SUPPORTED | deterministic-numeric | The fiscal deficit is budgeted at 4.3% of GDP for 2026-27. |
| 521 | CONTRADICTED | UNVERIFIED ✗ | heuristic | India's sex ratio was 940 in 2011. |
| 522 | SUPPORTED | UNVERIFIED ✗ | heuristic | In 2011, Haryana recorded a sex ratio of 879. |
| 523 | PARTLY SUPPORTED | UNVERIFIED ✗ | heuristic | Urban MPCE was ₹6,996 in 2023-24, nearly 70% higher than in rural India. |
| 524 | SUPPORTED | SUPPORTED | deterministic-numeric | The revised estimate of the fiscal deficit for 2025-26 is 4.4% of GDP. |
| 525 | SUPPORTED | UNVERIFIED ✗ | heuristic | A 2026 study of 926 households in Samastipur, Bihar found that 84.9 per cent had a functional tap connection. |
