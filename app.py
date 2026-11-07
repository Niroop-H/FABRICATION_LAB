"""Stateless web interface for the educational fabrication simulator."""
import math
from dataclasses import asdict

from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.exceptions import HTTPException

from src.simulation.process.thermal_oxidation import OxidationAmbient, ThermalOxidationModel

app = Flask(__name__, static_folder=None)
from src.fab.api import fab
app.register_blueprint(fab)

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024


@app.get('/')
def index():
    return render_template('fab.html')


@app.get('/calculator')
def calculator():
    return render_template('index.html')


@app.get('/assets/<path:filename>')
def assets(filename):
    # Vercel serves public/assets directly; this route supports local Flask runs.
    return send_from_directory('public/assets', filename)


@app.get('/api/health')
def health():
    return {'status': 'ok', 'mode': 'educational', 'persistence': 'none'}


def number(data, name, low, high):
    value = data.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name} must be a number.')
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} must be between {low} and {high}.')
    return float(value)


@app.post('/api/simulate/oxidation')
def oxidation():
    data = request.get_json()
    if not isinstance(data, dict):
        return {'error': 'Provide a JSON object.'}, 400
    try:
        temperature = number(data, 'temperature_c', 800, 1100)
        seconds = number(data, 'duration_s', 60, 7200)
        initial = number(data, 'initial_thickness_nm', 0, 100)
        ambient = data.get('ambient', 'DRY_O2')
        if ambient not in ('DRY_O2', 'WET_H2O'):
            raise ValueError('ambient must be DRY_O2 or WET_H2O.')
        result = ThermalOxidationModel().simulate_oxidation(
            temperature, seconds, ambient=OxidationAmbient(ambient),
            initial_thickness_nm=initial, enable_thin_oxide_enhancement=False,
            time_steps=100,
        )
    except ValueError as exc:
        return {'error': str(exc)}, 400
    return jsonify(
        final_thickness_nm=result.final_thickness.value,
        uncertainty_nm=result.final_thickness.uncertainty,
        profile=[asdict(point) for point in result.time_series],
        model='Deal–Grove, Si(100), 1 atm, no thin-oxide correction',
        limitation='Educational estimate; not a validated manufacturing recipe.',
    )


@app.errorhandler(HTTPException)
def http_error(error):
    if request.path.startswith('/api/'):
        return jsonify(error=error.description), error.code
    return error


@app.after_request
def headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response
