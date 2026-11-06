# Silicon Fabrication Lab Digital Twin

## Virtual Semiconductor Fabrication Training and Operations Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

> **Web preview:** Vercel-ready Flask dashboard with a stateless thermal oxidation calculator. The full 3D facility described below remains a development target.

> **Project Status**: Active Development — Stage 2 (Operational 180nm Reference Fab)

A high-fidelity, walkable semiconductor fabrication facility simulator designed for industrial training. Trainees operate as fabrication technicians inside a physically accurate virtual cleanroom, learning correct industrial procedures, equipment behavior, safety practices, and manufacturing principles.

---

## 🏭 What This Is

This platform is a **Virtual Semiconductor Fabrication Training and Operations System** — not a game, not a toy simulator. An experienced semiconductor fabrication engineer should be able to examine any machine, its interface, its operating sequence, its process outputs and its safety behavior — and recognize a technically faithful representation, with any approximations clearly documented.

### Key Distinction

> Until the platform receives and reconciles trusted real-equipment data, it is a **high-fidelity operational virtual fab simulator**. Once it has validated synchronization with actual industrial equipment and processes, it can function as a **production-connected digital twin**. The latter requires a secure, isolated, and explicitly authorized integration architecture.

---

## 🔬 Four Process Technology Nodes

| Node | Wafer Size | Architecture | Lithography | Key Features |
|------|-----------|-------------|-------------|--------------|
| **180 nm** | 200 mm | Planar CMOS | KrF (248nm) | Mature process, Al interconnects, LOCOS/STI isolation |
| **130 nm** | 200 mm | Planar CMOS | KrF (248nm) | Cu interconnects, low-k ILD, tighter overlay |
| **65 nm** | 300 mm | Planar CMOS | ArF dry (193nm) | Strain engineering, advanced DUV, complex interconnects |
| **22 nm FD-SOI** | 300 mm | Fully Depleted SOI | ArF immersion (193nm) | Ultra-thin body, back-gate biasing, no channel doping |

Each node has its own validated process library with qualified equipment configurations, materials, process routes, design rules, and simulation parameters. The 22nm reference is based on GlobalFoundries 22FDX technology (FD-SOI), with FinFET as a separately defined option.

---

## 🏗️ Facility Areas

The walkable 3D facility includes functionally accurate areas:

| Area | Function | Key Equipment |
|------|----------|---------------|
| **Gowning & Entry** | Cleanroom apparel, entry protocol, air shower | PPE stations, access control |
| **Lithography Bay** | Patterning under yellow light | Coat/develop tracks, steppers/scanners |
| **Deposition & Etch** | Thin film deposition and pattern transfer | CVD, PVD, RIE, ICP etchers |
| **Thermal & Implant** | Oxidation, diffusion, ion implantation | Furnaces, RTP, implanters |
| **Wet Processing & CMP** | Chemical cleaning and planarization | Wet benches, CMP tools |
| **Metrology & Inspection** | Measurement and quality control | Ellipsometry, CD-SEM, overlay |
| **Subfab & Facilities** | Utilities and support systems | Pumps, abatement, gas delivery |
| **Material Transport** | Wafer carrier handling | SMIF/FOUP, stockers, AMHS |

---

## ⚙️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│           DETERMINISTIC SIMULATION BACKEND              │
│                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Equipment   │  │   Process    │  │   Facility   │  │
│  │  & Safety    │  │   Engine     │  │   Engine     │  │
│  │  Engine      │  │              │  │              │  │
│  └─────────────┘  └──────────────┘  └──────────────┘  │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │     MES      │  │  Metrology   │  │  Training    │  │
│  │  & Dispatch  │  │  & SPC       │  │  Engine      │  │
│  └─────────────┘  └──────────────┘  └──────────────┘  │
└───────────────────────┬─────────────────────────────────┘
                        │ gRPC / WebSocket
                        │ State Sync @ 10-20 Hz
┌───────────────────────┴─────────────────────────────────┐
│              3D VISUALIZATION CLIENT                     │
│  (Unity/Unreal — presentation only, not authoritative)  │
│                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  3D Fab      │  │  Character   │  │  Equipment   │  │
│  │  Environment │  │  Controller  │  │  HMI Panels  │  │
│  └─────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

The 3D engine is strictly a presentation and interaction client. All process physics, equipment state machines, wafer tracking, and safety logic run in the deterministic backend.

---

## 📋 Standards Traceability

| Standard | Application |
|----------|-------------|
| SEMI S2 | Equipment environmental, health and safety |
| SEMI S8 / S10 | Ergonomics and risk assessment |
| SEMI E10 | Equipment reliability, availability, maintainability |
| SEMI E30 / E37 | GEM equipment communication and HSMS |
| SEMI E40 / E87 / E90 / E94 | Jobs, carrier management, wafer tracking |
| SEMI E95 | Semiconductor machine HMI design reference |
| SEMI E187 | Fab equipment cybersecurity |
| ISO 14644-1 | Cleanroom particle cleanliness classification |

