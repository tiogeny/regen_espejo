from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from src.domain.recommendations import Questionnaire


class TelemetryData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stability_duration_ms: int = Field(..., ge=1500, description="Tiempo de estabilidad facial en ms (>=1500)")
    thermal_soc_celsius: float = Field(..., le=75.0, description="Temperatura de CPU SoC en °C (<=75.0)")


class SelectedRegion(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    radius: float = Field(ge=.01, le=.2)


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    shm_descriptor: str = Field(..., description="Identificador del buffer POSIX de memoria compartida (224x224x3)")
    telemetry: TelemetryData
    questionnaire: Optional[Questionnaire] = None
    selected_region: Optional[SelectedRegion] = None


class PrescripcionItem(BaseModel):
    condicion_objetivo: str
    especie: str
    nombre_comun: str
    precauciones: str
    explicacion: str = ""
    fuentes: List[str] = Field(default_factory=list)


class ClinicaData(BaseModel):
    edad_biologica_estimada: int
    porcentaje_hiperpigmentacion: float
    clasificacion_severidad: str
    porcentaje_hiperpigmentacion_zona: Optional[float] = None
    zona_seleccionada: Optional[SelectedRegion] = None


class DatosResponse(BaseModel):
    sesion_id: str
    clinica: ClinicaData
    prescripciones: List[PrescripcionItem]
    orientacion: dict = Field(default_factory=dict)


class MetadatosData(BaseModel):
    correlation_id: str
    execution_time_ms: float


class AnalyzeResponse(BaseModel):
    datos: DatosResponse
    metadatos: MetadatosData


class ErrorResponse(BaseModel):
    error_code: str
    message: str
