# Fabrication study manual

Revision SIM-SOP-02. Walkable navigation leads to equipment workstations. Each workstation separates its operation sheet, process science, recipe controls, alarms and history.

This is simulator instruction, not a qualified OEM procedure. Setpoints, model predictions and physical measurements are distinct. Input envelopes are not process acceptance specifications. Real process authorization requires equipment-specific procedures and validated recipes.

## Contamination control

Particles and molecular contamination can alter interfaces, pattern transfer and device yield. Entry discipline is part of process control, not an introductory game objective.

### Scientific basis

A cleanroom classification alone does not establish wafer cleanliness. Apparel condition, handling and local procedures also matter.

### Procedure

1. Identify the selected wafer diameter and compatible carrier.
2. Inspect the simulated apparel, glove and footwear checks.
3. Confirm all entry checks before attempting any tool load.

### Acceptance and interpretation

Entry checks must be recorded. This simulator does not measure particles on personnel.

Study question: Explain why a clean-looking surface is not proof of semiconductor cleanliness.

## Wafer identity and genealogy

A traveller connects wafer identity, material history, recipe revision and inspection results. A process result is not interpretable without knowing which wafer and layer it describes.

### Scientific basis

Thickness values belong to individual layers. Adding film thicknesses does not reconstruct three-dimensional topography.

### Procedure

1. Read the laser mark, lot identifier, substrate and carrier.
2. Compare the released route operation with the intended tool.
3. Inspect the current layer stack and any hold before transfer.

### Acceptance and interpretation

A held wafer is not released by moving it or resetting a tool. Only the supported disposition resolves its route status.

Study question: Explain the difference between tool availability and wafer release.

## Surface preparation

Cleaning prepares the surface for the next process by controlling contamination and residues. Surface condition can affect adhesion, nucleation and subsequent interface quality.

### Scientific basis

This module records a procedural checkpoint; it does not compute chemical reaction rates, residue removal or surface termination.

### Procedure

1. Read the incoming wafer history and the purpose of this clean step.
2. Verify that the clean station is the released operation and load the compatible carrier.
3. Select the procedural recipe, verify simulated utility status and run the checkpoint.
4. Review the recorded result before unloading.

### Acceptance and interpretation

Completion establishes only that the simulated procedure ran. No chemical cleanliness measurement is generated.

Study question: Why can a completed clean cycle still require independent surface verification?

## Thermal oxide growth

Thermal oxidation converts silicon at the interface into silicon dioxide. It is different from depositing an oxide film onto a surface.

### Scientific basis

Deal–Grove relation: x² + A·x = B·(t + τ). x is oxide thickness; A has units of length, B length²/time, and τ accounts for an initial oxide. Use consistent units. Coefficients depend on the modeled conditions.

### Procedure

1. Identify the substrate and existing film stack.
2. Review temperature and duration with units, then select the recipe.
3. Verify utility interlocks before starting the modeled cycle.
4. Advance simulated time and inspect the oxide result and model provenance.
5. Record the result before releasing the wafer.

### Acceptance and interpretation

Thin-oxide corrections are disabled in this route. A computed gate oxide thickness is not proof of a qualified gate dielectric.

Study question: How do the linear and parabolic terms change the relationship between thickness and time?

## Film growth and thickness control

Deposition adds material to the wafer. Film performance also depends on composition, uniformity, stress, adhesion and interfaces; thickness alone is insufficient.

### Scientific basis

For the integrated LPCVD gate step, Δh = R(T, p, F)·Δt/60, with h in nm, rate R in nm/min and elapsed time in seconds. The rate is evaluated from the existing model using recipe temperature, pressure and flow. Other deposition steps use target bookkeeping.

### Procedure

1. Identify whether this route step is integrated LPCVD or target-controlled bookkeeping.
2. Review all setpoints and units. A valid input range is not an acceptance specification.
3. For integrated LPCVD, compare duration with the target thickness and stated tolerance.
4. Load, select the recipe, check permissives and start.
5. Advance time in increments; inspect partial thickness and the growth trace.
6. At completion compare actual modeled thickness with the acceptance window. Resolve a hold before any release.

### Acceptance and interpretation

Integrated gate deposition uses its route target and ±10% teaching tolerance. An interrupted run retains partial film. Other films do not have an independent physical growth calculation.

Study question: Why does doubling duration approximately double thickness in this constant-setpoint model, and why might real equipment deviate?

## Pattern definition and overlay

Lithography defines a resist pattern used by a later transfer process. Critical dimension describes feature size; overlay describes relative alignment between patterned levels.

### Scientific basis

Overlay and critical dimension are different quantities. The connected module checks the entered overlay offset against the profile window; it does not simulate optical imaging, focus, exposure dose or resist development.

### Procedure

1. Identify the intended pattern level from the traveller.
2. Review the reference scanner description for the selected technology.
3. Compare the requested overlay with the permitted profile window.
4. Run the step and inspect the alignment decision before release.

### Acceptance and interpretation

An overlay excursion places the wafer on hold. A passed overlay check does not verify resist profile or printed critical dimension.

Study question: Can correct overlay establish that a feature has the correct width? Explain.

## Pattern transfer and selectivity

