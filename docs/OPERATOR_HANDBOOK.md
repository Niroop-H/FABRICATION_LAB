# Fabrication study manual

Revision SIM-SOP-02. Follow the guided route map: numbered stops show process order, completed stops have ticks, and YOU ARE HERE identifies the current operation. Use Locate on map to find that stop and Open current workstation to work there. Repeated visits to the same bench appear as separate stops. The connecting line represents process order, not physical distance. All equipment and support benches remain available below the map. There is no character or walking control. Opening a workstation does not transfer a wafer; use the permitted carrier-load operation. Each workstation separates its operation sheet, process science, recipe controls, alarms and history.

This is simulator instruction, not a qualified OEM procedure. Setpoints, model predictions and physical measurements are distinct. Input envelopes are not process acceptance specifications. Real process authorization requires equipment-specific procedures and validated recipes.

## Exact control instructions

### New lot

Select a technology and Guided mode, then Create lot & enter. The old record remains on the server; export it first because the browser resumes only the latest selected session.

### Go to required bench

Opens the entry station, loaded wafer bench, or next released operation. It does not move the wafer or bypass the traveller.

### Operation sheet / Process science

Read the numbered procedure first, then the physical basis, assumptions and acceptance guidance. Proceed to recipe and controls opens Operate.

### Confirm entry checks

In Operate at Gowning & entry, tick all three checks and confirm. Processing stays blocked until this is recorded.

### 1 · Load carrier

At the released bench, with the wafer at the stocker and tool IDLE, click Load carrier. The server verifies carrier compatibility. WAFER changes to Loaded.

### Recipe fields

Read the unit beside every field. Defaults are the reference recipe for a first exercise. Input ranges are teaching envelopes, not a promise of passing quality. Editing a field alone does not select the new recipe.

### 2 · Select recipe

After loading, review values and click Select recipe. The server validates and stores them. If you edit values again, select the recipe again before starting.

### 3 · Start process

Requires a selected recipe, correct route, no wafer hold and available exhaust, cooling and vacuum. State changes to RUNNING. Wafer transfer stays locked.

### 4 · Advance time

Enter an interval from 1 to 3600 seconds, then click Advance time. Each click adds at most the remaining process duration. Repeat until COMPLETE or FAULT. LPCVD partial thickness updates; other process results appear at completion.

### Inspect results

Read Current operation result, units, provenance and acceptance limits before unloading. PASS may describe procedural completion only; consult the operation sheet to see which quantities are actually modeled.

### 5 · Unload wafer

Enabled only after completion without a hold. Returns the wafer to the stocker and releases the next route operation. Return to bench directory and open the required bench.

### Abort process / EMERGENCY STOP

Abort is exposed during a run. Emergency stop is available for a loaded, running or completed operation. Both inhibit modeled outputs and hold the wafer; neither is a pause/resume control.

### Facilities console

Open Operate to simulate loss or restoration of exhaust, cooling or vacuum. A loss during processing faults the active tool and holds the wafer. Restore unavailable utilities before reset.

### Acknowledge / Reset tool

In the affected bench Alarms tab, acknowledge awareness, restore utilities if needed, then reset. Reset clears the tool fault but does not release a held wafer.

### Scrap held wafer

After utilities are restored and the loaded tool is reset, use Alarms → Scrap held wafer. No rework release exists in this version. Export the record and create a new lot.

### History / Export report

History shows the latest 50 recorded commands. Export report saves the server session and assessment as JSON, including its retained audit and model limitations.

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

## Route steps: simulation and real fabrication

Real workflows vary by equipment and approved process integration. These comparisons explain roles and physical intent; they are not machine-specific operating recipes.

### Representative gate dielectric growth

**Purpose:** Form an insulating oxide and study how process conditions affect its modeled thickness.

**In the simulator:** Set temperature and duration, then run the oxidation step. The Deal–Grove model computes oxide thickness and adds it to the wafer stack; thin-oxide corrections are disabled.

