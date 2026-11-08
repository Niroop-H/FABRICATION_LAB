# Operator handbook — training-v1

This manual describes the simulator. It is not a real-fab SOP, equipment manual,
chemical handling instruction or emergency response authorization.

## Session and identity

Select the reference node and learning mode. Verify lot ID, wafer laser mark,
wafer diameter and carrier before processing. Each session contains one wafer.
A browser refresh resumes the current session using its access token. Export
reports before switching sessions; starting a new session does not delete the old
server record, but it replaces the browser's currently remembered token.

## Normal operation

Complete apparel, gloves and carrier checks. The route traveller releases one
operation at a time. Select the required machine, load the matching carrier,
review parameter names and units, select the recipe and check utility indicators.
Start processing. While running, the wafer cannot be unloaded. Finish run advances
simulated time by up to 3,600 seconds. Review the result and unload to release the
next step. A completed route is training evidence, not a fabricated qualified IC.

## Station modules

| Station | Learning goal | Model boundary / quality review |
| --- | --- | --- |
| Gowning | Entry checks before process operation | Procedural acknowledgement; apparel is not physically sensed |
| Stocker | Identity, diameter and carrier consistency | Single-wafer transport; no robotic trajectory or carrier slot arbitration |
| Wet preparation | Contamination and surface readiness | Particles reset by a teaching action; wet chemistry not modeled |
| Oxidation | Time and temperature affect film growth | Existing Deal–Grove calculation; no ultrathin correction or benchmark qualification |
| Deposition | Film material and target thickness | Target film added; no gas delivery/kinetic integration in this route |
| Lithography | Profile-specific scanner and overlay review | Offset checked against teaching tolerance; no optical resist simulation |
| Etch | Pattern transfer and rate/selectivity concepts | Existing plasma rate estimate and endpoint bookkeeping; not a timed 3D feature solver |
| Implant | Species, energy, projected range and straggle | Existing range table; no full electrical device calculation |
| Anneal | Recovery/activation step in the route | Procedure checkpoint; connected route applies no thermal diffusion model |
| CMP | Film removal and retained layer accounting | Thickness subtraction only; no dishing/erosion/slurry kinetics |
| Metrology | Inspect stack, particles and SOI dimensions | Model-derived values; not an independent measurement or SPC certification |
| Facilities | Detect, acknowledge and respond to utility loss | Representative interlocks; equipment-specific engineering review outstanding |

## Alarms and interrupted wafers

A simulated utility loss during a run inhibits modeled outputs and creates a
wafer hold. Restore the utility at Facilities. Open the affected tool's Alarms
tab and acknowledge the alarm, then reset. Reset restores the tool's control
state but does not release the wafer hold. Scrap the held wafer through
Disposition, retaining its record. Create a new lot to repeat the training.

The same hold discipline follows an out-of-window overlay result. Emergency stop
and abort actions also hold the wafer. There is no automatic resume or approved
rework path. The simulator does not claim that disabling all modeled outputs is
an equipment-specific industrial safe state (some tools require cooling/exhaust
or controlled ramp-down).

## Independent practice and assessment

Guided mode gives next-action prompts. Independent mode removes those prompts.
Assessment mode records the same state transitions for review and exposes
knowledge checks in the handbook. First answers are retained even if incorrect.
The report lists entry status, completed route steps, rejected actions, knowledge
results and whether a fault disposition was exercised. A fault not exercised is
reported as such rather than treated as passed.

An instructor should review the audit and model limitations. Actual facility
qualification requires approved SOPs, supervised practical assessment and expert
sign-off outside this software.
