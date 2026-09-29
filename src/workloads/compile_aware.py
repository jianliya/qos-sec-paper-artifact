from __future__ import annotations

from functools import lru_cache
from typing import Any

from core.job import Job

try:
    from qiskit import QuantumCircuit, transpile
    from qiskit.providers.fake_provider import GenericBackendV2

    QISKIT_AVAILABLE = True
except ModuleNotFoundError:
    QuantumCircuit = Any  # type: ignore
    transpile = None  # type: ignore
    GenericBackendV2 = Any  # type: ignore
    QISKIT_AVAILABLE = False


FAMILIES = (
    'small_qaoa',
    'bv_like',
    'grover_like',
    'random',
    'mirror',
)


def _default_compile_config() -> dict[str, int | str | None]:
    return {
        'optimization_level': 1,
        'seed_transpiler': None,
        'layout_method': None,
        'routing_method': None,
    }


def resolve_compile_config(compile_config: dict[str, Any] | None = None) -> dict[str, int | str | None]:
    resolved = _default_compile_config()
    if compile_config:
        resolved.update({k: v for k, v in compile_config.items() if k in resolved})
    opt_level = resolved.get('optimization_level', 1)
    if opt_level is None:
        opt_level = 1
    resolved['optimization_level'] = int(opt_level)
    if resolved.get('seed_transpiler') is not None:
        resolved['seed_transpiler'] = int(resolved['seed_transpiler'])  # type: ignore[index]
    return resolved


def qiskit_compile_available() -> bool:
    return bool(QISKIT_AVAILABLE)


def _job_index(job_id: str) -> int:
    digits = ''.join(ch for ch in job_id if ch.isdigit())
    if digits:
        return int(digits)
    return sum(ord(ch) for ch in job_id)


def _family_for_job(job: Job, label: str) -> str:
    explicit_family = job.metadata.notes.get('compile_family')
    if isinstance(explicit_family, str) and explicit_family:
        return explicit_family
    explicit_pool = job.metadata.notes.get('compile_family_pool')
    if isinstance(explicit_pool, (list, tuple)) and explicit_pool:
        pool = [str(x) for x in explicit_pool if str(x)]
        if pool:
            idx = _job_index(job.job_id)
            return pool[idx % len(pool)]
    idx = _job_index(job.job_id)
    if job.metadata.workload_tag == 'probe':
        return ('small_qaoa', 'mirror')[idx % 2]
    if label == 'classA':
        return ('small_qaoa', 'bv_like')[idx % 2]
    if label == 'classB':
        return ('grover_like', 'random')[idx % 2]
    if label == 'highIsolation':
        return ('mirror', 'grover_like')[idx % 2]
    return ('bv_like', 'random', 'mirror')[idx % 3]


def _line_coupling(num_qubits: int) -> list[list[int]]:
    edges: list[list[int]] = []
    for i in range(num_qubits - 1):
        edges.append([i, i + 1])
        edges.append([i + 1, i])
    return edges


def _ladder_coupling(num_qubits: int) -> list[list[int]]:
    edges: list[list[int]] = []
    top = list(range(0, num_qubits, 2))
    bottom = list(range(1, num_qubits, 2))
    for chain in (top, bottom):
        for a, b in zip(chain, chain[1:]):
            edges.append([a, b])
            edges.append([b, a])
    for a, b in zip(top, bottom):
        edges.append([a, b])
        edges.append([b, a])
    return edges


def _grid_coupling(num_qubits: int, cols: int = 3) -> list[list[int]]:
    edges: list[list[int]] = []
    rows = (num_qubits + cols - 1) // cols
    for r in range(rows):
        for c in range(cols):
            idx = r * cols + c
            if idx >= num_qubits:
                continue
            if c + 1 < cols:
                right = idx + 1
                if right < num_qubits:
                    edges.append([idx, right])
                    edges.append([right, idx])
            down = idx + cols
            if down < num_qubits:
                edges.append([idx, down])
                edges.append([down, idx])
    return edges


