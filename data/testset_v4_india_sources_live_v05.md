# testset_v4_india_sources.jsonl: live run v05

- Correct: **21/25 = 84.0%**
- Unsafe SUPPORTED: 1
- Contradictions caught: 5/6
- Wall time: 46 s

| id | expected | got | method | sentence |
|---|---|---|---|---|
| 601 | SUPPORTED | SUPPORTED | live-official-data | The RBI's policy repo rate is 5.50%. |
| 602 | CONTRADICTED | CONTRADICTED | live-official-data | The cash reserve ratio currently stands at 4%. |
| 603 | SUPPORTED | SUPPORTED | live-official-data | The statutory liquidity ratio is 18%. |
| 604 | SUPPORTED | UNVERIFIED ✗ | heuristic | India's foreign exchange reserves stood at US$719.7 billion in the week ended October 23, 2026. |
| 605 | SUPPORTED | UNVERIFIED ✗ | heuristic | Gold accounted for US$103.15 billion of India's foreign exchange reserves as on October 23, 2026. |
| 606 | CONTRADICTED | UNVERIFIED ✗ | heuristic | Scheduled commercial banks' credit grew 11.6% year-on-year as of mid-October 2026. |
| 607 | SUPPORTED | SUPPORTED | live-official-data | Gujarat had an installed power generation capacity of 79,508.78 MW in September 2026. |
| 608 | CONTRADICTED | CONTRADICTED | live-official-data | Rajasthan's installed generation capacity was 70,000 MW in September 2026. |
| 609 | SUPPORTED | SUPPORTED | live-official-data | All-India peak demand met was 258.27 GW in August 2026. |
| 610 | CONTRADICTED | CONTRADICTED | live-official-data | India's peak power demand met reached 270 GW in August 2026. |
| 611 | SUPPORTED | SUPPORTED | live-official-data | India imported 246.6 million tonnes of crude oil in 2025-26. |
| 612 | CONTRADICTED | CONTRADICTED | live-official-data | India's crude oil imports were 300 million tonnes in 2025-26. |
| 613 | SUPPORTED | SUPPORTED | live-official-data | Consumption of diesel (HSD) was 94.7 million tonnes in 2025-26. |
| 614 | SUPPORTED | SUPPORTED | live-official-data | Total petroleum product consumption was 241.6 million tonnes in 2025-26. |
| 615 | SUPPORTED | SUPPORTED | live-official-data | The retail selling price of petrol in Delhi is ₹102.12 per litre. |
| 616 | SUPPORTED | SUPPORTED | live-official-data | Goa has provided tap water connections to 100% of its rural households. |
| 617 | SUPPORTED | SUPPORTED | live-official-data | Ladakh has tap water connections in 98.53% of rural households. |
| 618 | CONTRADICTED | CONTRADICTED | live-official-data | Ladakh has tap water connections in 90% of rural households. |
| 619 | UNVERIFIED | SUPPORTED ✗ | heuristic | The repo rate was 6.5%. |
| 620 | UNVERIFIED | UNVERIFIED | heuristic | The stage of groundwater extraction in Punjab was 156.36% in 2024. |
| 621 | SUPPORTED | SUPPORTED | heuristic | A 2019 study using GRACE satellite data and more than 5,000 wells found that groundwater pumping to increase food production causes persistent groundwater drought in India. |
| 622 | SUPPORTED | SUPPORTED | heuristic | Groundwater pumping to increase food production causes persistent groundwater drought in India (arXiv:1908.00255). |
| 623 | UNVERIFIED | UNVERIFIED | heuristic | A study (arXiv:2601.99999) found that India's groundwater levels rose 40% after 2020. |
| 624 | UNVERIFIED | UNVERIFIED | heuristic | A PhD thesis on Shodhganga found that 62% of wells in Telangana were over-exploited. |
| 625 | SUPPORTED | SUPPORTED | live-official-data | CEA data show that the all-India plant load factor was 66.85% in August 2026. |
