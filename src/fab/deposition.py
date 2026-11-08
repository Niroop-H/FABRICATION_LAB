"""Time-dependent adapter for the existing, uncalibrated LPCVD kinetics model."""
from src.simulation.process.deposition_models import DepositionSimulator, DepositionFilm
from src.simulation.core.wafer import Wafer, Layer
from src.simulation.core.units import film_thickness


def growth_rate(parameters):
    return DepositionSimulator().calculate_cvd_kinetics(
        DepositionFilm.LPCVD_POLYSILICON, parameters['temperature_c'],
        parameters['pressure_torr'], parameters['flow_sccm']).net_growth_rate_nm_min


def advance_film(state, step, tool, elapsed):
    """Integrate constant setpoints over elapsed simulated time, preserving partial films."""
    rate=growth_rate(tool['recipe'])
    wafer=Wafer.from_dict(state['wafer'])
    layer=next((layer for layer in wafer.layer_stack.layers if layer.layer_id==step['id']),None)
    thickness=(layer.thickness.value if layer else 0.0)+rate*elapsed/60
    quantity=film_thickness(thickness,'nm',uncertainty=0.0,
        source='Existing Grove-series LPCVD model; uncertainty uncharacterized (not zero physical error)')
    if layer:
        layer.thickness=quantity
    else:
        wafer.layer_stack.add_layer(Layer(step['id'],step['name'],'Si',quantity,
            deposition_method='LPCVD',process_step_id=step['id']))
    state['wafer']=wafer.to_dict()
    trend=tool.get('trend') or [{'time_s':0.0,'thickness_nm':0.0}]
    tool['trend']=trend
    trend.append({'time_s':state['clock']+elapsed-tool['started'],'thickness_nm':thickness})
    # Telemetry is a display sample, unlike the complete audit trail.
    if len(trend)>120:
        tool['trend']=[trend[0]]+trend[-119:]