def _backend_topology(num_qubits: int) -> tuple[str, list[list[int]]]:
    if num_qubits <= 7:
        return 'line', _line_coupling(num_qubits)
    if num_qubits <= 13:
        return 'ladder', _ladder_coupling(num_qubits)
    return 'grid', _grid_coupling(num_qubits, cols=3)


def _synthetic_family_profile(family: str) -> dict[str, float]:
    profiles = {
        'small_qaoa': {'logical_qubits': 4.0, 'logical_depth': 12.0, 'logical_cx': 8.0, 'routing_sensitivity': 0.95},
        'bv_like': {'logical_qubits': 5.0, 'logical_depth': 8.0, 'logical_cx': 2.0, 'routing_sensitivity': 0.20},
        'grover_like': {'logical_qubits': 5.0, 'logical_depth': 14.0, 'logical_cx': 8.0, 'routing_sensitivity': 0.75},
        'random': {'logical_qubits': 6.0, 'logical_depth': 18.0, 'logical_cx': 12.0, 'routing_sensitivity': 1.15},
        'mirror': {'logical_qubits': 6.0, 'logical_depth': 16.0, 'logical_cx': 10.0, 'routing_sensitivity': 0.85},
    }
    if family not in profiles:
        raise ValueError(f'unknown synthetic compile family: {family}')
    return profiles[family]


def _synthetic_transpile_signature(
    family: str,
    num_qubits: int,
    optimization_level: int,
    seed_transpiler: int | None,
    layout_method: str | None,
    routing_method: str | None,
) -> dict[str, float | int | str]:
    topology_name, _ = _backend_topology(num_qubits)
    profile = _synthetic_family_profile(family)
    logical_qubits = int(profile['logical_qubits'])
    logical_depth = float(profile['logical_depth'])
    logical_cx = float(profile['logical_cx'])
    routing_sensitivity = float(profile['routing_sensitivity'])

    topology_penalty = {'line': 1.00, 'ladder': 0.55, 'grid': 0.30}[topology_name]
    seed_value = 0 if seed_transpiler is None else int(seed_transpiler)
    seed_phase = ((seed_value % 11) - 5) / 10.0
    width_pressure = max(0.0, logical_qubits / max(float(num_qubits), 1.0) - 0.35)
    layout_swap_bias = {
        None: 0.0,
        'trivial': 0.28,
        'dense': 0.12,
        'sabre': -0.18,
    }.get(layout_method, 0.0)
    routing_swap_bias = {
        None: 0.0,
        'basic': 0.32,
        'lookahead': 0.10,
        'sabre': -0.16,
    }.get(routing_method, 0.0)
    layout_depth_bias = {
        None: 0.0,
        'trivial': 0.9,
        'dense': 0.35,
        'sabre': -0.55,
    }.get(layout_method, 0.0)
    routing_depth_bias = {
        None: 0.0,
        'basic': 1.1,
        'lookahead': 0.4,
        'sabre': -0.6,
    }.get(routing_method, 0.0)
    layout_span_bias = {
        None: 0.0,
        'trivial': 1.1,
        'dense': 0.45,
        'sabre': -0.65,
    }.get(layout_method, 0.0)

    base_swap = max(0.0, routing_sensitivity * (topology_penalty * 4.0 + width_pressure * 6.0))
    seed_swap_shift = routing_sensitivity * topology_penalty * 0.45 * seed_phase
    swap_before_opt = max(0.0, base_swap + seed_swap_shift + layout_swap_bias + routing_swap_bias)
    opt_reduction = 1.0 - 0.16 * min(max(int(optimization_level), 0), 3)
    swap_count = max(0.0, round(swap_before_opt * opt_reduction))

    seed_depth_shift = routing_sensitivity * topology_penalty * 1.8 * seed_phase
    compiled_depth = max(
        logical_depth + 2.0,
        logical_depth
        + 2.4 * float(swap_count)
        + topology_penalty * routing_sensitivity * 3.5
        + layout_depth_bias
        + routing_depth_bias
        + seed_depth_shift
        - 1.2 * min(max(int(optimization_level), 0), 3),
    )
    cx_count = max(
        logical_cx,
        logical_cx
        + 3.0 * float(swap_count)
        + topology_penalty * routing_sensitivity * 1.5
        - 0.5 * min(max(int(optimization_level), 0), 3),
    )
    layout_span = min(
        num_qubits,
        max(
            logical_qubits,
            round(
                logical_qubits
                + topology_penalty * routing_sensitivity * 2.6
                + layout_span_bias
                + max(0.0, seed_phase) * 1.2
            ),
        ),
    )
    return {
        'family': family,
        'compiled_depth': int(round(compiled_depth)),
        'cx_count': int(round(cx_count)),
        'swap_count': int(round(swap_count)),
        'layout_span': int(layout_span),
        'topology': topology_name,
        'optimization_level': int(optimization_level),
        'seed_transpiler': -1 if seed_transpiler is None else int(seed_transpiler),
        'layout_method': layout_method or 'default',
        'routing_method': routing_method or 'default',
    }


