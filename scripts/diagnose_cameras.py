"""
Diagnóstico Avanzado de Dispositivos de Cámara en Windows
Analiza hardware disponible mediante DirectShow y PnP, verificando índices y compatibilidad.
"""

import sys
import subprocess
from pathlib import Path
import cv2

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def get_windows_cameras():
    print("=" * 65)
    print("🔍 1. DISPOSITIVOS DE CÁMARA REGISTRADOS EN DIRECTSHOW / PNP")
    print("=" * 65)
    devices = []
    try:
        from pygrabber.dshow_graph import FilterGraph
        graph = FilterGraph()
        devices = graph.get_input_devices()
        print(f"DirectShow Input Filters ({len(devices)} encontrados):")
        for i, name in enumerate(devices):
            print(f"  [{i}] {name}")
    except Exception as e:
        print(f"  Aviso pygrabber: {e}")

    print("\nPnP Devices (Hardware):")
    cmd = (
        'Get-PnpDevice | '
        'Where-Object { $_.Class -in @("Camera", "Image") } | '
        'Select-Object FriendlyName, Status, InstanceId | Format-Table -AutoSize'
    )
    try:
        res = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True, timeout=10)
        print(res.stdout if res.stdout.strip() else "No se devolvieron cámaras mediante PnP.")
    except Exception as e:
        print(f"Error al consultar PnP: {e}")

    return devices


def test_dshow_cameras(devices):
    print("\n" + "=" * 65)
    print("📹 2. VERIFICACIÓN DE TRANSMISIÓN DE FOTOGRAMAS (cv2.CAP_DSHOW)")
    print("=" * 65)
    
    num_to_test = max(len(devices), 3)
    operational = []

    for idx in range(num_to_test):
        dev_label = devices[idx] if idx < len(devices) else f"Índice genérico #{idx}"
        print(f"\n--- Probando [{idx}]: {dev_label} ---")
        
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None and frame.size > 0:
                h, w, _ = frame.shape
                print(f"  ✅ OPERATIVA! Transmitiendo frames a resolución {w}x{h}")
                operational.append((idx, dev_label, f"{w}x{h}"))
            else:
                print(f"  ⚠️ Abierta pero no transmite fotogramas (read=False)")
            cap.release()
        else:
            print(f"  ❌ No disponible / Fallo de enlace DirectShow")

    print("\n" + "=" * 65)
    print("📊 RESUMEN FINAL")
    print("=" * 65)
    if operational:
        for idx, name, res in operational:
            print(f"  ⭐ [{idx}] {name} (Resolución: {res})")
        print("\nPara ejecutar la demo interactiva:")
        print(f"  .venv\\Scripts\\python demo_camara.py {operational[0][0]}")
    else:
        print("  ❌ No se detectó ninguna cámara transmitiendo fotogramas.")


if __name__ == "__main__":
    devs = get_windows_cameras()
    test_dshow_cameras(devs)
