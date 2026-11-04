# Match by meaning (v0.7.0): hand-check

Checked by hand on 4 Nov 2026 by the developer (one person, not blind to the method). A match is counted right when the new
sentence makes the same specific point as the old one (same subject and same kind of statement); a pair on the same
broad subject but a different point is counted wrong. Model: bge-small-en-v1.5 (ONNX, quantised); match score threshold
0.10. Reports: `eval-v07/` next to the repository (not part of the package).

## UP State Water Policy 1999 → 2020 (FAOLEX text): every matched pair

Summary: 16 kept · 7 strengthened · 1 weakened · 4 changed figure · 389 new · 194 dropped

| # | Label | Score | Old | New | Match | Label right? | Note |
|---|---|---|---|---|---|---|---|
| 1 | kept | 0.104 | The Govt. of India has adopted "National Water Policy" in 1987 under the aegies of "National Water Resources Counsel" as accepted by the states and un | The first State Water Policy was adopted in 1987, followed by the State Water Policy, 1999. | wrong | - | national policy 1987 vs first State policy 1987: different policies |
| 2 | kept | 0.154 | - Use of remote sensing techniques in development and management. | The application of remote sensing and web-based techniques in the Flood Information and Management System (FMISC) are being carried out since 2017. | right | right |  |
| 3 | kept | 0.121 | Water is a prime natural resource, a basic human need and a precious asset. | Water, a scarce and unevenly distributed natural resource, essential to sustain life, livelihoods, food security, development, and the environment, is | right | right |  |
| 4 | kept | 0.153 | Provide a Management Information System (M.I.S.) for effective monitoring of policy implementation. | (v) Monitoring policy implementation by integrating indicator-based tracking and multi-stakeholder based consultative processes. | right | right |  |
| 5 | kept | 0.133 | In this context, transfer of water from surplus to scarcity areas should also be considered. | Inter-basin Transfers, keeping in view the environmental safeguards, to be considered from water surplus regions to water deficit regions for meeting  | right | right |  |
| 6 | kept | 0.152 | 18.1 There is an urgent need of paradigm shift in the emphasis in the management of water resources sector. | paradigm shift’ is needed in water resources management in a way that a River Basin is taken as the hydrological unit for the planning, development an | right | right |  |
| 7 | kept | 0.103 | 19.1 Private sector participation should be encouraged in the various aspects of planning, development and management of the water resources projects  | (iv) Encouraging private sector participation and Public Private Partnerships (PPPs). | right | right |  |
| 8 | kept | 0.103 | 19.1 Private sector participation should be encouraged in the various aspects of planning, development and management of the water resources projects  | (i) In order to expedite the development of water infrastructure and for alternate financing and improved services in the water sector, the participat | right | debatable | 'will be actively sought' is firmer; label computed on both new sentences together |
| 9 | kept | 0.125 | Private sector participation may help in introducing innovative ideas, generating financial resources and introducing corporate management in improvin | (iv) Encouraging private sector participation and Public Private Partnerships (PPPs). | right | right |  |
| 10 | strengthened | 0.109 | Promote equity and social justice among individuals and groups of users in water resource allocation and management. | (iii) The Principle of Equity, Social Justice and Good Governance through informed and collective decision making must be used for the allocation, pri | right | right |  |
| 11 | strengthened | 0.132 | 4.1 A river basin or a sub-basin in case of surface water along with the corresponding aquifer for ground water should be considered as a unit of deve | River Basin as the fundamental unit for water governance: Based on the principle of the unity of the hydrological cycle that treats surface and ground | right | right |  |
| 12 | kept | 0.114 | 11- Irrigation Potential likely to be created. | There is a wide gap between the irrigation potential created and utilized. | wrong | - | table fragment |
| 13 | changed figure | 0.129 | Thus there remains only about 22.2 BCM (18.0 m.a.f). | Only about 118.47 BCM is utilizable through the present strategies. | wrong | - | different quantities (remaining vs utilisable) |
| 14 | changed figure | 0.111 | 9.1 Total replenish able ground water resource of the state is 84 BCM (68.1 maf.) Out of which 72 BCM (58.4 maf.) is exploitable for (Data) irrigation | The total available water resources (surface and ground water) of Uttar Pradesh is estimated to be about 179 BCM (109.19 BCM surface water and 69.92 B | wrong | - | groundwater resource vs total water resources |
| 15 | changed figure | 0.221 | Out of the total replenishable resource, present total extraction is about 40.95 BCM (33.2 maf.) and the net exploitation is 27 BCM (21.9 maf.) which  | BCM while the total extraction is estimated to be about 53 BCM. | right | right | extraction 40.95 → 53 BCM |
| 16 | changed figure | 0.107 | Thus the ground water resource available for future exploitation is about 43.95 BCM (34.9 maf.). | The total available water resources (surface and ground water) of Uttar Pradesh is estimated to be about 179 BCM (109.19 BCM surface water and 69.92 B | wrong | - | different quantities |
| 17 | kept | 0.130 | Provide adequate water for drinking and domestic use. | (i) Drinking and Domestic Use: The State and local governments are committed to ensuring access to a minimum quantity of potable water for essential h | right | debatable | new says 'committed to ensuring'; no rule for 'committed' |
| 18 | kept | 0.103 | However, these priorities might be modified if necessary in particular region with reference to area specific considerations. | Keeping in view the distinct water availability scenario in different regions in the State, the concerned area or region-specific allocation prioritie | right | right |  |
| 19 | kept | 0.133 | The thermal power sector shall be required to meet the development cost and its maintenance along with the cost of water which shall be fixed from tim | Appropriate arrangements will made for the water needs of thermal power plants. | right | wrong | the duty to bear the cost of water is gone: should be weakened; rules cannot see it |
| 20 | strengthened | 0.175 | Provide water for industries including Agro industries. | (v) Industries, including agro industries: In view of the need for equitable socio-economic development, agro based industries will be allocated water | right | right |  |
| 21 | strengthened | 0.117 | - Agro- industries non agricultural industries | (v) Industries, including agro industries: In view of the need for equitable socio-economic development, agro based industries will be allocated water | right | right | priority-list fragment |
| 22 | strengthened | 0.112 | Modernisation and upgradation of these channels is also needed to cater for future requirements. | The assessment will inform the need for upgrading or planning new projects to cater to the future demand and supply. | wrong | - | channel upgrading vs project assessment |
| 23 | kept | 0.112 | To augment the ground water by artificial means surplus monsoon runoff between sub-basin within river systems should be transferred and stored in the  | The State government through the Uttar Pradesh State Ground Water Management and Regulatory Authority will also explore methods of artificial groundwa | right | debatable | should → explore is softer, named body added: rules net to kept |
| 24 | weakened | 0.119 | (b) Adoption of improved irrigation and agriculture practices using appropriate technology to ensure optimal use of water for agriculture production. | e) WUE in agriculture should be promoted through wider adoption of micro irrigation practices and technologies, including sprinklers and drip irrigati | right | wrong | 'to ensure' is a purpose clause, not a duty |
| 25 | kept | 0.122 | Demand side management and conservation through the spread of efficient irrigation technologies, such as piping drip and sprinkler irrigation is essen | (ii) Water saving technologies such as micro-irrigation (drip, sprinkler, sub-surface drip etc.) should be promoted actively to achieve reduction in a | right | right |  |
| 26 | kept | 0.114 | The planning of such a unit should take into account the present status of development and consider surface and under ground water as a unitary resour | The conjunctive use of surface water should be also be promoted. | right | right |  |
| 27 | kept | 0.103 | Conjunctive Use : Conjunctive management and ground water recharge should be central to ground water management. | The conjunctive use of surface water should be also be promoted. | right | right |  |
| 28 | strengthened | 0.118 | Promote research and training facilities in the water resource sector. l. | (vii) A “Ground Water Research and Training Institute" should be set up to promote research & best practice studies, and to train personnel of the gro | right | right |  |
| 29 | strengthened | 0.106 | 2.0 For effective and purposeful implementation of the State Water Policy, an adequate organisation is essential. | To ensure full-fledged, consistent and effective implementation of the State Water Policy, an implementation plan will be developed. | wrong | - | organisation vs implementation plan |

**Matches right: 22 of 29.** Labels on the right matches: 17 right, 3 debatable, 2 wrong.

## National Health Policy 2002 → 2017 (non-water): every matched pair

Summary: 10 kept · 4 strengthened · 2 weakened · 3 changed figure · 476 new · 425 dropped

| # | Label | Score | Old | New | Match | Label right? | Note |
|---|---|---|---|---|---|---|---|
| 1 | kept | 0.140 | Smallpox and Guinea Worm Disease have been eradicated from the country; Polio is on the verge of being eradicated; Leprosy, Kala Azar, and Filariasis  | Achieve and maintain elimination status of Leprosy by 2018, Kala-Azar by 2017 and Lymphatic Filariasis in endemic pockets by 2017. | right | debatable | targets with deadlines are firmer than an expectation; rules net to kept |
| 2 | kept | 0.154 | There has been a substantial drop in the Total Fertility Rate and Infant Mortality Rate. | Reduce infant mortality rate to 28 by 2019. | right | right | loose: status vs target, same indicator |
| 3 | changed figure | 0.153 | expenditure by Government as a % of GDP from the existing 0.9 % | Increase health expenditure by Government as a percentage of GDP from the existing 1.15% to 2.5 % by 2025. | right | right | baseline 0.9% → 1.15% of GDP |
| 4 | changed figure | 0.138 | to 7% of the budget 2010 | Increase State sector health spending to > 8% of their budget by 2020. c. | right | right | State health spending 7% → 8% of budget |
| 5 | changed figure | 0.130 | 4.15.1 This Policy envisages an increase in Government-funded health research to a level of 1 percent of the total health spending by 2005; and therea | Increase health expenditure by Government as a percentage of GDP from the existing 1.15% to 2.5 % by 2025. | wrong | - | research share of health spending vs government health spending % of GDP |
| 6 | strengthened | 0.105 | 2.23.1 It has been observed that a large number of training institutions have mushroomed, particularly in the private sector, for para medical personn | Training courses and curriculum for super specialty paramedical care (perfusionists, physiotherapists, occupational therapists, radiological technicia | wrong | - | mushrooming paramedical institutes vs new curricula |
| 7 | strengthened | 0.114 | Since the `public health’ discipline has an interface with many other developmental sectors, specialization in Public health may be encouraged not onl | Medical & health professionals would form a major part of this, but professionals coming in from diverse backgrounds such as sociology, economics, ant | right | right |  |
| 8 | strengthened | 0.109 | 4.10.1.2 The Policy lays emphasis on improving the skill -level of nurses, and on increasing the ratio of degree- holding nurses vis-à-vis diploma-hol | The policy recognises the need to improve regulation and quality management of nursing education. | right | right |  |
| 9 | kept | 0.104 | with income Mortality Expenditure Expenditure of <$1 day Rate/1000 to GDP on Health to Total Health | Catastrophic household health care expenditures defined as health expenditure exceeding 10% of its total monthly consumption expenditure or 40% of its | wrong | - | table header |
| 10 | kept | 0.112 | This is a prerequisite for cost-effective public health care. | The policy prerequisite is for an empowered public health cadre to address social determinants of health effectively, by enforcing regulatory provisio | wrong | - | fragment |
| 11 | strengthened | 0.112 | Since the physical features of urban settings are different from those in rural areas, the policy envisages the adoption of appropriate population nor | The policy recommends that health centres be established on geographical norms apart from population norms. | right | right |  |
| 12 | weakened | 0.169 | This policy will address itself to recommending arrangements which will eliminate the risks arising from inappropriate treatment. | The policy seeks to eliminate the risks of inappropriate treatment by maintaining adequate standards of diagnosis and treatment. | right | debatable | 'will address itself to recommending' → 'seeks to eliminate' |
| 13 | kept | 0.106 | 1.7 Another area of grave concern in the public health domain is the persistent incidence of macro and micro nutrient deficiencies, especially among w | Malnutrition, especially micronutrient deficiencies, restricts survival, growth and development of children. | right | right |  |
| 14 | kept | 0.116 | It is expected that this initiative will strengthen the | The focus will be to build upon the success of Mission Indradhanush and strengthen it. | wrong | - | PDF fragment |
| 15 | kept | 0.119 | The increase in life expectancy has increased the requirement for geriatric care. | The policy recognizes the growing need for palliative and rehabilitative care for all geriatric | right | right |  |
| 16 | kept | 0.111 | 2 The Policy also envisages the establishment of fullyequipped ‘hub-spoke’ trauma care networks in large urban agglomerations to reduce accident morta | The policy envisages creation of a unified emergency response system, linked to a dedicated universal access number, with network of emergency care th | right | right |  |
| 17 | kept | 0.189 | An adequately robust disaster management plan has to be in place to effectively cope with situations arising from natural and man-made calamities. | Better response to disasters, both natural and manmade, requires a dispersed and effective capacity for emergency management. | right | right |  |
| 18 | kept | 0.113 | Pharmaceutical drugs and other health services have always been available in the country at extremely inexpensive prices. | Prices and availability of drugs are regulated by the Department of Pharmaceuticals. | wrong | - | cheap drugs (status) vs price regulation |
| 19 | weakened | 0.120 | Domestic medical research would be focused on new therapeutic drugs and vaccines for tropical diseases, such as TB and Malaria, as also on the sub-typ | Drug research on critical diseases such as TB, HIV/AIDS, and Malaria may be incentivized, to address them on priority. | right | right | would → may |

**Matches right: 13 of 19.** Labels on the right matches: 11 right, 2 debatable, 0 wrong.

## UP 1999 → 2020: 15 random "truly dropped" items

| # | Old sentence | Possible match shown? | Truly dropped? | Note |
|---|---|---|---|---|
| 1 | 4.3 The priorities of development should also be aimed at reducing the existing regional imbalances. | no | right | no regional-imbalance statement in the 2020 text |
| 2 | 13.1 Presently the state has a thermal installed capacity of 11624 mw out which 5775 mw is in UPSEB and 5849 mw is in central sector. | no | right | thermal capacity figures not in 2020 text |
| 3 | 3- No of Schemes at the beginning of IX Plan 29 | no | right | table row |
| 4 | Treatment of industrial discharge and reuse of water shall be strictly enforced. | yes (0.098) | wrong | 2020: 'Industrial effluents should be treated for its maximum fit-for-purpose reuse' |
| 5 | 12.2 While planning water resources, due consideration to development of navigation, whenever feasible shall be given. | yes (0.057) | wrong | 2020 has '(vi) Navigation: ... water may be allocated for ensuring navigation' |
| 6 | The present consumptive requirement for cooling water in thermal stations is about 12.46 cumes (440 cusecs) i.e. about 0.37 BCM (0.3 maf.) though the total draft is much  | yes (0.060) | right | figure gone |
| 7 | The water resources development Plan shall have necessarily to be prepared collectively by all the concerned user department spelling out time schedule and financial fore | no | unclear | multi-departmental authority in 2020; counted wrong |
| 8 | Till now flood protection to about 1.54 million ha has been provided under the state plans. | no | right | figure gone |
| 9 | 8- Scheme identified but not started yet. | no | right | table row |
| 10 | The proposed development shall be on the multisectoral basis. | yes (0.053) | unclear | IWRM framing in 2020; counted wrong |
| 11 | 1.7 Adequate provision for ecological, navigational, recreational and other purposes has also to be made. | no | wrong | 2020 allocates for ecology, navigation, recreation |
| 12 | Viable projects, specially in scarce ground water areas, should be investigated and implemented to increase the surface water availability would also help in recharging t | no | right |  |
| 13 | However the progress in its implementation has not been satisfactory because of resource limitations. | no | right |  |
| 14 | Depending upon the specific situations, various combinations of private sector participation, in building, owning, operating, leasing and transferring of water resources  | yes (0.081) | wrong | 2020: PPP models 'will be actively sought' |
| 15 | 6- Minimum requirement of funds for IX Plan. | no | right | table row |

**Truly dropped: 9 of 15.**
Of the 6 not truly dropped, 4 show a possible match.

## NHP 2002 → 2017: 12 random "dropped" items

| # | Old sentence | Possible match shown? | Truly dropped? | Note |
|---|---|---|---|---|
| 1 | The Policy envisages that the funding for the urban primary health system will be jointly borne by the local self-government institutions and State and Central Government | no | right |  |
| 2 | The provisioning of higher public health investments will also be | yes (0.067) | wrong | 2017 raises public spending to 2.5% of GDP |
| 3 | Further, it has to be recognized that such health needs are also dynamic, as threats in the area of public health keep changing over time. | yes (0.083) | wrong | 2017: 'the health priorities are changing' |
| 4 | For the outdoor medical facilities in existence, funding is generally insufficient; the presence of medical and para-medical personnel is often much less than that requir | no | right |  |
| 5 | 2.28.1 Efforts made over the years for improving health standards have been partially neutralized by the rapid growth of the population. | no | right |  |
| 6 | Apart from the uneven geographical distribution of medical institutions, the quality of education is highly uneven and in several instances even substandard. | no | wrong | 2017: 'Regional disparities in distribution of these institutions must be addressed' |
| 7 | capacity of the public health administration at the State level to render effective service delivery. | yes (0.058) | wrong | fragment; unclear, counted wrong |
| 8 | 2.1.1 The public health investment in the country over the years has been comparatively low, and as a percentage of GDP has declined from 1.3 percent in 1990 to 0.9 perce | no | right | historical figure gone |
| 9 | Private entrepreneurship will be encouraged in the field of medical research for new molecules / vaccines, inter alia, through fiscal incentives. | no | right |  |
| 10 | 4.7.1 Minimal statutory norms for the deployment of doctors and nurses in medical institutions need to be introduced urgently under the provisions of the Indian Medical C | no | right |  |
| 11 | Taking into account the gap in health care facilities, it is planned, under the policy to increase health sector expenditure to 6 percent of GDP, with 2 percent of GDP be | yes (0.081) | wrong | target 2% of GDP by 2010 → 2.5% by 2025 is in 2017: a changed figure, not a drop |
| 12 | 4.16.3 This Policy recognizes the immense potential of information technology applications in the area of telemedicine in the tertiary health care sector. | yes (0.073) | wrong | 2017: National Digital Health Authority / telemedicine |

**Truly dropped: 6 of 12.**
Of the 6 not truly dropped, 5 show a possible match.

## 1999 → Feb 2020 draft: spot check

10 random matched pairs with match score under 0.25 (the less obvious ones; 32 sentences are near-copies anyway):
**9 of 10 right.** The wrong one paired a PDF fragment ("This organisation shall have to be") with a sentence on
restructuring departments.

## How the threshold and model were chosen (UP 1999 → 2020 FAOLEX only)

1. First try: multilingual model, plain cosine similarity, 0.70. A hand-check of 40 best matches, 8 in each band of
   similarity, gave precision rising only slowly with similarity (3/8, 2/8, 3/8, 6/8, 4/8 from 0.60 to above 0.80):
   broad sentences ("The specific objectives of the State Water Policy are to:") were everyone's best match.
2. On those 40 labelled pairs the multilingual model separated right from wrong worse (AUC 0.64) than
   all-MiniLM-L6-v2 (0.73) and bge-small-en-v1.5 (0.79). The sample was picked by the multilingual model, so this
   favours no model on purpose, but it is small. bge-small-en-v1.5 became the default; the multilingual model is kept
   as `--model multilingual`.
3. With bge-small, a second 40-pair sample (8 per band) gave 3/8, 1/8, 4/8, 5/8, 8/8 from 0.70 to above 0.83. Two
   changes helped on that sample: subtracting each sentence's usual similarity (mean of its 10 best; AUC 0.77 → 0.84)
   and adding a little for shared distinctive words (→ 0.86). Lead-ins ending in ":" were removed.
4. A third 40-pair sample on the final match score gave 2/8 (0.04–0.06), 3/8 (0.06–0.08), 4/8 (0.08–0.10), 7/8
   (0.10–0.12) and 8/8 (above 0.12). The threshold was set at 0.10. Pairs scoring 0.05–0.10 are shown on dropped
   items as a "possible match".
5. The precision figures above are on the final run. 15 of the 29 UP pairs were also in the tuning samples, so the UP
   figure is not independent; the National Health Policy pair was not used for tuning.

## Runtime (this sandbox: 2 CPU cores, Python 3.12, model already downloaded)

| Pair | Sentences (old / new) | Meaning step | Whole command (incl. PDF reading and wording compare) |
|---|---|---|---|
| UP 1999 → 2020 FAOLEX | 231 / 425 | 31 s | 39 s |
| UP 1999 → Feb 2020 draft | 231 / 252 | 22 s | 27 s |
| UP groundwater 2013 → 2020 FAOLEX | 253 / 425 | 33 s | 42 s |
| NHP 2002 → 2017 | 454 / 497 | 44 s | 58 s |

Almost all of the meaning step is computing the sentence embeddings on the CPU. First use also downloads the model
(67 MB; 3 s here).
