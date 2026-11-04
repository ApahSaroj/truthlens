# Real documents: v0.5.3 vs v0.6.0

Run in the sandbox on 4 Nov 2026 (Linux, Python 3.12). Deep mode depends on live sources; during one run MoSPI returned HTTP 502 and the Lok Sabha archive timed out, so the affected documents were re-run. Wall times are indicative only (2 to 5 runs in parallel).

Documents: Karnataka SWP 2022, Maharashtra SWP 2019, Orissa SWP 2007, Kerala State Planning Board drinking-water report, Andhra Pradesh RWS O&M policy 2025, UP State Water Policy 1999 (IELRC transcription, not official), UP Draft SWP 2020 (Feb 2020), UP SWP 2020 final draft (UPWaMReC, FAOLEX copy), UP Policy for Sustainable Ground Water Management 2013.

| Doc | Mode | Version | Statements | Checkable | Supported | Partly | Wrong | Dated | Needs a source | Not checked this run | Wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ka_swp2022 | quick | 0.5.3 (d6b86ed) | 481 | 22 | 0 | 1 | 0 | 0 | 2 | 19 | 1.2 |
| ka_swp2022 | quick | 0.6.0 | 481 | 22 | 1 | 0 | 0 | 0 | 2 | 19 | 0.6 |
| ka_swp2022 | deep | 0.5.3 (d6b86ed) | 481 | 22 | 0 | 1 | 0 | 0 | 3 | 18 | 42.5 |
| ka_swp2022 | deep | 0.6.0 | 481 | 22 | 1 | 0 | 0 | 0 | 3 | 18 | 50.7 |
| mh_swp2019 | quick | 0.5.3 (d6b86ed) | 581 | 100 | 0 | 1 | 0 | 0 | 57 | 42 | 0.6 |
| mh_swp2019 | quick | 0.6.0 | 581 | 100 | 1 | 0 | 0 | 0 | 57 | 42 | 1.6 |
| mh_swp2019 | deep | 0.5.3 (d6b86ed) | 581 | 100 | 0 | 1 | 0 | 0 | 81 | 18 | 46.4 |
| mh_swp2019 | deep | 0.6.0 | 581 | 100 | 1 | 0 | 0 | 0 | 80 | 19 | 48.5 |
| od_swp2007 | quick | 0.5.3 (d6b86ed) | 374 | 67 | 0 | 0 | 0 | 0 | 20 | 47 | 2.2 |
| od_swp2007 | quick | 0.6.0 | 374 | 67 | 0 | 0 | 0 | 0 | 20 | 47 | 2.0 |
| od_swp2007 | deep | 0.5.3 (d6b86ed) | 374 | 67 | 0 | 0 | 0 | 0 | 48 | 19 | 38.6 |
| od_swp2007 | deep | 0.6.0 | 374 | 67 | 0 | 0 | 0 | 0 | 50 | 17 | 33.3 |
| kl_spb_dw | quick | 0.5.3 (d6b86ed) | 1973 | 526 | 0 | 0 | 0 | 0 | 287 | 239 | 2.0 |
| kl_spb_dw | quick | 0.6.0 | 1973 | 526 | 0 | 0 | 0 | 0 | 287 | 239 | 8.7 |
| kl_spb_dw | deep | 0.5.3 (d6b86ed) | 1973 | 526 | 0 | 0 | 0 | 0 | 496 | 30 | 60.7 |
| kl_spb_dw | deep | 0.6.0 | 1973 | 526 | 0 | 0 | 0 | 0 | 492 | 34 | 61.9 |
| ap_rws_om2025 | quick | 0.5.3 (d6b86ed) | 1948 | 343 | 0 | 0 | 0 | 0 | 195 | 148 | 6.9 |
| ap_rws_om2025 | quick | 0.6.0 | 1948 | 341 | 0 | 0 | 0 | 0 | 193 | 148 | 6.2 |
| ap_rws_om2025 | deep | 0.5.3 (d6b86ed) | 1948 | 343 | 0 | 0 | 0 | 0 | 325 | 18 | 31.4 |
| ap_rws_om2025 | deep | 0.6.0 | 1948 | 341 | 0 | 0 | 0 | 0 | 325 | 16 | 48.1 |
| up_swp1999 | quick | 0.5.3 (d6b86ed) | 327 | 69 | 0 | 0 | 0 | 0 | 21 | 48 | 3.8 |
| up_swp1999 | quick | 0.6.0 | 327 | 69 | 0 | 0 | 0 | 1 | 21 | 47 | 1.2 |
| up_swp1999 | deep | 0.5.3 (d6b86ed) | 327 | 69 | 0 | 0 | 0 | 0 | 49 | 20 | 56.0 |
| up_swp1999 | deep | 0.6.0 | 327 | 69 | 0 | 0 | 0 | 1 | 49 | 19 | 48.1 |
| up_swp2020d | quick | 0.5.3 (d6b86ed) | 304 | 38 | 0 | 0 | 0 | 0 | 14 | 24 | 2.4 |
| up_swp2020d | quick | 0.6.0 | 304 | 38 | 0 | 1 | 0 | 0 | 14 | 23 | 0.8 |
| up_swp2020d | deep | 0.5.3 (d6b86ed) | 304 | 38 | 0 | 0 | 0 | 0 | 20 | 18 | 55.7 |
| up_swp2020d | deep | 0.6.0 | 304 | 38 | 0 | 1 | 0 | 0 | 19 | 18 | 49.7 |
| up_swp2020f | quick | 0.5.3 (d6b86ed) | 642 | 91 | 0 | 0 | 0 | 0 | 62 | 29 | 3.6 |
| up_swp2020f | quick | 0.6.0 | 642 | 91 | 0 | 0 | 0 | 0 | 62 | 29 | 1.2 |
| up_swp2020f | deep | 0.5.3 (d6b86ed) | 642 | 91 | 0 | 0 | 0 | 0 | 68 | 23 | 42.6 |
| up_swp2020f | deep | 0.6.0 | 642 | 91 | 0 | 0 | 0 | 0 | 68 | 23 | 52.7 |
| up_gw2013 | quick | 0.5.3 (d6b86ed) | 349 | 94 | 0 | 0 | 0 | 0 | 65 | 29 | 4.8 |
| up_gw2013 | quick | 0.6.0 | 349 | 94 | 0 | 0 | 0 | 0 | 65 | 29 | 1.4 |
| up_gw2013 | deep | 0.5.3 (d6b86ed) | 349 | 94 | 0 | 0 | 0 | 0 | 71 | 23 | 58.4 |
| up_gw2013 | deep | 0.6.0 | 349 | 94 | 0 | 0 | 0 | 0 | 71 | 23 | 55.7 |


## Every verdict that changed, checked by hand against Census 2011

- Karnataka 2022: 191,791 / 3,287,469 sq km = 5.83% of India's area. Now SUPPORTED (was partly supported).
- Maharashtra 2019: 112.37 million people and 0.3077 million sq km match Census 2011. Now SUPPORTED (was partly supported).
- UP 1999: "29.44 million ha" = 294,411 sq km = UP 240,928 + Uttarakhand 53,483 (undivided UP, before 9 Nov 2000). Now DATED, not wrong.
- UP Draft 2020: "7.33% of land area" matches Census 2011. "16.17% of population" differs from Census 2011 (16.50%); the draft gives no year, so it is partly supported, not wrong.
- Andhra Pradesh 2025: two checkable claims fewer; both were instructions ("See that...", "Verify..."), now set aside as not checkable facts.

0 claims marked wrong in any document, before or after.
