"""
Hermes ML Training Pipeline: Regresión de Edad Cutánea y Biológica con MobileNetV3-Small.
Dataset: UTKFace (D:\\Rostros)
Aceleración: NVIDIA CUDA (Quadro RTX 4000) + NVMe Cache + Bias Initialization a Media Poblacional
Exportación: ONNX INT8 para Inferencia On-Edge en Raspberry Pi 5 / PC Local.
"""

import os
import sys
import glob
import time
import argparse
from pathlib import Path
from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
from PIL import Image
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as T
import torchvision.models as models
from tqdm import tqdm

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
DATA_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = DATA_DIR / "utkface_cache_224.pt"


# =====================================================================
# 1. Dataset UTKFace con Caching NVMe / RAM
# =====================================================================
def load_single_image(path: str) -> Tuple[np.ndarray, float]:
    """Carga y redimensiona una imagen a 224x224 uint8 RGB."""
    fname = os.path.basename(path)
    age = float(fname.split("_")[0])
    with Image.open(path) as img:
        img_resized = img.convert("RGB").resize((224, 224), Image.Resampling.BILINEAR)
        arr = np.array(img_resized, dtype=np.uint8)
    return arr, age


class RamCachedUTKFaceDataset(Dataset):
    """
    Dataset con tensores uint8 en memoria RAM. Cero acceso a disco mecánico.
    """
    def __init__(self, images_tensor: torch.Tensor, ages_tensor: torch.Tensor, is_train: bool = True):
        self.images = images_tensor  # [N, 3, 224, 224] uint8
        self.ages = ages_tensor      # [N, 1] float32
        self.is_train = is_train

        self.jitter = T.ColorJitter(brightness=0.15, contrast=0.15, saturation=0.1)

    def __len__(self):
        return len(self.ages)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        img = self.images[idx].float().div_(255.0)
        age = self.ages[idx]

        if self.is_train:
            # Data Augmentation dinámico en CPU
            if torch.rand(1).item() > 0.5:
                img = torch.flip(img, dims=[2])
            angle = (torch.rand(1).item() - 0.5) * 16.0
            if abs(angle) > 2.0:
                img = T.functional.rotate(img, angle)
            img = self.jitter(img)

        return img, age


def collect_utkface_samples(root_dir: str) -> List[str]:
    """Escanea recursivamente las carpetas y valida nomenclatura."""
    pattern = os.path.join(root_dir, "**", "*.jpg")
    candidates = glob.glob(pattern, recursive=True)
    valid_paths = []
    
    for p in candidates:
        fname = os.path.basename(p)
        parts = fname.split("_")
        if len(parts) >= 4:
            try:
                age = int(parts[0])
                if 1 <= age <= 116:
                    valid_paths.append(p)
            except ValueError:
                continue
                
    return valid_paths


def get_cached_dataset(data_dir: str, cache_path: Path, max_workers: int = 16) -> Tuple[torch.Tensor, torch.Tensor]:
    """Carga desde caché en SSD NVMe si existe, o precarga desde el dataset en HDD."""
    if cache_path.exists():
        print(f"  Cargando dataset preprocesado desde caché NVMe: {cache_path.name}...")
        t0 = time.perf_counter()
        data = torch.load(cache_path, weights_only=True)
        images_tensor = data["images"]
        ages_tensor = data["ages"]
        elapsed = time.perf_counter() - t0
        print(f"  ✓ {len(images_tensor)} muestras cargadas en {elapsed:.2f}s desde NVMe")
        return images_tensor, ages_tensor

    sample_paths = collect_utkface_samples(data_dir)
    total = len(sample_paths)
    print(f"  Precargando {total} imágenes a RAM con {max_workers} hilos paralelos...")
    t0 = time.perf_counter()

    images_np = np.empty((total, 3, 224, 224), dtype=np.uint8)
    ages_np = np.empty((total, 1), dtype=np.float32)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for idx, (arr, age) in enumerate(tqdm(executor.map(load_single_image, sample_paths), total=total, desc="  RAM Cache")):
            images_np[idx] = np.transpose(arr, (2, 0, 1))
            ages_np[idx, 0] = age

    elapsed = time.perf_counter() - t0
    print(f"  ✓ {total} imágenes procesadas en {elapsed:.1f}s")

    images_tensor = torch.from_numpy(images_np)
    ages_tensor = torch.from_numpy(ages_np)

    # Guardar en SSD para arranques instantáneos futuros
    print(f"  Guardando caché optimizada en SSD NVMe: {cache_path.name}...")
    torch.save({"images": images_tensor, "ages": ages_tensor}, cache_path)
    print("  ✓ Caché persistida con éxito.")

    return images_tensor, ages_tensor


