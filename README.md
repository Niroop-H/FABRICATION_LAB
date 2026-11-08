# Silicon Fabrication Lab

A browser-based semiconductor **training simulator under development**. This is
not a production-connected digital twin or a qualified manufacturing system.

## What works

- A procedural Three.js cleanroom with a movable operator, collision boundaries,
  first/third-person cameras and machine terminals. If WebGL is unavailable, a
  floor-plan interface provides the same operational controls.
- Distinct, versioned **condensed teaching routes** for 180 nm, 130 nm, 65 nm and
  22 nm FD-SOI. Diameter, SMIF/FOUP carrier, scanner reference, overlay envelope,
  gate film target, interconnect material and route operations differ.
- Entry checks; load, recipe selection, start, simulated-time advancement and
  unload; route-order and carrier enforcement; wafer identity and layer tracking.
- Utility-loss injection, inhibited outputs, alarm acknowledgement, reset, wafer
  holds and scrap disposition. These are representative state transitions, not
  validated equipment-specific emergency sequences.
- Durable sessions with capability-token access and optimistic concurrency.
- Guided prompts, independent operation, recorded assessment mode, first-attempt
  knowledge checks, station handbook and server-generated JSON reports.
- Separate oxidation calculator at `/calculator` using the existing process model.

## Start locally

Python 3.12 is the deployment reference (project modules require 3.11+).

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m flask --app app run
```

Open http://127.0.0.1:5000. Local sessions are saved to the ignored
`.local-data/fab.sqlite3` file. `FAB_DB_PATH` can select another SQLite path.
The browser stores a random session access token so a reload can resume the lot.
Clearing browser storage loses that browser's access token; reports do not contain it.

Optional analysis dependencies: `python -m pip install '.[full]'`.

## Deploy to Vercel

1. Import this GitHub repository into Vercel.
2. Select **Flask**, Root Directory **`./`**, with default install/build/output settings.
3. Provision a PostgreSQL database and set **`DATABASE_URL`** in the Vercel
   project's environment variables. Use the provider's connection string with
   TLS enabled. Set it for each deployment environment that needs saved lots.
4. Redeploy. The application creates the `fab_sessions` table on first use.
   The database role must be allowed to create/use this table.
5. Open `/`, create a lot, complete entry checks and process the first step.
   Reload and verify that the lot resumes. `/api/health` checks the web process;
   successful lot creation/resume checks persistence.

**The connected fab requires `DATABASE_URL` on Vercel.** It deliberately refuses
an ephemeral local-file fallback. `/calculator` and the static interface can load
without it, but creating or resuming a training lot cannot.

The app has no real-world machine connections. For a public deployment, configure
appropriate hosting access controls and request limits; session creation is
currently anonymous. Session tokens are bearer capabilities, not user accounts.

References: [Vercel Flask deployment](https://vercel.com/docs/frameworks/backend/flask),
[psycopg installation](https://www.psycopg.org/psycopg3/docs/basic/install.html).

## Using the fab

1. Create a lot and choose a technology and mode.
2. At Gowning & Entry, confirm the three checks.
3. Walk with WASD/arrows, drag to look, press E near a terminal, or select a route
   step/floor-plan station. V or the camera button switches first/third person.
4. At the current route tool: **Load → Select recipe → Start → Finish run → Unload**.
   Finish run advances simulation time; it is not real-time processing.
5. Inspect layer genealogy and model outputs. Export the report for instructor review.
6. Use the handbook for station principles and knowledge checks.

To practice a fault, start a run, use Facilities Console to simulate utility loss,
restore the utility, select the affected tool's Alarms tab, acknowledge and reset.
The interrupted wafer remains held. This release permits scrap disposition only;
rework requires a new lot. Failed overlay checks follow the same hold discipline.

All modes retain audit evidence. Guided mode additionally shows operation prompts.
Assessment reports describe demonstrated/pending criteria and first submissions;
they are **not certifications** or validated competency scores.

## Architecture and verification

`src/fab/catalog.py` owns training profiles and routes. `engine.py` applies
commands deterministically and integrates the canonical wafer model with selected
process calculations. `store.py` persists server-authoritative state. `api.py`
authenticates and version-checks operations. The frontend is a presentation client.

```bash
python -m unittest discover -s tests/unit -v
npm run check
```

Tests cover all four complete routes, carrier/order rejection, utility trips,
wafer holds, alarm reset, quality excursions, persistence, bearer authentication,
concurrent revision rejection, HTTP validation and assessment evidence.

The 3D renderer imports pinned Three.js 0.170.0 from jsDelivr. Internet access to
that CDN and WebGL are needed for 3D; machine operation remains available via the
floor-plan fallback. Browser QA in the development environment verified lot
creation, entry, a complete machine cycle and refresh/resume through that fallback;
WebGL was disabled in that environment, so the 3D geometry/camera view still needs
visual acceptance on a WebGL-capable browser. PostgreSQL deployment has not been
validated against a live provisioned database in this workspace.

See [operator handbook](docs/OPERATOR_HANDBOOK.md),
[model traceability](docs/MODEL_TRACEABILITY.md), and
[remaining engineering work](docs/ENGINEERING_STATUS.md).

MIT licensed. Representative geometry and controls are not OEM reproductions.
