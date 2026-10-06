import { useState, useEffect, type RefObject } from 'react';

export function useWebcam(videoRef: RefObject<HTMLVideoElement | null>, enabled: boolean) {
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isActive, setIsActive] = useState(false);

  useEffect(() => {
    let currentStream: MediaStream | null = null;

    if (enabled) {
      navigator.mediaDevices
        ?.getUserMedia({
          video: {
            width: { ideal: 1280 },
            height: { ideal: 720 },
            facingMode: 'user',
          },
          audio: false,
        })
        .then((s) => {
          currentStream = s;
          setStream(s);
          setIsActive(true);
          setError(null);
          if (videoRef.current) {
            videoRef.current.srcObject = s;
          }
        })
        .catch((err) => {
          console.warn('Cámara web no disponible o permiso denegado:', err);
          setError('No se pudo acceder a la cámara. Usando modo simulación.');
          setIsActive(false);
        });
    } else {
      setIsActive(false);
      if (videoRef.current) {
        videoRef.current.srcObject = null;
      }
    }

    return () => {
      if (currentStream) {
        currentStream.getTracks().forEach((track) => track.stop());
      }
    };
  }, [enabled, videoRef]);

  return { stream, isActive, error };
}
