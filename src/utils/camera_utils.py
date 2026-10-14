"""
Módulo de Gestión y Acceso a Dispositivos Ópticos de Captura (Cámara Web / V4L2 / DirectShow).

Optimizado para:
- Linux / Raspberry Pi OS: backend cv2.CAP_V4L2 con códec hardware FourCC 'MJPG'
  para descompresión acelerada y mínima saturación del bus USB / CSI.
- Windows: backend cv2.CAP_DSHOW (DirectShow) para acceso de bajo nivel sin latencias WMF.
"""

import sys
from typing import Optional
import cv2


def get_preferred_camera_backend() -> int:
    """
    Retorna el backend de captura de OpenCV recomendado según la plataforma.
    - Linux / Raspberry Pi OS: cv2.CAP_V4L2
    - Windows: cv2.CAP_DSHOW
    - Otros sistemas (macOS, BSD): cv2.CAP_ANY
    """
    if sys.platform.startswith("linux"):
        return cv2.CAP_V4L2
    if sys.platform.startswith("win"):
        return cv2.CAP_DSHOW
    return cv2.CAP_ANY


def get_camera_capture(
    camera_index: int = 0,
    width: Optional[int] = None,
    height: Optional[int] = None,
    fps: Optional[int] = None,
) -> cv2.VideoCapture:
    """
    Inicializa y configura un objeto cv2.VideoCapture optimizado según la plataforma operativa.

    En Linux / Raspberry Pi:
        - Abre la cámara utilizando backend `cv2.CAP_V4L2`.
        - Configura FourCC en `MJPG` (`cv2.VideoWriter_fourcc(*'MJPG')`).
    En Windows:
        - Abre la cámara utilizando backend `cv2.CAP_DSHOW`.
    En otras plataformas:
        - Abre la cámara utilizando backend `cv2.CAP_ANY`.

    Args:
        camera_index: Índice numérico del dispositivo de captura (por defecto 0).
        width: Ancho opcional del fotograma (ej. 1280).
        height: Alto opcional del fotograma (ej. 720).
        fps: Tasa de fotogramas por segundo deseada (ej. 30).

    Returns:
        cv2.VideoCapture: Instancia configurada de captura de vídeo de OpenCV.
    """
    backend = get_preferred_camera_backend()
    cap = cv2.VideoCapture(camera_index, backend)

    # Configuración específica para plataformas Linux / Raspberry Pi con V4L2
    if sys.platform.startswith("linux"):
        fourcc_mjpg = cv2.VideoWriter_fourcc(*"MJPG")
        cap.set(cv2.CAP_PROP_FOURCC, float(fourcc_mjpg))

    if width is not None:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(width))
    if height is not None:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(height))
    if fps is not None:
        cap.set(cv2.CAP_PROP_FPS, float(fps))

    return cap