# =====================================================================
# 2. Arquitectura de Regresión de Edad (MobileNetV3-Small)
# =====================================================================
class AgeEstimatorMobileNet(nn.Module):
    """
    MobileNetV3-Small para regresión continua de edad.
    Entrada: [B, 3, 224, 224] float32 en rango [0.0, 1.0].
    Inicialización de bias a 33.0 (media del dataset) para convergencia instantánea.
    """
    def __init__(self, pretrained: bool = True):
        super().__init__()
        weights = models.MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        backbone = models.mobilenet_v3_small(weights=weights)
        
        self.features = backbone.features
        self.avgpool = nn.AdaptiveAvgPool2d(1)
        
        # Buffers fijos para normalización ImageNet (fusionados en ONNX)
        self.register_buffer("mean", torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1))
        self.register_buffer("std", torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1))
        
        # Cabeza de regresión
        self.regressor = nn.Sequential(
            nn.Linear(576, 128),
            nn.Hardswish(),
            nn.Dropout(p=0.2),
            nn.Linear(128, 1),
        )

        # Inicialización matemática óptima: bias a la media poblacional (33.0 años)
        nn.init.normal_(self.regressor[0].weight, std=0.01)
        nn.init.zeros_(self.regressor[0].bias)
        nn.init.normal_(self.regressor[3].weight, std=0.01)
        nn.init.constant_(self.regressor[3].bias, 33.0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [B, 3, 224, 224] float32 en [0, 1]
        x_norm = (x - self.mean) / self.std
        feat = self.features(x_norm)
        pooled = self.avgpool(feat)
        flat = torch.flatten(pooled, 1)
        age = self.regressor(flat)
        return age


# =====================================================================
# 3. Pipeline de Entrenamiento y Validación
# =====================================================================
def train_epoch(model, loader, criterion, optimizer, device):
    model.train()
    total_loss = 0.0
    total_mae = 0.0
    num_samples = 0

    pbar = tqdm(loader, desc="  Train", leave=False)
    for images, targets in pbar:
        images = images.to(device, non_blocking=True)
        targets = targets.to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)
        preds = model(images)
        loss = criterion(preds, targets)
        loss.backward()
        optimizer.step()

        batch_size = images.size(0)
        mae = torch.mean(torch.abs(preds - targets)).item() * batch_size

        total_loss += loss.item() * batch_size
        total_mae += mae
        num_samples += batch_size

        pbar.set_postfix(loss=f"{loss.item():.2f}", mae=f"{mae / batch_size:.2f}a")

    return total_loss / num_samples, total_mae / num_samples


@torch.no_grad()
def evaluate(model, loader, criterion, device):
    model.eval()
    total_loss = 0.0
    total_mae = 0.0
    num_samples = 0

    for images, targets in tqdm(loader, desc="  Val  ", leave=False):
        images = images.to(device, non_blocking=True)
        targets = targets.to(device, non_blocking=True)

        preds = model(images)
        loss = criterion(preds, targets)

        batch_size = images.size(0)
        mae = torch.mean(torch.abs(preds - targets)).item() * batch_size

        total_loss += loss.item() * batch_size
        total_mae += mae
        num_samples += batch_size

    return total_loss / num_samples, total_mae / num_samples


# =====================================================================
# 4. Exportación y Cuantización ONNX
# =====================================================================
def export_to_onnx(model, output_dir: Path):
    print("\n" + "=" * 60)
    print("🚀 HERMES ML: Exportación y Cuantización ONNX INT8")
    print("=" * 60)

    model.eval()
    model_cpu = model.to("cpu")
    dummy_input = torch.randn(1, 3, 224, 224, dtype=torch.float32)

    fp32_path = output_dir / "age_estimator_fp32.onnx"
    int8_path = output_dir / "age_estimator.onnx"

    print(f"\n[1/3] Exportando grafo ONNX FP32 -> {fp32_path.name}...")
    torch.onnx.export(
        model_cpu,
        dummy_input,
        str(fp32_path),
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["age"],
        dynamic_axes={"input": {0: "batch_size"}, "age": {0: "batch_size"}},
    )
    fp32_size_mb = fp32_path.stat().st_size / (1024 * 1024)
    print(f"  ✓ Grafo FP32 exportado: {fp32_size_mb:.2f} MB")

    print(f"\n[2/3] Cuantización dinámica simétrica INT8 -> {int8_path.name}...")
    from onnxruntime.quantization import quantize_dynamic, QuantType
    quantize_dynamic(
        model_input=str(fp32_path),
        model_output=str(int8_path),
        weight_type=QuantType.QInt8,
    )
    int8_size_mb = int8_path.stat().st_size / (1024 * 1024)
    print(f"  ✓ Modelo cuantizado INT8: {int8_size_mb:.2f} MB (reducción ~{100*(1 - int8_size_mb/fp32_size_mb):.1f}%)")

    print("\n[3/3] Validando inferencia con ONNX Runtime...")
    import onnxruntime as ort
    session = ort.InferenceSession(str(int8_path))
    inp_name = session.get_inputs()[0].name
    test_tensor = np.random.uniform(0.0, 1.0, (1, 3, 224, 224)).astype(np.float32)

    times = []
    for _ in range(15):
        t0 = time.perf_counter()
        out = session.run(None, {inp_name: test_tensor})
        times.append((time.perf_counter() - t0) * 1000)

    avg_lat = np.mean(times[5:])
    pred_age = float(np.squeeze(out[0]))
    print(f"  ✓ Inferencia verificada: Predicción={pred_age:.1f} años, Latencia={avg_lat:.2f} ms")


