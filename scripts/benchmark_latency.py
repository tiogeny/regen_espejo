"""
Benchmark de Latencia On-Edge (Hermes):
Mide la latencia de inferencia en milisugundos para MobileNetV3 INT8 y U-Net Nano INT8,
validando el cumplimiento del SLA de hardware.

Resuelve las rutas de modelo mediante `src.inference.pipeline.resolve_model_path`, de modo
que el benchmark mide exactamente los mismos archivos que carga el pipeline en producción
(`mobilenetv3_age_int8.onnx` / `unet_nano_spots_int8.onnx`, con fallback a los alias
`*_int8.onnx` y a FP32), en lugar de asumir nombres fijos que no existen en el despliegue.

Uso:
    python scripts/benchmark_latency.py
    python scripts/benchmark_latency.py --models-dir /opt/derma-onedge/models --iterations 200
    python scripts/benchmark_latency.py --threads 1

Devuelve código de salida 1 si el P90 supera el SLA, para poder usarse como puerta de
verificación en CI o antes de un despliegue.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import onnxruntime as ort

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.config import MAX_THERMAL_SOC_CELSIUS  # noqa: E402
from src.inference.pipeline import resolve_model_path  # noqa: E402

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SLA_LATENCY_MS = 110.0

_TENSOR_DTYPES = {
    "tensor(float)": np.float32,
    "tensor(float16)": np.float16,
    "tensor(uint8)": np.uint8,
    "tensor(int8)": np.int8,
    "tensor(int32)": np.int32,
    "tensor(int64)": np.int64,
}


def read_soc_temperature_celsius() -> Optional[float]:
    """
    Temperatura del SoC en grados Celsius, o None si no es legible en esta plataforma.
    No debe lanzar excepciones: el benchmark funciona tambien fuera de Raspberry Pi.
    """
    try:
        out = subprocess.run(
            ["vcgencmd", "measure_temp"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()
        return float(out.split("=", 1)[1].strip().rstrip("'C").strip())
    except Exception:
        pass
    try:
        raw = Path("/sys/class/thermal/thermal_zone0/temp").read_text(encoding="utf-8")
        return float(raw.strip()) / 1000.0
    except Exception:
        return None


def describe_providers() -> str:
    """Describe los execution providers activos y advierte si no hay EP vectorial NEON."""
    available = ort.get_available_providers()
    vector_eps = [p for p in available if "xnnpack" in p.lower() or "neon" in p.lower()]
    lines = [f"Proveedores disponibles: {available}"]
    if vector_eps:
        lines.append(f"Aceleracion vectorial NEON activa: {vector_eps}")
    else:
        lines.append(
            "Aviso: no hay execution provider vectorial (XNNPACK/NEON). "
            "El CPUExecutionProvider ya vectoriza con NEON via MLAS, pero la fusion de "
            "operadores queda limitada."
        )
    return "\n".join(lines)


def build_session(model_path: Path, threads: int) -> ort.InferenceSession:
    sess_options = ort.SessionOptions()
    sess_options.intra_op_num_threads = threads
    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return ort.InferenceSession(str(model_path), sess_options)


MAX_DUMMY_INPUT_MB = 64


def make_dummy_input(session: ort.InferenceSession) -> np.ndarray:
    """
    Crea una entrada de prueba respetando el dtype y las dimensiones reales del modelo.

    Las dimensiones simbolicas de ONNX Runtime (por ejemplo 'batch_size') se resuelven a 1:
    asumir un valor grande por defecto multiplicaria el tensor y terminaria en un OOM del
    dispositivo, porque las activaciones intermedias escalan con el tamano de lote.
    """
    meta = session.get_inputs()[0]
    dtype = _TENSOR_DTYPES.get(meta.type, np.float32)

    dims = []
    for dim in meta.shape:
        # Solo se respetan dimensiones enteras positivas y explicitas; el resto (simbolicas
        # o negativas) colapsa a 1, que es el lote minimo valido para el pipeline.
        dims.append(dim if isinstance(dim, int) and dim > 0 else 1)

    if not dims:
        raise ValueError(f"El modelo '{meta.name}' no declara forma de entrada utilizable.")

    total_mb = (int(np.prod(dims)) * np.dtype(dtype).itemsize) / (1024 * 1024)
    if total_mb > MAX_DUMMY_INPUT_MB:
        raise ValueError(
            f"La entrada de prueba seria de {total_mb:.1f} MB para la forma {tuple(dims)} "
            f"({meta.type}), por encima del limite de {MAX_DUMMY_INPUT_MB} MB. "
            "Revisa las dimensiones declaradas por el modelo antes de medir."
        )

    if dtype in (np.uint8, np.int8):
        return (np.random.rand(*dims) * 255).astype(dtype)
    return np.random.rand(*dims).astype(dtype)


def stats(samples) -> Dict[str, float]:
    return {
        "media": float(np.mean(samples)),
        "p50": float(np.percentile(samples, 50)),
        "p90": float(np.percentile(samples, 90)),
        "p99": float(np.percentile(samples, 99)),
        "max": float(np.max(samples)),
        "min": float(np.min(samples)),
    }


def _row(label: str, s: Dict[str, float]) -> str:
    return (f"| {label:<25} | {s['media']:<10.2f} | {s['p50']:<10.2f} | "
            f"{s['p90']:<10.2f} | {s['p99']:.2f}")


def run_benchmark(
    models_dir: Path,
    num_iterations: int = 100,
    threads: int = 4,
    sla_ms: float = SLA_LATENCY_MS,
) -> bool:
    age_path, age_precision = resolve_model_path("age", models_dir=models_dir)
    spot_path, spot_precision = resolve_model_path("spot", models_dir=models_dir)

    print("=" * 78)
    print("BENCHMARK DE LATENCIA ON-EDGE (Hermes INT8 ONNX)")
    print(f"    Modelos  : {models_dir}")
    print(f"    Threads  : {threads}   Iteraciones: {num_iterations}   SLA P90: {sla_ms:.0f} ms")
    print("=" * 78)
    print(f"    Edad  -> {age_path.name} [{age_precision}]")
    print(f"    Manchas -> {spot_path.name} [{spot_precision}]")
    print(f"    SoC antes: {_fmt_temp(read_soc_temperature_celsius())}")
    print(describe_providers())
    print("-" * 78)

    missing = [p for p in (age_path, spot_path) if not p.exists()]
    if missing:
        for p in missing:
            print(f"ERROR: modelo no encontrado: {p}")
        print("       Revisa el despliegue o indica --models-dir con el directorio correcto.")
        return False

    try:
        age_sess = build_session(age_path, threads)
        spot_sess = build_session(spot_path, threads)
    except Exception as exc:
        print(f"ERROR: no se pudo cargar el modelo: {exc}")
        return False

    age_in = age_sess.get_inputs()[0].name
    spot_in = spot_sess.get_inputs()[0].name
    try:
        age_input = make_dummy_input(age_sess)
        spot_input = make_dummy_input(spot_sess)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return False

    print(f"    Entrada edad   : {age_sess.get_inputs()[0].type} {age_input.shape}")
    print(f"    Entrada manchas: {spot_sess.get_inputs()[0].type} {spot_input.shape}")

    print("Calentando motores de inferencia...")
    for _ in range(10):
        age_sess.run(None, {age_in: age_input})
        spot_sess.run(None, {spot_in: spot_input})

    age_times, spot_times, total_times = [], [], []
    print("Ejecutando mediciones...")
    for _ in range(num_iterations):
        t0 = time.perf_counter()
        age_sess.run(None, {age_in: age_input})
        t1 = time.perf_counter()
        spot_sess.run(None, {spot_in: spot_input})
        t2 = time.perf_counter()
        age_times.append((t1 - t0) * 1000.0)
        spot_times.append((t2 - t1) * 1000.0)
        total_times.append((t2 - t0) * 1000.0)

    s_age, s_spot, s_total = stats(age_times), stats(spot_times), stats(total_times)

    print()
    print(f"| {'MODULO':<25} | {'MEDIA (ms)':<10} | {'P50 (ms)':<10} | {'P90 (ms)':<10} | {'P99 (ms)'}")
    print("-" * 78)
    print(_row("MobileNetV3 (Edad)", s_age))
    print(_row("U-Net Nano (Manchas)", s_spot))
    print(_row("TOTAL PIPELINE IA", s_total))
    print("-" * 78)

    temp_after = read_soc_temperature_celsius()
    print(f"    SoC despues: {_fmt_temp(temp_after)}"
          f"   (limite de bloqueo: {MAX_THERMAL_SOC_CELSIUS:.1f} C)")

    compliant = s_total["p90"] <= sla_ms
    verdict = "CUMPLE SLA" if compliant else f"EXCEDE SLA en {s_total['p90'] / sla_ms - 1:+.0%}"
    print(f"\nResultado P90 vs SLA ({sla_ms:.0f} ms): {s_total['p90']:.2f} ms --> {verdict}")
    print("=" * 78)

    if temp_after is not None and temp_after > MAX_THERMAL_SOC_CELSIUS:
        print(f"PELIGRO TERMICO: SoC en {temp_after:.1f} C supera el limite; "
              "el diagnostico deberia bloquearse con HTTP 422.")
    if not compliant:
        print("Sugerencias: medir con la camara detenida para separar contencion, "
              "reducir iteraciones por lectura, o cuantizar mas aggressivamente.")
    return compliant


def _fmt_temp(value: Optional[float]) -> str:
    return "no disponible" if value is None else f"{value:.1f} C"


def main() -> int:
    from src.config import MODELS_DIR

    parser = argparse.ArgumentParser(description="Benchmark de latencia on-edge (SLA P90).")
    parser.add_argument("--models-dir", type=Path, default=MODELS_DIR,
                        help="Directorio que contiene los modelos ONNX.")
    parser.add_argument("--iterations", type=int, default=100, help="Numero de iteraciones.")
    parser.add_argument("--threads", type=int, default=4, help="Hilos intra-operador.")
    parser.add_argument("--sla-ms", type=float, default=SLA_LATENCY_MS, help="Limite de P90 en ms.")
    args = parser.parse_args()

    ok = run_benchmark(
        models_dir=args.models_dir,
        num_iterations=args.iterations,
        threads=args.threads,
        sla_ms=args.sla_ms,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