@lru_cache(maxsize=16)
def _compile_backend(num_qubits: int) -> tuple[Any, str]:
    topology_name, coupling_map = _backend_topology(num_qubits)
    backend = GenericBackendV2(
        num_qubits=num_qubits,
        basis_gates=['id', 'rz', 'sx', 'x', 'cx'],
        coupling_map=coupling_map,
        seed=17 + num_qubits,
    )
    return backend, topology_name


def _small_qaoa() -> QuantumCircuit:
    qc = QuantumCircuit(4)
    for q in range(4):
        qc.h(q)
    for layer in range(2):
        for a, b in ((0, 3), (1, 2), (0, 2), (1, 3)):
            qc.cx(a, b)
        for q in range(4):
            qc.rz(0.25 + 0.05 * layer + 0.02 * q, q)
            qc.rx(0.18 + 0.03 * q, q)
    qc.measure_all()
    return qc


def _bv_like() -> QuantumCircuit:
    qc = QuantumCircuit(5)
    anc = 4
    qc.x(anc)
    qc.h(range(5))
    for q in range(4):
        if q % 2 == 0:
            qc.cx(q, anc)
    qc.h(range(4))
    qc.measure_all()
    return qc


def _grover_like() -> QuantumCircuit:
    qc = QuantumCircuit(5)
    qc.h(range(5))
    for a, b in ((0, 4), (1, 3), (0, 2), (2, 4)):
        qc.cx(a, b)
    for q in range(5):
        qc.rz(0.17 * (q + 1), q)
        qc.sx(q)
    for a, b in ((1, 4), (0, 3), (2, 4), (1, 2)):
        qc.cx(a, b)
    qc.measure_all()
    return qc


def _random_like() -> QuantumCircuit:
    qc = QuantumCircuit(6)
    for layer in range(4):
        for q in range(6):
            qc.rz(0.11 * (layer + 1) * (q + 1), q)
            if (layer + q) % 2 == 0:
                qc.sx(q)
        pairs = [(0, 5), (1, 4), (2, 3)] if layer % 2 == 0 else [(0, 3), (1, 5), (2, 4)]
        for a, b in pairs:
            qc.cx(a, b)
    qc.measure_all()
    return qc


def _mirror() -> QuantumCircuit:
    half = QuantumCircuit(6)
    for q in range(6):
        half.h(q)
        half.rz(0.13 * (q + 1), q)
    for pair in ((0, 5), (1, 4), (2, 3), (1, 5), (0, 4)):
        half.cx(*pair)
    qc = QuantumCircuit(6)
    qc.compose(half, inplace=True)
    for q in range(6):
        qc.rx(0.09 * (q + 1), q)
    for pair in ((0, 4), (1, 5), (2, 3), (1, 4), (0, 5)):
        qc.cx(*pair)
    qc.measure_all()
    return qc


@lru_cache(maxsize=16)
def _representative_circuit(family: str) -> QuantumCircuit:
    if family == 'small_qaoa':
        return _small_qaoa()
    if family == 'bv_like':
        return _bv_like()
    if family == 'grover_like':
        return _grover_like()
    if family == 'random':
        return _random_like()
    if family == 'mirror':
        return _mirror()
    raise ValueError(f'unknown compile family: {family}')