**In a real fab:** A qualified thermal oxidation sequence controls the wafer temperature, oxidizing ambient and time to grow silicon dioxide by consuming silicon at the interface. Operators verify the released recipe and equipment readiness; inspection evaluates the resulting film. Actual gate-dielectric integration may use different materials or methods, and the app model is not sufficient to qualify ultrathin gate oxides.

### Incoming inspection & surface clean

**Purpose:** Prepare the starting surface for subsequent interfaces and films.

**In the simulator:** Run the clean checkpoint; the simulator sets its particle count to zero.

**In a real fab:** An operator verifies lot identity and incoming condition, then runs an approved surface preparation sequence using compatible equipment. Inspection determines whether contamination requirements are met; running a clean does not prove a particle-free wafer.

### Verify SOI body and buried oxide

**Purpose:** Confirm the starting substrate matches the intended device architecture.

**In the simulator:** Read the body and buried-oxide dimensions stored in the reference SOI wafer.

**In a real fab:** The facility checks supplied SOI material against its specifications using appropriate metrology and supplier records. Body thickness and buried oxide are separate quantities.

### Representative high-k gate dielectric

**Purpose:** Introduce the insulating layer associated with gate control.

**In the simulator:** Enter a target thickness; the model adds an HfO2 layer directly to the stack.

**In a real fab:** A qualified process forms the gate dielectric, often using atomic layer deposition for suitable high-k films. Engineers evaluate thickness, interfaces, composition and electrical behavior. This app does not perform ALD cycle chemistry.

### Gate electrode deposition

**Purpose:** Provide material that will subsequently be patterned into a gate electrode.

**In the simulator:** For new bulk-planar routes, temperature, pressure, flow and elapsed time determine modeled LPCVD thickness. The FD-SOI and legacy routes use target thickness bookkeeping.

**In a real fab:** An operator loads the released lot and runs the approved gate-stack recipe. The actual material and deposition method depend on process integration. Film thickness, uniformity and material properties are checked; a generic silicon layer does not reproduce a modern qualified gate stack.

### Coat, align, expose & develop

**Purpose:** Define where the next pattern-transfer process acts.

**In the simulator:** Set an overlay offset and run the alignment check. The app records nominal feature size and alignment; it does not form a physical resist image.

**In a real fab:** A lithography sequence coats photoresist, performs the prescribed bake steps, aligns the wafer and pattern, exposes the resist, and develops it. Inspection checks pattern quality before transfer.

### Second pattern alignment demonstration

**Purpose:** Study why registration between patterning steps matters.

**In the simulator:** Run a second alignment check within the reference overlay window.

**In a real fab:** A multi-patterning scheme needs a defined sequence of masks and intermediate processing. Operators align each relevant level and inspect registration. This additional app step illustrates alignment only, not a complete multi-patterning flow.

### Pattern transfer into gate electrode

**Purpose:** Transfer the defined pattern into the electrode film.

**In the simulator:** Set source and bias RF powers. The plasma model estimates etch rate and anisotropy; the stack marks the gate film as patterned.

**In a real fab:** A qualified etch process removes exposed gate material while the mask protects intended features. Engineers check endpoint, selectivity and resulting dimensions/profile. The app does not calculate full evolving feature geometry.

### Resist strip & post-etch clean

**Purpose:** Remove temporary mask material and residues before later processing.

**In the simulator:** Run a second clean checkpoint after pattern transfer; the simulated contamination count is reset.

**In a real fab:** After the mask has served its purpose, an approved strip and residue-clean sequence removes resist and etch by-products while protecting the remaining materials. Compatibility and inspection determine acceptability.

### Representative source/drain implant

**Purpose:** Introduce dopant into selected regions before activation processing.

**In the simulator:** Choose ion energy; the existing arsenic range model reports projected range and straggle.

**In a real fab:** The released implant recipe specifies species, dose, energy and other tool settings. The operator verifies the recipe and lot, while equipment delivers the ion beam under controlled conditions. Range alone does not establish dose, activated concentration or junction performance.

