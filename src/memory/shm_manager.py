import numpy as np
from multiprocessing import shared_memory
from typing import Tuple, Generator
from contextlib import contextmanager
from src.config import EXPECTED_BUFFER_SHAPE, EXPECTED_BUFFER_SIZE_BYTES, EXPECTED_BUFFER_DTYPE


class InvalidSHMError(Exception):
    pass


@contextmanager
def map_shared_memory_buffer(
    shm_descriptor: str,
    expected_shape: Tuple[int, int, int] = EXPECTED_BUFFER_SHAPE,
    expected_dtype: str = EXPECTED_BUFFER_DTYPE
) -> Generator[np.ndarray, None, None]:
    shm = None
    try:
        shm = shared_memory.SharedMemory(name=shm_descriptor)
    except Exception as exc:
        raise InvalidSHMError(f"No se pudo acceder al descriptor SHM '{shm_descriptor}': {exc}") from exc

    try:
        # El buffer del sistema operativo (POSIX o Windows) puede redondearse al tamaño de página (4KB).
        # Debe contener al menos la cantidad requerida de bytes para el tensor (150,528 bytes).
        if shm.size < EXPECTED_BUFFER_SIZE_BYTES:
            raise InvalidSHMError(
                f"Tamaño de buffer SHM insuficiente: {shm.size} bytes (esperado al menos {EXPECTED_BUFFER_SIZE_BYTES} bytes)"
            )

        # Mapear exactamente los bytes correspondientes a la dimensión requerida en memoria volátil RAM
        raw_slice = shm.buf[:EXPECTED_BUFFER_SIZE_BYTES]
        tensor_view = np.ndarray(expected_shape, dtype=expected_dtype, buffer=raw_slice)
        if tensor_view.shape != expected_shape:
            raise InvalidSHMError(
                f"Shape de matriz SHM incorrecto: {tensor_view.shape} (esperado {expected_shape})"
            )

        # Extraer array en RAM y liberar puntero de buffer para permitir el cierre limpio de SHM
        tensor = tensor_view.copy()
        del tensor_view
        del raw_slice

        yield tensor
    finally:
        if shm is not None:
            try:
                shm.close()
            except Exception:
                pass