def _layout_span(transpiled_circuit: QuantumCircuit, logical_width: int) -> int:
    layout = getattr(transpiled_circuit, 'layout', None)
    if layout is None:
        return logical_width
    initial_layout = getattr(layout, 'initial_layout', None)
    physical: list[int] = []
    if initial_layout is not None and hasattr(initial_layout, 'get_virtual_bits'):
        mapping = initial_layout.get_virtual_bits()
        physical = sorted(int(v) for _, v in list(mapping.items())[:logical_width] if isinstance(v, int))
    elif hasattr(layout, 'input_qubit_mapping'):
        mapping = getattr(layout, 'input_qubit_mapping', {}) or {}
        if isinstance(mapping, dict):
            physical = sorted(int(v) for _, v in list(mapping.items())[:logical_width] if isinstance(v, int))
    if not physical:
        return logical_width
    return max(physical) - min(physical) + 1


@lru_cache(maxsize=512)
def _transpile_signature(
    family: str,
    num_qubits: int,
    optimization_level: int,
    seed_transpiler: int | None,
    layout_method: str | None,
    routing_method: str | None,
) -> dict[str, float | int | str]:
    if not QISKIT_AVAILABLE:
        return _synthetic_transpile_signature(
            family,
            num_qubits,
            optimization_level,
            seed_transpiler,
            layout_method,
            routing_method,
        )
    circuit = _representative_circuit(family)
    backend, topology_name = _compile_backend(num_qubits)
    transpile_kwargs: dict[str, Any] = {
        'backend': backend,
        'optimization_level': optimization_level,
    }
    if seed_transpiler is not None:
        transpile_kwargs['seed_transpiler'] = seed_transpiler
    if layout_method is not None:
        transpile_kwargs['layout_method'] = layout_method
    if routing_method is not None:
        transpile_kwargs['routing_method'] = routing_method
    compiled = transpile(circuit, **transpile_kwargs)
    ops = compiled.count_ops()
    logical_ops = circuit.count_ops()
    logical_cx = int(logical_ops.get('cx', 0))
    compiled_cx = int(ops.get('cx', 0))
    routing_overhead = max(0, compiled_cx - logical_cx)
    logical_width = int(circuit.num_qubits)
    return {
        'family': family,
        'compiled_depth': int(compiled.depth() or 0),
        'cx_count': compiled_cx,
        'swap_count': int(max(0, round(routing_overhead / 3.0))),
        'layout_span': int(_layout_span(compiled, logical_width)),
        'topology': topology_name,
        'optimization_level': int(optimization_level),
        'seed_transpiler': -1 if seed_transpiler is None else int(seed_transpiler),
    }


def _derive_expected_fidelity(job: Job, backend: Any, signature: dict[str, float | int | str]) -> float:
    quality = float(getattr(backend, 'quality_score', 0.9))
    noise_scale = float(getattr(backend, 'properties', {}).get('noise_scale', 0.0) or 0.0)
    crosstalk_risk = float(getattr(backend, 'properties', {}).get('crosstalk_risk', 0.0) or 0.0)
    depth_penalty = 0.00055 * float(signature['compiled_depth'])
    cx_penalty = 0.0028 * float(signature['cx_count'])
    swap_penalty = 0.0065 * float(signature['swap_count'])
    layout_penalty = 0.0045 * max(0.0, float(signature['layout_span']) - float(job.num_qubits()))
    fidelity = quality - depth_penalty - cx_penalty - swap_penalty - layout_penalty - 0.08 * noise_scale - 0.05 * crosstalk_risk
    return round(max(0.05, min(0.99, fidelity)), 4)


def _derive_suitability(job: Job, backend: Any, signature: dict[str, float | int | str], expected_fidelity: float) -> float:
    spare_qubits = max(0.0, float(getattr(backend, 'num_qubits', 0) - job.num_qubits()))
    tightness_penalty = max(0.0, float(job.num_qubits()) / max(float(getattr(backend, 'num_qubits', 1)), 1.0) - 0.45)
    queue_penalty = 0.035 * float(getattr(backend, 'queue_time', 0.0))
    util_penalty = 0.025 * float(getattr(backend, 'utilization', 0.0))
    swap_penalty = 0.015 * float(signature['swap_count'])
    suitability = expected_fidelity + 0.01 * min(spare_qubits, 6.0) - queue_penalty - util_penalty - swap_penalty - 0.06 * tightness_penalty
    return round(max(0.0, min(1.0, suitability)), 4)