Etching removes material to transfer a mask pattern into a film. Rate, directionality and selectivity influence the resulting structure.

### Scientific basis

Selectivity is the ratio of etch rates for two materials under the same conditions. The connected plasma model estimates rate and anisotropy; this route marks a film patterned without evolving a three-dimensional profile.

### Procedure

1. Check which previously patterned layer is being transferred.
2. Review source and bias power separately; both are in watts but represent different controls.
3. Confirm simulated utility permissives and start.
4. Inspect modeled rate, provenance and the recorded pattern-transfer result before unloading.

### Acceptance and interpretation

No measured endpoint signal or full feature profile is generated. A pattern flag must not be interpreted as a verified sidewall or remaining-film measurement.

Study question: Why is a high etch rate insufficient to establish a successful pattern transfer?

## Ion implantation

Implantation introduces dopant ions into a substrate. Ion species, energy and dose serve different roles; later thermal processing changes the resulting material state.

### Scientific basis

Projected range estimates a characteristic penetration depth; straggle describes the spread. The current route exposes energy and uses an existing range model. It does not solve a complete activated dopant profile.

### Procedure

1. Confirm that the current route calls for implantation rather than the FD-SOI concept step.
2. Review ion energy in keV and the recorded model assumptions.
3. Run the step, then inspect projected range and straggle.
4. Keep the subsequent anneal checkpoint distinct from implantation completion.

### Acceptance and interpretation

A range estimate is not an electrical junction qualification. Dose, channeling, damage and activation are not fully represented in this connected route.

Study question: Why is projected range different from an electrically active junction depth?

## Thermal processing and activation

Annealing changes material state through temperature-dependent mechanisms. In implanted material, activation and damage recovery must be distinguished from simply completing a heating cycle.

### Scientific basis

Thermal budget depends on the temperature history and the mechanism of interest. This connected step is a procedural checkpoint, not a diffusion or activation calculation.

### Procedure

1. Review the prior process and why an anneal follows it.
2. Select the checkpoint recipe and verify simulated utilities.
3. Run and inspect the history entry.
4. Do not infer activated concentration or electrical performance from this completion flag.

### Acceptance and interpretation

The route does not generate activation fraction, diffusion length or a measured temperature trace.

Study question: Why cannot two thermal cycles be compared by duration alone?

## Planarization and material removal

Chemical mechanical planarization reduces surface topography through combined chemical and mechanical action. Removal uniformity and material selectivity matter alongside average removal.

### Scientific basis

The connected bookkeeping calculation subtracts the requested removal from the film stack. It does not solve pressure distribution, slurry behavior, dishing or erosion.

### Procedure

1. Identify the film intended for planarization.
2. Review requested removal in nm against the incoming stack.
3. Run the simulated step and compare incoming and outgoing thickness.
4. Inspect the result before release; do not treat a thickness decrement as a topography map.

### Acceptance and interpretation

No independent uniformity or surface-planarity measurement is available in this model.

Study question: Can identical average removal produce different local topography? Explain.

## Measurement and process evidence

Metrology supports decisions by relating an observation to a defined measurand, method and uncertainty. A displayed number without those attributes is incomplete evidence.

### Scientific basis

A model prediction is not an independent measurement. Repeatable deterministic output does not establish accuracy or measurement uncertainty.

### Procedure

1. Identify the measurand, layer and units.
2. Read the reported model and provenance.
3. Compare only against a stated applicable limit; otherwise record the value without inventing a pass criterion.
4. Export the report with process history and unresolved limitations.

### Acceptance and interpretation

Current inspection reads deterministic simulator state. It does not include instrument calibration, sampling plans or measurement noise.

Study question: What additional evidence would be needed to turn a model prediction into a defensible wafer acceptance decision?

## Permissives, alarms and recovery

Equipment permissives prevent a process from starting or continuing when required conditions are absent. Tool recovery and wafer quality disposition are separate decisions.

### Scientific basis

The simulator uses Boolean exhaust, cooling and vacuum availability. These are logical permissives, not measured pressure, flow or temperature channels.

### Procedure

1. Read the selected utility and current availability.
2. Use simulated utility loss to study the response of a running process.
3. Inspect inhibited outputs, the active alarm and wafer hold.
4. Restore the utility, acknowledge the alarm and request a permitted reset.
5. Review the held wafer separately. The current teaching route supports scrap disposition rather than automatic rework.

### Acceptance and interpretation

Acknowledgement does not fix the cause. Reset does not establish wafer quality. Real equipment recovery must follow its approved procedure.

Study question: Why must a wafer remain held even after the utility and equipment state recover?

## Further reading

- [TU Wien — Deal–Grove oxidation model](https://www.iue.tuwien.ac.at/phd/filipovic/node31.html) — Oxidation theory; not qualification of simulator coefficients.
- [BYU Integrated Microfabrication Lab — process reference](https://www.cleanroom.byu.edu/processes) — Further study across fabrication processes; not a recipe release for this simulator.
- [IIT Bombay Nanofabrication Facility — dry etch tools](https://www.iitbnf.iitb.ac.in/iitbnf/infrastructure/dry_etch_tools.php) — Pattern-transfer context and equipment families.
