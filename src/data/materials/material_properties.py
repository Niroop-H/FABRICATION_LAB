"""
Material Properties Database
=============================

Comprehensive material properties for semiconductor fabrication simulation.

All values include units, valid ranges, temperature dependencies where applicable,
and literature references. Values represent typical bulk properties; actual thin-film
properties may vary with deposition conditions, thickness, and microstructure.

References:
- Sze & Ng, "Physics of Semiconductor Devices", 3rd ed., Wiley (2007)
- Campbell, "Science and Engineering of Microelectronic Fabrication", Oxford (2001)
- Wolf & Tauber, "Silicon Processing for the VLSI Era", Lattice Press (2000)
- Plummer, Deal & Griffin, "Silicon VLSI Technology", Prentice Hall (2000)
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class MaterialCategory(Enum):
    """Classification of materials used in semiconductor fabrication."""
    SEMICONDUCTOR = auto()
    DIELECTRIC = auto()
    CONDUCTOR = auto()
    BARRIER = auto()
    PHOTORESIST = auto()
    SLURRY = auto()
    PROCESS_GAS = auto()
    CHEMICAL = auto()
    SUBSTRATE = auto()


class HazardClass(Enum):
    """Safety classification for hazardous materials."""
    NONE = "Non-hazardous"
    FLAMMABLE = "Flammable"
    PYROPHORIC = "Pyrophoric (spontaneously ignites in air)"
    TOXIC = "Toxic"
    CORROSIVE = "Corrosive"
    OXIDIZING = "Oxidizing"
    CARCINOGENIC = "Carcinogenic"
    COMPRESSED_GAS = "Compressed gas"
    CRYOGENIC = "Cryogenic liquid"


@dataclass(frozen=True)
class ThermalProperties:
    """Thermal properties of a material."""
    melting_point_K: Optional[float] = None        # Kelvin
    boiling_point_K: Optional[float] = None        # Kelvin
    thermal_conductivity_W_mK: Optional[float] = None  # W/(m·K) at 300K
    specific_heat_J_kgK: Optional[float] = None    # J/(kg·K) at 300K
    thermal_expansion_1_K: Optional[float] = None   # 1/K (linear CTE)


@dataclass(frozen=True)
class ElectricalProperties:
    """Electrical properties of a material."""
    resistivity_ohm_cm: Optional[float] = None     # Ω·cm at 300K
    dielectric_constant: Optional[float] = None     # relative permittivity (κ)
    breakdown_field_MV_cm: Optional[float] = None   # MV/cm
    bandgap_eV: Optional[float] = None             # eV at 300K
    electron_mobility_cm2_Vs: Optional[float] = None  # cm²/(V·s) (intrinsic)
    hole_mobility_cm2_Vs: Optional[float] = None      # cm²/(V·s) (intrinsic)
    work_function_eV: Optional[float] = None        # eV


@dataclass(frozen=True)
class OpticalProperties:
    """Optical properties of a material."""
    refractive_index_633nm: Optional[float] = None  # at 633nm (HeNe laser)
    refractive_index_248nm: Optional[float] = None  # at 248nm (KrF)
    refractive_index_193nm: Optional[float] = None  # at 193nm (ArF)
    absorption_coeff_1_cm: Optional[float] = None   # 1/cm at specified wavelength


@dataclass(frozen=True)
class MechanicalProperties:
    """Mechanical properties of a material."""
    density_kg_m3: Optional[float] = None           # kg/m³
    youngs_modulus_GPa: Optional[float] = None      # GPa
    poissons_ratio: Optional[float] = None
    hardness_GPa: Optional[float] = None            # GPa (Vickers or nano-indentation)
    intrinsic_stress_MPa: Optional[float] = None    # MPa (thin film, process-dependent)


@dataclass(frozen=True)
class SafetyData:
    """Safety and hazard data for a material."""
    hazard_classes: tuple[HazardClass, ...] = (HazardClass.NONE,)
    tlv_ppm: Optional[float] = None        # Threshold Limit Value (ppm)
    idlh_ppm: Optional[float] = None       # Immediately Dangerous to Life/Health (ppm)
    lel_percent: Optional[float] = None     # Lower Explosive Limit (%)
    uel_percent: Optional[float] = None     # Upper Explosive Limit (%)
    nfpa_health: int = 0                    # NFPA 704 health hazard (0-4)
    nfpa_flammability: int = 0              # NFPA 704 flammability (0-4)
    nfpa_reactivity: int = 0               # NFPA 704 reactivity (0-4)
    special_hazards: str = ""               # Additional hazard notes


@dataclass(frozen=True)
class Material:
    """Complete material definition for semiconductor fabrication."""
    name: str
    formula: str
    category: MaterialCategory
    description: str
    thermal: ThermalProperties = field(default_factory=ThermalProperties)
    electrical: ElectricalProperties = field(default_factory=ElectricalProperties)
    optical: OpticalProperties = field(default_factory=OpticalProperties)
    mechanical: MechanicalProperties = field(default_factory=MechanicalProperties)
    safety: SafetyData = field(default_factory=SafetyData)
    references: tuple[str, ...] = ()
    notes: str = ""


# ============================================================================
# SEMICONDUCTOR MATERIALS
# ============================================================================

SILICON = Material(
    name="Silicon",
    formula="Si",
    category=MaterialCategory.SEMICONDUCTOR,
    description="Primary substrate material for CMOS fabrication",
    thermal=ThermalProperties(
        melting_point_K=1687,
        thermal_conductivity_W_mK=149,
        specific_heat_J_kgK=700,
        thermal_expansion_1_K=2.6e-6,
    ),
    electrical=ElectricalProperties(
        resistivity_ohm_cm=2.3e5,  # intrinsic at 300K
        dielectric_constant=11.7,
        bandgap_eV=1.12,
        electron_mobility_cm2_Vs=1400,
        hole_mobility_cm2_Vs=450,
        work_function_eV=4.05,  # electron affinity
    ),
    optical=OpticalProperties(
        refractive_index_633nm=3.88,
    ),
    mechanical=MechanicalProperties(
        density_kg_m3=2329,
        youngs_modulus_GPa=130,  # <100> direction
        poissons_ratio=0.28,
        hardness_GPa=12.5,
    ),
    references=(
        "Sze & Ng, Physics of Semiconductor Devices, 3rd ed., Table 1.1",
        "Plummer et al., Silicon VLSI Technology, Appendix A",
    ),
)

SILICON_GERMANIUM = Material(
    name="Silicon Germanium",
    formula="Si1-xGex",
    category=MaterialCategory.SEMICONDUCTOR,
    description=(
        "Strained SiGe for PMOS source/drain (compressive stress to channel) "
        "and raised source/drain in FD-SOI. x typically 0.17-0.35 for eSiGe."
    ),
    thermal=ThermalProperties(
        melting_point_K=1483,  # for x~0.25
        thermal_conductivity_W_mK=8.0,  # significantly lower than pure Si
    ),
    electrical=ElectricalProperties(
        bandgap_eV=0.95,  # for x~0.25, decreases with Ge content
    ),
    mechanical=MechanicalProperties(
        density_kg_m3=3460,  # for x~0.25
    ),
    notes="Properties depend strongly on Ge fraction x. Lattice constant = 5.431 + 0.20x Å",
    references=("Kasper & Lyutovich, Properties of Silicon Germanium and SiGe:Carbon, INSPEC",),
)

# ============================================================================
# DIELECTRIC MATERIALS
# ============================================================================

SILICON_DIOXIDE = Material(
    name="Silicon Dioxide",
    formula="SiO2",
    category=MaterialCategory.DIELECTRIC,
    description=(
        "Primary gate and isolation dielectric. Grown thermally or deposited "
        "by CVD (TEOS, silane, HDP, HARP). Thermal oxide on Si(100) has the "
        "highest quality interface."
    ),
    thermal=ThermalProperties(
        melting_point_K=1986,
        thermal_conductivity_W_mK=1.4,
        specific_heat_J_kgK=740,
        thermal_expansion_1_K=0.5e-6,
    ),
    electrical=ElectricalProperties(
        dielectric_constant=3.9,
        breakdown_field_MV_cm=10.0,  # thermal oxide; CVD oxides typically 8-9
        bandgap_eV=9.0,
        resistivity_ohm_cm=1e15,
    ),
    optical=OpticalProperties(
        refractive_index_633nm=1.46,
        refractive_index_248nm=1.51,
        refractive_index_193nm=1.56,
    ),
    mechanical=MechanicalProperties(
        density_kg_m3=2200,  # thermal oxide
        youngs_modulus_GPa=70,
        poissons_ratio=0.17,
        intrinsic_stress_MPa=-300,  # compressive for thermal oxide on Si
    ),
    references=(
        "Plummer et al., Silicon VLSI Technology, Chapter 6",
        "Wolf & Tauber, Silicon Processing, Vol. 1, Chapter 3",
    ),
)

SILICON_NITRIDE = Material(
    name="Silicon Nitride",
    formula="Si3N4",
    category=MaterialCategory.DIELECTRIC,
    description=(
        "Used as oxidation mask (LOCOS/STI), etch stop, passivation layer, "
        "and stress liner (DSL). LPCVD Si3N4 is stoichiometric; PECVD SiN "
        "is typically silicon-rich (SixNy) with adjustable stress."
    ),
    thermal=ThermalProperties(
        melting_point_K=2173,  # decomposes
        thermal_conductivity_W_mK=30,
        thermal_expansion_1_K=3.3e-6,
    ),
    electrical=ElectricalProperties(
        dielectric_constant=7.5,  # LPCVD stoichiometric
        breakdown_field_MV_cm=10.0,
        bandgap_eV=5.3,
        resistivity_ohm_cm=1e14,
    ),
    optical=OpticalProperties(
        refractive_index_633nm=2.05,  # LPCVD stoichiometric; PECVD: 1.8-2.1
    ),
    mechanical=MechanicalProperties(
        density_kg_m3=3100,
        youngs_modulus_GPa=290,
        poissons_ratio=0.27,
        intrinsic_stress_MPa=1200,  # LPCVD: high tensile; PECVD: adjustable -2000 to +1500
    ),
    references=(
        "Plummer et al., Silicon VLSI Technology, Chapter 6",
        "Sze, VLSI Technology, Chapter 6",
    ),
    notes=(
        "PECVD SiN stress is tunable from ~-2 GPa (compressive, high-frequency RF) "
        "to ~+1.5 GPa (tensile, low-frequency RF). Critical for DSL strain engineering."
    ),
)

HAFNIUM_OXIDE = Material(
    name="Hafnium Oxide",
    formula="HfO2",
    category=MaterialCategory.DIELECTRIC,
    description=(
        "High-k gate dielectric replacing SiO2/SiON at 45nm and below. "
        "Deposited by ALD for atomic-level thickness control. "
        "Used in 22nm FD-SOI HKMG gate stacks with EOT ~0.9-1.0nm."
    ),
    thermal=ThermalProperties(
        melting_point_K=3031,
        thermal_conductivity_W_mK=1.1,
    ),
    electrical=ElectricalProperties(
        dielectric_constant=22.0,  # monoclinic phase; can vary 16-25 depending on phase
        breakdown_field_MV_cm=3.9,
        bandgap_eV=5.8,
    ),
    optical=OpticalProperties(
        refractive_index_633nm=1.9,
    ),
    mechanical=MechanicalProperties(
        density_kg_m3=9680,
        youngs_modulus_GPa=260,
    ),
    references=(
        "Robertson, Rep. Prog. Phys. 69, 327 (2006)",
        "Wilk et al., J. Appl. Phys. 89, 5243 (2001)",
    ),
)

LOW_K_SICOH = Material(
    name="Carbon-Doped Oxide (SiCOH)",
    formula="SiCOH",
    category=MaterialCategory.DIELECTRIC,
    description=(
        "Low-k inter-metal dielectric for Cu dual damascene interconnects. "
        "Dense SiCOH k~2.7-3.0 (e.g., Black Diamond I), "
        "porous p-SiCOH k~2.4-2.6 (e.g., Black Diamond II). "
        "Deposited by PECVD from DEMS/OMCTS precursors."
    ),
    electrical=ElectricalProperties(
        dielectric_constant=2.7,  # dense SiCOH; porous: 2.4-2.6
        breakdown_field_MV_cm=5.0,
    ),
    mechanical=MechanicalProperties(
        density_kg_m3=1400,  # porous
        youngs_modulus_GPa=8.0,  # porous; dense ~15 GPa; much weaker than SiO2
        hardness_GPa=1.5,
    ),
    references=(
        "Grill, J. Appl. Phys. 93, 1785 (2003)",
        "Maex et al., J. Appl. Phys. 93, 8793 (2003)",
    ),
    notes="Mechanically fragile. Requires special CMP with low downforce (<1.5 psi).",
)

# ============================================================================
# CONDUCTOR MATERIALS
# ============================================================================

ALUMINUM = Material(
    name="Aluminum (Al-0.5%Cu)",
    formula="Al",
    category=MaterialCategory.CONDUCTOR,
    description=(
        "Primary metallization for 180nm and above. Deposited by PVD sputtering. "
        "0.5% Cu added to resist electromigration. Patterned by subtractive RIE "
        "using Cl2/BCl3 chemistry."
    ),
    thermal=ThermalProperties(
        melting_point_K=933,
        thermal_conductivity_W_mK=237,
        thermal_expansion_1_K=23.1e-6,
    ),
    electrical=ElectricalProperties(
        resistivity_ohm_cm=2.7e-6,  # bulk; thin film ~3.0-3.5e-6
        work_function_eV=4.08,
    ),
    mechanical=MechanicalProperties(
        density_kg_m3=2700,
        youngs_modulus_GPa=70,
    ),
    references=("Sze, VLSI Technology, Chapter 9",),
)

COPPER = Material(
    name="Copper",
    formula="Cu",
    category=MaterialCategory.CONDUCTOR,
    description=(
        "Primary metallization for 130nm and below. Deposited by electrochemical "
        "deposition (ECD/electroplating) over PVD seed layer. Patterned by "
        "dual damascene CMP (cannot be RIE etched in production). "
        "Requires Ta/TaN barrier to prevent Cu diffusion into dielectric."
    ),
    thermal=ThermalProperties(
        melting_point_K=1358,
        thermal_conductivity_W_mK=401,
        thermal_expansion_1_K=16.5e-6,
    ),
    electrical=ElectricalProperties(
        resistivity_ohm_cm=1.7e-6,  # bulk; thin film ~2.0-2.5e-6 (grain boundary scattering)
        work_function_eV=4.65,
    ),
    mechanical=MechanicalProperties(
        density_kg_m3=8960,
        youngs_modulus_GPa=130,
    ),
    references=("Sze, VLSI Technology, Chapter 9",),
    notes=(
        "Cu resistivity increases significantly below ~50nm width due to "
        "grain boundary and surface scattering (Fuchs-Sondheimer model). "
        "At 22nm M1 pitch (~40nm half-pitch), effective resistivity can be 4-6 μΩ·cm."
    ),
)

TUNGSTEN = Material(
    name="Tungsten",
    formula="W",
    category=MaterialCategory.CONDUCTOR,
    description=(
        "Used for contact plugs (W-plugs) connecting FEOL devices to M1. "
        "Deposited by CVD from WF6 + H2/SiH4. Also used for local interconnect "
        "and some via fills."
    ),
    thermal=ThermalProperties(
        melting_point_K=3695,
        thermal_conductivity_W_mK=173,
    ),
    electrical=ElectricalProperties(
        resistivity_ohm_cm=5.6e-6,  # bulk; CVD W thin film ~8-15e-6
        work_function_eV=4.55,
    ),
    mechanical=MechanicalProperties(
        density_kg_m3=19300,
        youngs_modulus_GPa=411,
    ),
    references=("Campbell, Microelectronic Fabrication, Chapter 11",),
)

TITANIUM_NITRIDE = Material(
    name="Titanium Nitride",
    formula="TiN",
    category=MaterialCategory.BARRIER,
    description=(
        "Diffusion barrier and adhesion layer. Used as ARC (anti-reflective coating) "
        "for Al metallization, barrier liner for W-plugs, and work-function metal "
        "in HKMG gate stacks."
    ),
    electrical=ElectricalProperties(
        resistivity_ohm_cm=50e-6,  # PVD; ALD: 100-200e-6
        work_function_eV=4.6,  # can vary 4.4-4.8 depending on deposition
    ),
    mechanical=MechanicalProperties(
        density_kg_m3=5240,
        youngs_modulus_GPa=251,
        hardness_GPa=20.0,
    ),
    references=("Kang & Kim, Atomic Layer Deposition, Cambridge (2011)",),
)

TANTALUM_NITRIDE = Material(
    name="Tantalum Nitride",
    formula="TaN",
    category=MaterialCategory.BARRIER,
    description=(
        "Primary Cu diffusion barrier for dual damascene interconnects. "
        "Deposited by PVD or ALD. Used with Ta liner for Cu adhesion."
    ),
    electrical=ElectricalProperties(
        resistivity_ohm_cm=200e-6,  # PVD
    ),
    mechanical=MechanicalProperties(
        density_kg_m3=13800,
        hardness_GPa=30.0,
    ),
    references=("Sze, VLSI Technology, Chapter 9",),
)

# ============================================================================
# PROCESS GASES
# ============================================================================

SILANE = Material(
    name="Silane",
    formula="SiH4",
    category=MaterialCategory.PROCESS_GAS,
    description=(
        "Primary silicon precursor for LPCVD and PECVD. Pyrophoric - "
        "spontaneously ignites in air. Used for polysilicon, amorphous Si, "
        "PECVD SiO2 (with N2O), and PECVD SiN (with NH3) deposition."
    ),
    thermal=ThermalProperties(
        boiling_point_K=161,  # -112°C
    ),
    safety=SafetyData(
        hazard_classes=(HazardClass.PYROPHORIC, HazardClass.FLAMMABLE, HazardClass.TOXIC),
        tlv_ppm=5.0,
        idlh_ppm=50.0,
        lel_percent=1.37,
        uel_percent=96.0,
        nfpa_health=2,
        nfpa_flammability=4,
        nfpa_reactivity=2,
        special_hazards="Pyrophoric. Spontaneously ignites at concentrations >2% in air.",
    ),
    references=("Matheson Gas Data Book, 7th ed.",),
)

CHLORINE = Material(
    name="Chlorine",
    formula="Cl2",
    category=MaterialCategory.PROCESS_GAS,
    description="Etch gas for polysilicon and metal etching. Highly toxic and corrosive.",
    safety=SafetyData(
        hazard_classes=(HazardClass.TOXIC, HazardClass.CORROSIVE, HazardClass.OXIDIZING),
        tlv_ppm=0.5,
        idlh_ppm=10.0,
        nfpa_health=3,
        nfpa_flammability=0,
        nfpa_reactivity=0,
        special_hazards="Highly toxic. Reacts violently with many materials.",
    ),
    references=("Matheson Gas Data Book",),
)

HYDROGEN_FLUORIDE = Material(
    name="Hydrogen Fluoride",
    formula="HF",
    category=MaterialCategory.CHEMICAL,
    description=(
        "Used in aqueous solution (49% HF or dilute HF/DHF) for SiO2 etching "
        "and native oxide removal. BOE (buffered oxide etch) uses NH4F:HF mixture. "
        "EXTREMELY DANGEROUS - causes deep tissue burns and systemic fluoride poisoning."
    ),
    safety=SafetyData(
        hazard_classes=(HazardClass.TOXIC, HazardClass.CORROSIVE),
        tlv_ppm=0.5,  # ceiling limit
        idlh_ppm=30.0,
        nfpa_health=4,
        nfpa_flammability=0,
        nfpa_reactivity=1,
        special_hazards=(
            "EXTREMELY HAZARDOUS. Aqueous HF causes severe, potentially fatal burns "
            "that may not be immediately painful. Penetrates skin and attacks bone. "
            "Systemic fluoride poisoning can cause cardiac arrest. "
            "Calcium gluconate gel must be immediately available."
        ),
    ),
    references=("Matheson Gas Data Book", "OSHA HF Safety Guidelines"),
)

CF4 = Material(
    name="Carbon Tetrafluoride",
    formula="CF4",
    category=MaterialCategory.PROCESS_GAS,
    description=(
        "Fluorocarbon etch gas for SiO2 and Si3N4 etching. "
        "Generates F* radicals and CFx+ ions in plasma. "
        "High GWP (global warming potential = 6,500)."
    ),
    safety=SafetyData(
        hazard_classes=(HazardClass.COMPRESSED_GAS,),
        tlv_ppm=None,  # simple asphyxiant
        nfpa_health=1,
        nfpa_flammability=0,
        nfpa_reactivity=0,
        special_hazards="Simple asphyxiant. Very high GWP (6,500). Abatement required.",
    ),
    references=("Matheson Gas Data Book",),
)

ARSINE = Material(
    name="Arsine",
    formula="AsH3",
    category=MaterialCategory.PROCESS_GAS,
    description=(
        "N-type dopant source for ion implantation and epitaxy. "
        "One of the most toxic gases used in semiconductor manufacturing."
    ),
    safety=SafetyData(
        hazard_classes=(HazardClass.TOXIC, HazardClass.FLAMMABLE),
        tlv_ppm=0.005,
        idlh_ppm=3.0,
        lel_percent=4.5,
        uel_percent=78.0,
        nfpa_health=4,
        nfpa_flammability=4,
        nfpa_reactivity=2,
        special_hazards=(
            "EXTREMELY TOXIC. Exposure to 250 ppm for 30 minutes is lethal. "
            "Destroys red blood cells causing hemolytic anemia. "
            "Requires continuous toxic gas monitoring (TGM) in all areas."
        ),
    ),
    references=("SEMI S2", "Matheson Gas Data Book"),
)

PHOSPHINE = Material(
    name="Phosphine",
    formula="PH3",
    category=MaterialCategory.PROCESS_GAS,
    description="N-type dopant source for ion implantation and doping.",
    safety=SafetyData(
        hazard_classes=(HazardClass.TOXIC, HazardClass.FLAMMABLE, HazardClass.PYROPHORIC),
        tlv_ppm=0.3,
        idlh_ppm=50.0,
        lel_percent=1.79,
        nfpa_health=4,
        nfpa_flammability=4,
        nfpa_reactivity=2,
        special_hazards="Extremely toxic and pyrophoric at higher concentrations.",
    ),
    references=("Matheson Gas Data Book",),
)

NITROGEN = Material(
    name="Nitrogen",
    formula="N2",
    category=MaterialCategory.PROCESS_GAS,
    description=(
        "Inert purge gas, carrier gas, and atmospheric control. "
        "Bulk supply from air separation plant. Used for FOUP purging "
        "and equipment purge/vent cycles."
    ),
    thermal=ThermalProperties(
        boiling_point_K=77.4,
    ),
    safety=SafetyData(
        hazard_classes=(HazardClass.COMPRESSED_GAS, HazardClass.CRYOGENIC),
        special_hazards="Simple asphyxiant. Liquid N2 causes cryogenic burns.",
    ),
    references=("Matheson Gas Data Book",),
)

ARGON = Material(
    name="Argon",
    formula="Ar",
    category=MaterialCategory.PROCESS_GAS,
    description=(
        "Noble gas used as sputter gas in PVD, carrier/dilution gas in CVD/etch, "
        "and backside cooling gas. Inert and non-reactive."
    ),
    safety=SafetyData(
        hazard_classes=(HazardClass.COMPRESSED_GAS,),
        special_hazards="Simple asphyxiant.",
    ),
    references=("Matheson Gas Data Book",),
)


# ============================================================================
# MATERIAL REGISTRY
# ============================================================================

MATERIALS_REGISTRY: dict[str, Material] = {
    # Semiconductors
    "Si": SILICON,
    "SiGe": SILICON_GERMANIUM,
    # Dielectrics
    "SiO2": SILICON_DIOXIDE,
    "Si3N4": SILICON_NITRIDE,
    "HfO2": HAFNIUM_OXIDE,
    "SiCOH": LOW_K_SICOH,
    # Conductors
    "Al": ALUMINUM,
    "Cu": COPPER,
    "W": TUNGSTEN,
    # Barriers
    "TiN": TITANIUM_NITRIDE,
    "TaN": TANTALUM_NITRIDE,
    # Process Gases
    "SiH4": SILANE,
    "Cl2": CHLORINE,
    "HF": HYDROGEN_FLUORIDE,
    "CF4": CF4,
    "AsH3": ARSINE,
    "PH3": PHOSPHINE,
    "N2": NITROGEN,
    "Ar": ARGON,
}


def get_materials_by_category(category: MaterialCategory) -> list[Material]:
    """Get all materials in a given category."""
    return [m for m in MATERIALS_REGISTRY.values() if m.category == category]


def get_hazardous_materials() -> list[Material]:
    """Get all materials with non-trivial hazard classifications."""
    return [
        m for m in MATERIALS_REGISTRY.values()
        if m.safety.hazard_classes != (HazardClass.NONE,)
        and m.safety.hazard_classes != (HazardClass.COMPRESSED_GAS,)
    ]
