from src.domain.recommendations import recommend, localized_orientation
from src.inference.segmentation import localized_spot_percentage
import time
import uuid
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Header, HTTPException, status, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from src.config import MAX_THERMAL_SOC_CELSIUS, DB_PATH
from src.api.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    DatosResponse,
    ClinicaData,
    PrescripcionItem,
    MetadatosData,
)
from src.api.security import verify_device_token
from src.memory.shm_manager import map_shared_memory_buffer, InvalidSHMError
from src.inference.pipeline import inference_engine
from src.db.database import get_db, init_db
from src.db.repository import (
    get_severity_by_spot_pct,
    generate_deterministic_session_id,
    save_diagnostic_session,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialización de esquema y datos de catálogo en SQLite
    init_db()
    yield


app = FastAPI(
    title="Sistema Embebido de Diagnóstico Dermatoscópico Facial y Recomendación Fitoterapéutica",
    version="1.1.0",
    lifespan=lifespan,
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error_code" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail,
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": "HTTP_ERROR", "message": str(exc.detail)},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Verificar si el fallo se debe a telemetría térmica
    for error in exc.errors():
        loc = error.get("loc", ())
        if "thermal_soc_celsius" in loc:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "error_code": "THERMAL_THROTTLING_ACTIVE",
                    "message": "Temperatura SoC Broadcom > 75.0°C. Inferencia suspendida por seguridad térmica.",
                },
            )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error_code": "VALIDATION_ERROR", "message": str(exc.errors())},
    )


@app.post(
    "/api/v1/diagnostics/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_201_CREATED,
)
def analyze_diagnostic(
    request: AnalyzeRequest,
    authorization: str = Depends(verify_device_token),
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
):
    start_time = time.perf_counter()
    correlation_id = x_correlation_id or str(uuid.uuid4())

    # 1. Validación de Telemetría Térmica
    if request.telemetry.thermal_soc_celsius > MAX_THERMAL_SOC_CELSIUS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "THERMAL_THROTTLING_ACTIVE",
                "message": f"Temperatura SoC ({request.telemetry.thermal_soc_celsius}°C) supera el límite de 75.0°C.",
            },
        )

    # 2. Mapeo y Lectura Zero-Copy del buffer POSIX SHM
    try:
        with map_shared_memory_buffer(request.shm_descriptor) as tensor:
            # 3. Inferencia de Redes Neuronales en memoria volátil (Zero-Disk)
            age, spot_pct = inference_engine.run_inference(tensor)
            local_pct = None
            if request.selected_region is not None:
                try:
                    local_pct = localized_spot_percentage(
                        inference_engine.get_segmentation_mask(tensor),
                        **request.selected_region.model_dump())
                except ValueError as exc:
                    raise HTTPException(422, detail={"error_code": "INVALID_REGION", "message": str(exc)})

    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": "INFERENCE_UNAVAILABLE",
                    "message": "El motor de visión no está disponible. No se generó un diagnóstico."},
        )
    except InvalidSHMError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_SHM_DESCRIPTOR",
                "message": str(err),
            },
        )

    # 4. Transacción y Motor de Reglas en SQLite 3NF
    with get_db() as conn:
        severity_info = get_severity_by_spot_pct(conn, spot_pct)
        severity_id = severity_info["severidad_id"]
        severity_code = severity_info["codigo"]

        session_id = generate_deterministic_session_id(
            age=age,
            spot_pct=spot_pct,
            seed=correlation_id,
        )

        orientation = localized_orientation() if request.selected_region else recommend(conn, spot_pct, request.questionnaire)
        rules_rows = orientation.pop("prescripciones")
        rule_ids = [r["regla_id"] for r in rules_rows]
        prescriptions = [PrescripcionItem(**r) for r in rules_rows]

        execution_time_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        save_diagnostic_session(
            conn=conn,
            session_id=session_id,
            severity_id=severity_id,
            age=age,
            spot_pct=spot_pct,
            processing_time_ms=execution_time_ms,
            rule_ids=rule_ids,
        )

    return AnalyzeResponse(
        datos=DatosResponse(
            sesion_id=session_id,
            clinica=ClinicaData(
                edad_biologica_estimada=age,
                porcentaje_hiperpigmentacion=spot_pct,
                clasificacion_severidad=severity_code,
                porcentaje_hiperpigmentacion_zona=local_pct,
                zona_seleccionada=request.selected_region,
            ),
            prescripciones=prescriptions,
            orientacion=orientation,
        ),
        metadatos=MetadatosData(
            correlation_id=correlation_id,
            execution_time_ms=execution_time_ms,
        ),
    )