def _compile_cost(signature: dict[str, float | int | str]) -> float:
    return round(
        0.010 * float(signature['compiled_depth'])
        + 0.060 * float(signature['swap_count'])
        + 0.004 * float(signature['cx_count'])
        + 0.010 * max(0.0, float(signature['layout_span']) - 3.0),
        4,
    )


def _features_for_backend(
    job: Job,
    backend: Any,
    family: str,
    compile_config: dict[str, Any] | None = None,
) -> dict[str, float | int | str]:
    resolved = resolve_compile_config(compile_config)
    default_seed = 23 + int(getattr(backend, 'num_qubits', 0))
    seed_transpiler = resolved['seed_transpiler']
    effective_seed = default_seed if seed_transpiler is None else int(seed_transpiler)
    signature = _transpile_signature(
        family,
        int(getattr(backend, 'num_qubits', 0)),
        int(resolved['optimization_level']),
        effective_seed,
        resolved['layout_method'],
        resolved['routing_method'],
    )
    expected_fidelity = _derive_expected_fidelity(job, backend, signature)
    suitability = _derive_suitability(job, backend, signature, expected_fidelity)
    noise_sensitivity = round(
        min(
            1.0,
            0.008 * float(signature['cx_count'])
            + 0.028 * float(signature['swap_count'])
            + 0.010 * float(signature['layout_span']),
        ),
        4,
    )
    if not QISKIT_AVAILABLE:
        backend_phase = ((sum(ord(ch) for ch in str(getattr(backend, 'backend_id', 'b0'))) % 9) - 4) / 4.0
        seed_phase = ((int(effective_seed) % 13) - 6) / 6.0
        opt_phase = (int(resolved['optimization_level']) - 1.5) / 1.5
        topology_name = str(signature.get('topology', 'grid'))
        topology_factor = {'line': 1.0, 'ladder': 0.6, 'grid': 0.35}.get(topology_name, 0.4)
        seed_backend_bias = topology_factor * backend_phase * seed_phase
        opt_backend_bias = topology_factor * backend_phase * opt_phase
        expected_fidelity = round(max(0.05, min(0.99, expected_fidelity + 0.012 * seed_backend_bias + 0.018 * opt_backend_bias)), 4)
        suitability = round(max(0.0, min(1.0, suitability + 0.035 * seed_backend_bias + 0.05 * opt_backend_bias)), 4)
        compile_cost = round(max(0.0, _compile_cost(signature) + 0.18 * topology_factor * max(0.0, seed_phase) - 0.12 * topology_factor * opt_phase), 4)
    else:
        compile_cost = _compile_cost(signature)
    return {
        **signature,
        'expected_fidelity': expected_fidelity,
        'backend_suitability': suitability,
        'compile_cost': compile_cost,
        'noise_sensitivity': noise_sensitivity,
        'optimization_level': int(resolved['optimization_level']),
        'seed_transpiler': int(effective_seed),
    }