---

## 🎓 Training Modes

| Mode | Description |
|------|-------------|
| **Guided Training** | Step-by-step instruction with highlighted controls and explanations |
| **Independent Operation** | Complete tasks without prompts; errors cause realistic consequences |
| **Competency Assessment** | Evaluated procedure compliance, safety, and decision-making |

> A high simulator score demonstrates virtual competency, not real-world certification. Actual authorization requires facility-specific training, practical assessment, and EHS requirements.

---

## 🚀 Development Stages

| Stage | Deliverable | Status |
|-------|-------------|--------|
| 1. Reference Engineering | Validated specs for all nodes | ✅ In Progress |
| 2. Operational 180nm Fab | Walkable facility, core tools, connected workflows | 🔄 Active |
| 3. Expand to 130nm | Technology-specific recipes and configurations | ⏳ Planned |
| 4. Expand to 65nm | Advanced processing and automation | ⏳ Planned |
| 5. Implement 22nm FD-SOI | FD-SOI architecture, advanced patterning | ⏳ Planned |
| 6. Industrial Verification | Expert review, benchmarking, SOP traceability | ⏳ Planned |

---

## 📁 Project Structure

```
FABRICATION_LAB/
├── docs/                           # Documentation and specifications
├── src/
│   ├── simulation/
│   │   ├── core/                   # Units, state machines, wafer model, recipes
│   │   ├── equipment/              # Equipment simulators (etch, CVD, litho, etc.)
│   │   ├── process/                # Process physics models (oxidation, etch, deposition)
│   │   ├── facility/               # Cleanroom, gas delivery, utilities
│   │   ├── safety/                 # Interlocks, EMO, hazard management
│   │   ├── metrology/              # Measurements, SPC, defect inspection
│   │   └── mes/                    # MES, wafer tracking, dispatch, audit
│   ├── visualization/
│   │   ├── unity/                  # Unity/Unreal 3D environment
│   │   └── hmi/                    # Equipment HMI panels
│   ├── training/                   # Training engine, assessments, competency
│   └── data/
│       ├── nodes/                  # Process flows per technology node
│       │   ├── 180nm/
│       │   ├── 130nm/
│       │   ├── 65nm/
│       │   └── 22nm_fdsoi/
│       ├── equipment/              # Equipment specifications
│       ├── materials/              # Material properties
│       ├── recipes/                # Process recipes
│       └── standards/              # Standards references
└── tests/
    ├── unit/                       # Unit tests
    ├── integration/                # Integration tests
    └── validation/                 # Validation against reference data
```

---

## 🛠️ Technical Requirements

- **Python 3.11+** for simulation backend
- **Unity (HDRP/URP) or Unreal Engine 5** for 3D visualization
- **gRPC / WebSocket** for client-server communication
- **Protocol Buffers** for serialization

---

## 📄 License

MIT License — See [LICENSE](LICENSE) for details.

---

## ⚠️ Disclaimer

This software is an educational training simulator. It does not replace OEM equipment documentation, facility-specific operating procedures, or hands-on training under qualified supervision. Equipment interfaces are representative industry-style interfaces, not reproductions of proprietary OEM screens. All approximations in process models are documented with their limitations and valid operating ranges.
"# FABRICATION_LAB" 


## Deploy the web preview to Vercel

1. Import this repository at https://vercel.com/new.
2. Use the repository root (`./`) as Root Directory and **Flask** as Framework Preset.
3. Leave Build Command, Install Command and Output Directory at their defaults.
4. Deploy. No environment variables or database are required for this preview.
5. Check `/api/health`, then run a calculation on the home page.

`app.py` exports the Flask application. `vercel.json` sets a 30-second function
limit. `.python-version` selects Python 3.12. Assets in `public/assets` are served
by Vercel's CDN and templates are rendered by Flask. Deployment guidance:
https://vercel.com/docs/frameworks/backend/flask

### Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m flask --app app run
```

Open http://127.0.0.1:5000. Run all current unit and HTTP checks with:

```bash
python -m unittest discover -s tests/unit -v
```

Optional scientific, plotting and communication dependencies remain available
through `python -m pip install '.[full]'`. They are not needed by the web preview.

### Current web scope

- Responsive process dashboard, health check, input validation, growth chart and JSON export.
- Existing Deal–Grove oxidation model with fixed Si(100), 1 atm and thin-oxide
  enhancement disabled. Inputs are bounded to keep requests small and predictable.
- Model uncertainty is an estimate from the existing engine, not measured accuracy.
- Each request starts a separate calculation. There is no server-side history,
  authentication, database, background simulation or WebSocket service.
- Full wafer routes, other process tools and the walkable 3D client are not yet
  exposed in the browser. Persistent training sessions need durable storage;
  continuously running simulation services need a separate backend.