# =====================================================================
# 5. Punto de Entrada Principal
# =====================================================================
def main():
    parser = argparse.ArgumentParser(description="Entrenamiento de MobileNetV3 con RAM/NVMe Cache")
    parser.add_argument("--data_dir", type=str, default=r"D:\Rostros", help="Ruta al dataset UTKFace")
    parser.add_argument("--epochs", type=int, default=10, help="Número de épocas de entrenamiento")
    parser.add_argument("--batch_size", type=int, default=64, help="Tamaño del batch")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate inicial")
    parser.add_argument("--val_split", type=float, default=0.15, help="Proporción para validación")
    parser.add_argument("--export_onnx", action="store_true", default=True, help="Exportar a ONNX al finalizar")
    args = parser.parse_args()

    print("=" * 60)
    print("🧠 HERMES ML TRAINING: Estimador de Edad Biológica (Prior-Informed)")
    print("=" * 60)

    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        device = torch.device("cuda")
        print(f"Hardware Acelerador: CUDA ({torch.cuda.get_device_name(0)})")
    else:
        device = torch.device("cpu")
        print("Hardware Acelerador: CPU")

    # 1. Carga o Precarga con Caché NVMe
    print(f"\n[1/5] Cargando dataset...")
    images_all, ages_all = get_cached_dataset(args.data_dir, CACHE_FILE, max_workers=16)
    total_samples = len(images_all)

    # 2. Split Train / Validation
    val_size = int(total_samples * args.val_split)
    train_size = total_samples - val_size
    generator = torch.Generator().manual_seed(42)
    indices = torch.randperm(total_samples, generator=generator)

    train_indices = indices[:train_size]
    val_indices = indices[train_size:]

    train_dataset = RamCachedUTKFaceDataset(images_all[train_indices], ages_all[train_indices], is_train=True)
    val_dataset = RamCachedUTKFaceDataset(images_all[val_indices], ages_all[val_indices], is_train=False)

    print(f"  ✓ Conjunto Train: {len(train_dataset)} muestras")
    print(f"  ✓ Conjunto Val:   {len(val_dataset)} muestras")

    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=False,
        drop_last=True,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=False,
    )

    # 3. Inicializar Modelo, Pérdida y Optimizador
    print("\n[2/5] Inicializando MobileNetV3-Small con pesos preentrenados y bias=33.0...")
    model = AgeEstimatorMobileNet(pretrained=True).to(device)

    # Pérdida L1 Loss directa para minimizar MAE en años
    criterion = nn.L1Loss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-5)

    # 4. Bucle de Entrenamiento
    print(f"\n[3/5] Iniciando entrenamiento por {args.epochs} épocas...")
    best_mae = float("inf")
    best_weights_path = MODELS_DIR / "best_age_model.pth"

    for epoch in range(1, args.epochs + 1):
        t_start = time.perf_counter()
        train_loss, train_mae = train_epoch(model, train_loader, criterion, optimizer, device)
        val_loss, val_mae = evaluate(model, val_loader, criterion, device)
        scheduler.step()
        epoch_sec = time.perf_counter() - t_start

        is_best = val_mae < best_mae
        marker = " [BEST]" if is_best else ""
        if is_best:
            best_mae = val_mae
            torch.save(model.state_dict(), best_weights_path)

        lr_curr = optimizer.param_groups[0]["lr"]
        print(
            f"Epoca [{epoch:02d}/{args.epochs:02d}] "
            f"Train Loss: {train_loss:.2f} | Train MAE: {train_mae:.2f}a | "
            f"Val Loss: {val_loss:.2f} | Val MAE: {val_mae:.2f}a | "
            f"LR: {lr_curr:.1e} | Tiempo: {epoch_sec:.1f}s{marker}"
        )

    print(f"\n[4/5] Entrenamiento finalizado. Mejor MAE en Validación: {best_mae:.2f} años")

    # 5. Cargar mejores pesos y exportar a ONNX
    if args.export_onnx:
        print(f"\n[5/5] Cargando mejor modelo ({best_weights_path.name}) para exportar a ONNX...")
        model.load_state_dict(torch.load(best_weights_path, map_location="cpu"))
        export_to_onnx(model, MODELS_DIR)

    print("\n✅ Pipeline de entrenamiento de edad completado con éxito!")


if __name__ == "__main__":
    main()