### Raised source/drain concept demonstration

**Purpose:** Illustrate adding material locally in source/drain regions.

**In the simulator:** Enter the requested regional height; the app records it as a concept result without simulating epitaxial growth.

**In a real fab:** A suitable process integration may use selective epitaxial growth to form raised regions. Material, doping, selectivity and geometry are process-specific and require inspection.

### Thermal activation / recovery checkpoint

**Purpose:** Connect implantation or other prior processing with its required thermal treatment.

**In the simulator:** Complete an anneal checkpoint. No dopant activation or diffusion is calculated.

**In a real fab:** The approved thermal cycle controls temperature history and ambient for the intended material changes, such as implant damage recovery and dopant activation. Engineers evaluate activation and unwanted redistribution.

### Interlayer dielectric deposition

**Purpose:** Provide insulation associated with subsequent wiring levels.

**In the simulator:** Enter a thickness target; the app adds a SiO2 layer to the stack.

**In a real fab:** An approved dielectric process deposits an insulating film. Coverage, thickness, defects and integration with later contacts/interconnects are evaluated.

### Dielectric planarization

**Purpose:** Prepare a more suitable surface for later lithography and interconnect processing.

**In the simulator:** Enter removal thickness; the app subtracts material from the top film.

**In a real fab:** CMP equipment uses a qualified pad/slurry and controlled mechanics to reduce topography. Inspection assesses remaining film, uniformity, defects and local effects. A thickness subtraction alone does not establish planarity.

### Damascene interconnect pattern

**Purpose:** Define the intended interconnect openings.

**In the simulator:** Run another overlay check for the wiring-pattern step.

**In a real fab:** Lithography defines the intended openings in the dielectric using the released mask and resist process. Operators inspect alignment and pattern quality before dielectric etching.

### Dielectric trench pattern transfer

**Purpose:** Create the openings that will subsequently receive conductor material.

**In the simulator:** Run the plasma model with dielectric chemistry assumptions; mark the dielectric as patterned.

**In a real fab:** A dielectric etch transfers the mask openings into the insulating material. Depth, profile, selectivity and residue control affect later metal filling.

### Al interconnect deposition

**Purpose:** Introduce the conductor used by this reference interconnect concept.

**In the simulator:** Add the requested aluminum thickness to the stack.

**In a real fab:** An aluminum wiring process deposits and patterns conductor using its qualified integration sequence. This condensed app route omits important operations; adding an Al film does not create a complete connected wiring network.

### Cu interconnect deposition

**Purpose:** Introduce conductor into the interconnect concept before overburden removal.

**In the simulator:** Add the requested copper thickness to the stack.

**In a real fab:** A copper damascene integration generally includes barrier/liner and seed preparation, metal fill and subsequent planarization. The operator follows the released sequence and checks fill quality. These intermediate layers and fill mechanics are omitted here.

### Cu overburden polish

**Purpose:** Illustrate removing excess conductor after a fill operation.

**In the simulator:** Subtract the requested amount from the top copper film.

**In a real fab:** A qualified copper CMP sequence removes overburden while controlling remaining structures, dishing, erosion and defects. Endpoint and post-process inspection matter; uniform subtraction cannot reproduce them.

### Final thickness, CD & defect inspection

**Purpose:** Review process evidence and decide whether further assessment is needed.

**In the simulator:** Read total film thickness and particle count from simulator state, plus SOI dimensions where applicable. This step does not independently measure CD despite its route title.

**In a real fab:** Real inspection uses an appropriate measurement plan and calibrated methods for specified dimensions, thicknesses and defects. Engineers compare results with release criteria and review deviations. Final device qualification requires additional electrical and reliability evidence.

### Entry and carrier verification

**Purpose:** Establish contamination-control and identity discipline before processing.

**In the simulator:** Confirm the apparel, glove/footwear and carrier checkboxes to enable the route.

**In a real fab:** Personnel follow the facility gowning and handling procedure, verify authorization and material identity, and use compatible carriers. Checking boxes is not physical verification.
