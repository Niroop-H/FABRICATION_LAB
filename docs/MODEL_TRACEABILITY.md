# Model traceability — training-v1

All connected routes are educational approximations. Existing repository modules
contain literature attributions; those attributions do not establish calibration
or independent validation. Numeric envelopes in the training catalog are teaching
choices, not verified OEM limits. No standards compliance is claimed.

| Connected function | Source / implementation | Units | Validation status |
| --- | --- | --- | --- |
| Wafer identity and films | `src/simulation/core/wafer.py` | mm, nm, count | Software round-trip and route tests |
| Oxide growth | `thermal_oxidation.py`, Deal–Grove implementation | °C, s, nm | Existing numerical model; no external benchmark in this release |
| Plasma rate/profile estimate | `etch_models.py`, plasma state and profile functions | W, mTorr, nm/min | Integration exercised; industrial accuracy unverified |
| Implant projected range | `implant_models.py`, range lookup | keV, nm | Integration exercised; source tables not independently audited |
| Film deposition | `src/fab/engine.py`, target-controlled film addition | nm | Bookkeeping only; no deposition kinetics |
| Lithography | catalog-specific overlay limit comparison | nm | Teaching envelope only; no resist/optical physics |
| CMP | canonical layer removal | nm | Material-thickness bookkeeping only |
| Anneal | procedure checkpoint | s | No physical model in connected route |
| Metrology | deterministic state inspection | nm, count | No independent sensor, calibration or uncertainty model |
| Interlocks | command reducer and state guards | boolean state | Fault/hold/reset regression tests; no OEM validation |
| Assessment | audit-derived criteria and first answers | counts, status | Software evidence only; no certification |

## Standards review queue

| Reference | Intended review area | Current state |
| --- | --- | --- |
| SEMI S2 / S8 / S10 | Safety, ergonomics, risk | Qualified reviewer and licensed text required |
| SEMI E30 / E37 | Equipment communication | No production SECS/GEM or HSMS integration |
| SEMI E40 / E87 / E90 / E94 | Jobs, carriers, tracking | Representative state tracking; conformance not assessed |
| SEMI E95 | HMI design | Representative interface; revision/conformance review pending |
| SEMI E187 | Equipment cybersecurity | No industrial equipment integration |
| ISO 14644-1 | Cleanroom classification | No classified facility or particle simulation |

Before an industrial release, every limit/model needs a source revision,
applicability envelope, independent benchmark dataset, error tolerance and
reviewer approval. The current software tests establish state consistency, not
physical fidelity.
