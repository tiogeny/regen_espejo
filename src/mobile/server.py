"""Servidor independiente del API de inferencia, dentro del proceso de cámara."""
import io
import json
import os
import secrets
import socket
import subprocess
import threading
import time
from copy import deepcopy
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse, Response
from pydantic import BaseModel, Field
from qrcode import QRCode

from src.mobile.diagnostic import project_diagnostic
from src.domain.recommendations import Questionnaire, recommend, localized_orientation
from src.db.database import get_db


def _get_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and ip != "127.0.0.1":
            return ip
    except Exception:
        pass
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip and ip != "127.0.0.1":
            return ip
    except Exception:
        pass
    return "127.0.0.1"


class ScanControl:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = "DESCONECTADO"
        self._heartbeat = 0.0
        self._pending = None
        self._revision = 0
        self._applied_revision = None
        self._samples = 0
        self._diagnostic = None
        self._diagnostic_key = None
        self._result = None
        self._touch = None
        self._preview = None
        self._preview_at = 0.0
        self._analysis_preview = None
        self._new_person = False

    def publish_analysis_preview(self, rgb, mask, region, analysis_id):
        from src.inference.region_analysis import encode_zone_preview
        jpeg = encode_zone_preview(rgb, mask, region)
        with self._lock:
            self._analysis_preview = (analysis_id, jpeg)

    def analysis_preview(self, analysis_id):
        with self._lock:
            if (self._state != 'DIAGNOSTICADO' or self._pending is not None
                    or time.monotonic() - self._heartbeat >= 10
                    or not self._diagnostic or not self._analysis_preview
                    or self._diagnostic['analysis_id'] != analysis_id
                    or self._analysis_preview[0] != analysis_id):
                raise HTTPException(409, 'La lectura ya no está disponible.')
            return self._analysis_preview[1]

    def publish_preview(self, frame, selector=None):
        """Espejo cuadrado en RAM, con coordenadas del mismo fotograma."""
        if time.monotonic() - self._preview_at < .05:
            return
        import cv2
        h, w = frame.shape[:2]
        side = min(h, w)
        left, top = (w - side) // 2, (h - side) // 2
        image = cv2.resize(frame[top:top + side, left:left + side], (720, 720))
        ok, jpeg = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if not ok:
            return
        headers = {}
        if selector is not None and selector.point is not None:
            headers = {'X-Zone-X': str((float(selector.point[0]) - left) / side),
                       'X-Zone-Y': str((float(selector.point[1]) - top) / side),
                       'X-Zone-Radius': str(float(selector.radius) / side)}
        with self._lock:
            self._preview = (jpeg.tobytes(), headers)
            self._preview_at = time.monotonic()

    def preview(self):
        with self._lock:
            if self._preview is None or time.monotonic() - self._preview_at > 3:
                raise HTTPException(503, 'Esperando cámara')
            return self._preview

    def publish(self, state, samples, result=None, session_id=None):
        with self._lock:
            self._state = state
            self._result = result if state == "DIAGNOSTICADO" else None
            self._samples = samples
            self._heartbeat = time.monotonic()
            key = (id(result), session_id, samples)
            if state != "DIAGNOSTICADO" or result is None:
                self._diagnostic = None
                self._diagnostic_key = None
                self._analysis_preview = None
            elif key != self._diagnostic_key:
                self._diagnostic = project_diagnostic(result, session_id, samples)
                self._diagnostic_key = key

    def snapshot(self):
        with self._lock:
            connected = self._state != "DESCONECTADO" and time.monotonic() - self._heartbeat < 10
            result = dict(connected=connected, state=self._state if connected else "DESCONECTADO",
                        samples=self._samples, revision=self._revision, applied_revision=self._applied_revision, pending=self._pending is not None,
                        diagnostic=deepcopy(self._diagnostic) if connected and self._state == "DIAGNOSTICADO" and self._pending is None else None)
            if self._touch is not None and connected:
                result["touch"] = deepcopy(self._touch)
            if result['diagnostic'] is not None:
                result['diagnostic']['zone_preview_available'] = bool(
                    self._analysis_preview and self._analysis_preview[0] == self._diagnostic['analysis_id'])
            return result

    def publish_touch(self, state, message, progress=0.0):
        with self._lock:
            self._touch = dict(state=state, message=message, progress=progress)


    def recommend_current(self, analysis_id, questionnaire, scope="zone", revision=None):
        with self._lock:
            if (self._state != "DIAGNOSTICADO" or self._pending is not None
                    or (revision is not None and revision != self._revision)
                    or time.monotonic() - self._heartbeat >= 10
                    or not self._result or not self._diagnostic
                    or self._diagnostic["analysis_id"] != analysis_id):
                raise HTTPException(409, "La lectura cambió. Actualiza y completa el cuestionario de la lectura actual.")
            data = self._result["datos"]
            with get_db() as conn:
                orientation = (localized_orientation() if scope == "zone" and data["clinica"].get("zona_seleccionada")
                               else recommend(conn, data["clinica"]["porcentaje_hiperpigmentacion"], questionnaire))
                orientation["alcance"] = "zona" if scope == "zone" and data["clinica"].get("zona_seleccionada") else "rostro_completo"
                prescriptions = orientation.pop("prescripciones")
                # Mantener el registro de reglas aplicado a la misma lectura.
                with conn:
                    conn.execute("DELETE FROM sesion_prescripciones WHERE sesion_id=?", (analysis_id,))
                    for item in prescriptions:
                        conn.execute("INSERT INTO sesion_prescripciones(sesion_id, regla_id) VALUES (?, ?)",
                                     (analysis_id, item["regla_id"]))
            data.update(prescripciones=prescriptions, orientacion=orientation)
            self._diagnostic = project_diagnostic(self._result, self._diagnostic["session_id"], self._samples)
            return deepcopy(self._diagnostic)

    def request_restart(self, revision, new_person=False):
        with self._lock:
            if self._state == "DESCONECTADO" or time.monotonic() - self._heartbeat >= 10:
                raise HTTPException(503, "La cámara no está disponible.")
            if revision != self._revision or self._pending is not None:
                raise HTTPException(409, "El estado cambió. Actualiza e inténtalo de nuevo.")
            if self._state == "ANALIZANDO":
                raise HTTPException(409, "Espera a que termine el análisis.")
            self._pending = time.monotonic()
            self._new_person = new_person
            self._analysis_preview = None

    def apply_pending(self, restart, new_person=None):
        with self._lock:
            if self._pending is None:
                return
            queued_at = self._pending
            self._pending = None
            if time.monotonic() - queued_at < 10:
                if self._new_person:
                    if new_person is None:
                        raise RuntimeError('La cámara debe proporcionar el cambio de persona')
                    new_person()
                else:
                    restart()
                self._new_person = False
                self._touch = None
                self._state = "BUSCANDO"
                self._applied_revision = self._revision
                self._revision += 1

    def invalidate(self):
        with self._lock:
            self._pending = None
            self._revision += 1

    def disconnect(self):
        with self._lock:
            self._state = "DESCONECTADO"
            self._result = None
            self._pending = None
            self._diagnostic = None
            self._diagnostic_key = None
            self._preview = None
            self._analysis_preview = None
            self._touch = None


