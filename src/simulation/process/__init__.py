"""Process Simulation Module for Semiconductor Fabrication Digital Twin.

Exports physical models and kinetics simulators for:
  - Thermal Oxidation (Deal-Grove linear-parabolic, Massoud thin enhancement, dopant effects)
  - Plasma Etching (Coburn-Winters ion-enhanced kinetics, ARDE lag, microloading, OES endpoint)
  - Thin-Film Deposition (Grove CVD series transport, LPCVD, PECVD, PVD sputtering, ALD)
  - Ion Implantation (Gibbons/SRIM ranges, Dual Pearson profiles, damage/amorphization, RTA activation)
"""

from src.simulation.process.deposition_models import (
    ALDCycleState,
    CVDDepositionKinetics,
    DepositionFilm,
    DepositionProcessType,
    DepositionSimulator,
    FilmMaterialProperties,
    KineticRegime,
    ThinFilmState,
)
from src.simulation.process.etch_models import (
    EndpointSignalPoint,
    EtchGasChemistry,
    EtchProfileResult,
    EtchRateComponents,
    MaterialEtchParameters,
    PlasmaEtchModel,
    PlasmaState,
    RadialProfileShape,
    SubstrateMaterial,
    WaferRadialEtchUniformity,
)
from src.simulation.process.implant_models import (
    AnnealActivationResult,
    ImplantDamageModel,
    ImplantProfilePoint,
    ImplantSimulationResult,
    ImplantSpecies,
    IonImplantModel,
    RangeStatistics,
)
from src.simulation.process.thermal_oxidation import (
    DealGroveParameters,
    DopantType,
    OxidationAmbient,
    OxidationProfilePoint,
    OxidationResult,
    SiliconOrientation,
    ThermalOxidationModel,
)

__all__ = [
    # Thermal Oxidation
    "ThermalOxidationModel",
    "OxidationAmbient",
    "SiliconOrientation",
    "DopantType",
    "DealGroveParameters",
    "OxidationProfilePoint",
    "OxidationResult",
    # Plasma Etch
    "PlasmaEtchModel",
    "SubstrateMaterial",
    "EtchGasChemistry",
    "RadialProfileShape",
    "MaterialEtchParameters",
    "PlasmaState",
    "EtchRateComponents",
    "EtchProfileResult",
    "EndpointSignalPoint",
    "WaferRadialEtchUniformity",
    # Deposition
    "DepositionSimulator",
    "DepositionProcessType",
    "DepositionFilm",
    "KineticRegime",
    "FilmMaterialProperties",
    "CVDDepositionKinetics",
    "ThinFilmState",
    "ALDCycleState",
    # Ion Implantation
    "IonImplantModel",
    "ImplantSpecies",
    "RangeStatistics",
    "ImplantDamageModel",
    "AnnealActivationResult",
    "ImplantProfilePoint",
    "ImplantSimulationResult",
]
