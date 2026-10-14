import os
from pathlib import Path
from typing import Optional
from fastapi import Header, HTTPException, status
from src.config import get_token_path, DEV_TOKEN


def get_current_device_token() -> str:
    token_file = Path(get_token_path())
    if token_file.exists():
        try:
            token = token_file.read_text(encoding="utf-8").strip()
            if token:
                return token
        except Exception:
            pass
    return os.getenv("DERMA_DEVICE_TOKEN", DEV_TOKEN)


def verify_device_token(authorization: Optional[str] = Header(None)) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "INVALID_DEVICE_TOKEN", "message": "Cabecera Authorization ausente."},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "INVALID_DEVICE_TOKEN", "message": "Formato de token Bearer inválido."},
        )

    provided_token = parts[1]
    expected_token = get_current_device_token()

    if provided_token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "INVALID_DEVICE_TOKEN", "message": "Token no coincide con el secreto en tmpfs."},
        )

    return provided_token
