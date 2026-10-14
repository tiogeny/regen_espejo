---
name: onedge-hardware-optimizer
description: Procedimientos de optimización on-edge para Raspberry Pi 5 y sistemas embebidos, cuantización INT8 ONNX, memoria compartida POSIX y verificación de SLAs de latencia y temperatura.
---

# Skill: Optimización de Hardware y Despliegue On-Edge

Esta skill define la validación de rendimiento, latencia y telemetría térmica en hardware embebido.

## SLAs del Sistema (Embedded Raspberry Pi 5 / ARM Cortex-A76)

1. **Latencia Máxima de Inferencia**:
   - MobileNetV3 + U-Net Nano $\le 110\text{ ms}$.
   - Tiempo de ida y vuelta de API local (loopback) $\le 180\text{ ms}$.
2. **Límites Térmicos del SoC**:
   - Temperatura máxima de seguridad: $75.0^\circ\text{C}$.
   - Bloqueo preventivo obligatorio de diagnóstico si $T > 75.0^\circ\text{C}$ con código HTTP 422.
3. **Validación de Modelos Cuantizados INT8**:
   - `models/age_estimator_int8.onnx` (tamaño ~3.4 MB, reducción de ~73% de memoria vs FP32).
   - `models/spot_segmentation_int8.onnx` (tamaño ~50 KB).
   - Aceleración con OpenVINO / XNNPACK / CPUExecutionProvider.
4. **Cero Persistencia Biométrica en Disco (Zero-Disk)**:
   - Comunicación de imágenes mediante descriptores de memoria compartida POSIX (`/dev/shm`).
   - Cero escritura de imágenes de rostros en disco para garantizar cumplimiento GDPR / HIPAA.