class RestartRequest(BaseModel):
    revision: int = Field(ge=0)
    new_person: bool = False


class RecommendationRequest(BaseModel):
    analysis_id: str = Field(min_length=1)
    questionnaire: Questionnaire
    scope: Literal["zone", "face"] = "zone"
    revision: int | None = Field(default=None, ge=0)


class PowerRequest(BaseModel):
    confirm: bool = Field(default=False)


class PairingRequest(BaseModel):
    password: str = Field(min_length=1, max_length=16)


def create_mobile_app(control, token, listen_port: int = 8080):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    ACCESS_PASSWORD = "1234"

    @app.middleware("http")
    async def privacy_headers(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    def authorize(authorization: str = Header(default="")):
        if not secrets.compare_digest(authorization, f"Bearer {token}"):
            raise HTTPException(401, "Código de acceso incorrecto o vencido.")

    def local_display(request: Request):
        # Las imágenes quedan disponibles solo para el navegador del equipo.
        if request.client is None or request.client.host not in ('127.0.0.1', '::1'):
            raise HTTPException(403, 'El espejo está disponible solo en este equipo.')
        if request.url.hostname not in ('127.0.0.1', '::1', 'localhost'):
            raise HTTPException(403, 'Dirección local inválida.')
        origin = request.headers.get('origin')
        if origin and origin != str(request.base_url).rstrip('/'):
            raise HTTPException(403, 'Origen inválido.')

    @app.get('/mirror', include_in_schema=False)
    def mirror():
        return FileResponse(Path(__file__).with_name('mirror.html'))

    @app.get('/mirror.css', include_in_schema=False)
    def mirror_style():
        return FileResponse(Path(__file__).with_name('mirror.css'), media_type='text/css')

    @app.get('/mirror.js', include_in_schema=False)
    def mirror_script():
        return FileResponse(Path(__file__).with_name('mirror.js'), media_type='text/javascript')

    @app.get('/mirror/api/frame', dependencies=[Depends(local_display)])
    def mirror_frame():
        jpeg, headers = control.preview()
        return Response(jpeg, media_type='image/jpeg', headers=headers)

    @app.get('/mirror/api/status', dependencies=[Depends(local_display)])
    def mirror_status():
        return control.snapshot()

    @app.get('/mirror/api/analysis-frame', dependencies=[Depends(local_display)])
    def mirror_analysis_frame(analysis_id: str):
        return Response(control.analysis_preview(analysis_id), media_type='image/jpeg')

    @app.post('/mirror/api/recommendations', dependencies=[Depends(local_display)])
    def mirror_recommendations(body: RecommendationRequest):
        if body.revision is None:
            raise HTTPException(422, "La revisión de la lectura es obligatoria.")
        return control.recommend_current(body.analysis_id, body.questionnaire, body.scope, body.revision)

    @app.post('/mirror/api/restart', status_code=202, dependencies=[Depends(local_display)])
    def mirror_restart(body: RestartRequest):
        control.request_restart(body.revision, body.new_person)
        return {'accepted': True}

    @app.get("/", include_in_schema=False)
    def index(request: Request):
        local = request.client is not None and request.client.host in ('127.0.0.1', '::1')
        page = 'mirror.html' if local and os.getenv('DERMA_WEB', '1') == '1' else 'index.html'
        return FileResponse(Path(__file__).with_name(page))

    @app.get("/mobile.js", include_in_schema=False)
    def script():
        return FileResponse(Path(__file__).with_name("mobile.js"), media_type="text/javascript")

    @app.get("/mobile.css", include_in_schema=False)
    def style():
        return FileResponse(Path(__file__).with_name("mobile.css"), media_type="text/css")

    @app.get("/pairing/qr.png", include_in_schema=False)
    def pairing_qr(request: Request):
        host = request.headers.get("host") or f"127.0.0.1:{listen_port}"
        base_url = f"http://{host}"
        qr_url = f"{base_url}/?password={ACCESS_PASSWORD}"
        qr = QRCode(version=None, error_correction=0, box_size=4, border=2)
        qr.add_data(qr_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png", headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        })

    @app.post("/api/pair", status_code=200)
    def pair(body: PairingRequest):
        if secrets.compare_digest(body.password, ACCESS_PASSWORD):
            return {"token": token}
        raise HTTPException(401, "Contraseña incorrecta")

    @app.get("/api/status", dependencies=[Depends(authorize)])
    def status():
        return control.snapshot()

    @app.post("/api/recommendations", dependencies=[Depends(authorize)])
    def recommendations(body: RecommendationRequest):
        return control.recommend_current(body.analysis_id, body.questionnaire, body.scope)

    @app.post("/api/restart", status_code=202, dependencies=[Depends(authorize)])
    def restart(body: RestartRequest):
        control.request_restart(body.revision)
        return {"accepted": True}

    @app.post("/api/system/shutdown", status_code=202, dependencies=[Depends(authorize)])
    def shutdown(body: PowerRequest):
        if not body.confirm:
            raise HTTPException(400, "Se requiere confirmación para apagar el equipo.")
        def _do():
            time.sleep(1.5)
            subprocess.run(["sudo", "poweroff"], check=False)
        threading.Thread(target=_do, daemon=True).start()
        return {"accepted": True, "action": "shutdown"}

    @app.post("/api/system/reboot", status_code=202, dependencies=[Depends(authorize)])
    def reboot(body: PowerRequest):
        if not body.confirm:
            raise HTTPException(400, "Se requiere confirmación para reiniciar el equipo.")
        def _do():
            time.sleep(1.5)
            subprocess.run(["sudo", "reboot"], check=False)
        threading.Thread(target=_do, daemon=True).start()
        return {"accepted": True, "action": "reboot"}

    return app


def start_mobile_server(control, port):
    lan_ip = _get_lan_ip()
    token = f"{secrets.randbelow(10**6):06d}"
    base_url = f"http://{lan_ip}:{port}"

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", port))
        sock.listen(32)
        import uvicorn
        server = uvicorn.Server(
            uvicorn.Config(
                create_mobile_app(control, token, listen_port=port),
                access_log=False,
                log_level="warning",
            )
        )
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
    except BaseException:
        sock.close()
        raise

    try:
        info = {
            "url": base_url,
            "token": token,
            "ip": lan_ip,
            "port": port,
            "ts": time.time(),
        }
        Path("/tmp/derma_mobile_url.txt").write_text(f"{base_url}\nToken: {token}\n", encoding="utf-8")
        Path("/tmp/derma_mobile.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    except Exception:
        pass

    print(f"\nControl móvil: {base_url}")
    print(f"Código temporal: {token}")
    print("Conecta el celular a la misma red Wi-Fi de confianza.\n")
    return server, thread, sock, token, base_url