def annotate_job_compile_features(
    job: Job,
    label: str,
    backends: list[Any],
    *,
    use_compile_path_variation: bool = True,
    use_eligibility_variation: bool = True,
    compile_config: dict[str, Any] | None = None,
) -> bool:
    if not use_compile_path_variation:
        return False
    family = _family_for_job(job, label)
    features_by_backend = {
        backend.backend_id: _features_for_backend(job, backend, family, compile_config)
        for backend in backends
    }
    ranked = sorted(
        features_by_backend.items(),
        key=lambda item: float(item[1]['backend_suitability']),
        reverse=True,
    )
    ordered_ids = [backend_id for backend_id, _ in ranked]
    if use_eligibility_variation:
        if label == 'classB':
            eligible = ordered_ids[: max(1, len(ordered_ids) - 1)]
        elif label == 'highIsolation':
            eligible = ordered_ids[:1]
        elif label == 'classA':
            eligible = ordered_ids[: max(1, len(ordered_ids) - 1)]
        else:
            eligible = ordered_ids
    else:
        eligible = ordered_ids
    selected = [features_by_backend[backend_id] for backend_id in eligible]
    mean_compile_cost = sum(float(item['compile_cost']) for item in selected) / max(len(selected), 1)
    mean_two_qubit = sum(float(item['cx_count']) for item in selected) / max(len(selected), 1)
    job.metadata.notes['compile_family'] = family
    job.metadata.notes['compile_features_by_backend'] = features_by_backend
    job.metadata.notes['compile_visibility'] = 'qiskit_transpile'
    job.metadata.notes['compile_config'] = resolve_compile_config(compile_config)
    job.estimated_compile_cost = round(mean_compile_cost, 4)
    job.two_qubit_gate_proxy = round(mean_two_qubit, 4)
    job.backend_eligibility = eligible
    return True


def get_backend_compile_features(job: Job, backend: Any) -> dict[str, float | int | str]:
    features_by_backend = job.metadata.notes.get('compile_features_by_backend', {})
    if backend.backend_id in features_by_backend:
        return dict(features_by_backend[backend.backend_id])
    transpilation_penalty = float(getattr(backend, 'properties', {}).get('transpilation_penalty', 1.0) or 1.0)
    noise_scale = float(getattr(backend, 'properties', {}).get('noise_scale', 0.0) or 0.0)
    crosstalk_risk = float(getattr(backend, 'properties', {}).get('crosstalk_risk', 0.0) or 0.0)
    compile_cost = float(getattr(job, 'estimated_compile_cost', 0.0) or 0.0)
    cx_count = float(getattr(job, 'two_qubit_gate_proxy', 0.0) or 0.0)
    expected_fidelity = max(0.0, min(0.99, float(getattr(backend, 'quality_score', 0.9)) - 0.03 * compile_cost * transpilation_penalty - 0.08 * noise_scale))
    suitability = max(0.0, min(1.0, expected_fidelity - 0.03 * crosstalk_risk))
    return {
        'family': job.metadata.notes.get('compile_family', 'fallback'),
        'compiled_depth': int(max(job.depth(), 0)),
        'cx_count': int(cx_count),
        'swap_count': 0,
        'layout_span': int(job.num_qubits()),
        'topology': 'fallback',
        'expected_fidelity': round(expected_fidelity, 4),
        'backend_suitability': round(suitability, 4),
        'compile_cost': round(compile_cost * transpilation_penalty, 4),
        'noise_sensitivity': round(min(1.0, 0.06 * noise_scale + 0.04 * crosstalk_risk), 4),
    }


def representative_compile_catalog(
    backends: list[Any],
    compile_config: dict[str, Any] | None = None,
) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    resolved = resolve_compile_config(compile_config)
    for family in FAMILIES:
        job_stub = Job(job_id=f'catalog-{family}', tenant_id='catalog', circuit=None, submit_time=0.0)
        job_stub.logical_qubits = int(_synthetic_family_profile(family)['logical_qubits'])
        job_stub.depth_proxy = 0.0
        for backend in backends:
            features = _features_for_backend(job_stub, backend, family, resolved)
            rows.append({
                'family': family,
                'backend_id': backend.backend_id,
                'backend_qubits': int(getattr(backend, 'num_qubits', 0)),
                'compiled_depth': int(features['compiled_depth']),
                'cx_count': int(features['cx_count']),
                'swap_count': int(features['swap_count']),
                'layout_span': int(features['layout_span']),
                'expected_fidelity': round(float(features['expected_fidelity']), 4),
                'backend_suitability': round(float(features['backend_suitability']), 4),
                'topology': str(features['topology']),
                'optimization_level': int(features.get('optimization_level', resolved['optimization_level'])),
                'seed_transpiler': int(features.get('seed_transpiler', resolved.get('seed_transpiler') or -1)),
            })
    return rows
