"""
Hermes & Antigravity - Fine-Tuning de Alta Precisión para Estimación de Edad Biológica
=======================================================================================
Mejoras v2 (con Early Stopping):
1. EarlyStopping(patience=4, min_delta=0.05) sobre val_mae para evitar sobreajuste.
2. ReduceLROnPlateau(factor=0.5, patience=2) – reduce LR cuando el val_mae se estanca.
3. WeightedRandomSampler con potencia 0.5 para corregir sesgo demográfico UTKFace.
4. SmoothL1Loss(beta=0.4) – gradientes fuertes en errores de 0.5 a 1.5 años.
5. Generación automática del cache desde el dataset crudo si no existe.
6. Exportación INT8 ONNX a múltiples rutas compatibles con pipeline.py.
7. dynamo=False en torch.onnx.export para compatibilidad con quantize_dynamic.
"""

import sys
import time
import os
from pathlib import Path
from typing import Tuple, Optional

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
import torchvision.transforms.v2 as v2
import torchvision.models as models
from tqdm import tqdm
import onnxruntime as ort

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
CACHE_FILE = DATA_DIR / "utkface_cache_224.pt"
INITIAL_WEIGHTS = MODELS_DIR / "best_age_model.pth"
FINETUNED_WEIGHTS = MODELS_DIR / "best_age_model_finetuned.pth"

# Dataset raw en disco externo
DATASET_DIRS = [
    Path("/media/metrx/DITT 2025/Rostros/dataset"),
    DATA_DIR / "utkface",
]

# Rutas de exportación ONNX (múltiples para compatibilidad con pipeline.py)
ONNX_PATHS = [
    MODELS_DIR / "age_estimator.onnx",
    MODELS_DIR / "age_estimator_fp32.onnx",
]
INT8_ONNX_PATHS = [
    MODELS_DIR / "age_estimator_int8.onnx",
    MODELS_DIR / "mobilenetv3_age_int8.onnx",
]


# ─────────────────────────────────────────────────────────────────────────────
# Modelo
# ─────────────────────────────────────────────────────────────────────────────
class BoundedAgeEstimator(nn.Module):
    """MobileNetV3-Large con Regresión Continua Bounded [15.0, 90.0] años."""

    def __init__(self, pretrained: bool = False):
        super().__init__()
        weights = models.MobileNet_V3_Large_Weights.DEFAULT if pretrained else None
        backbone = models.mobilenet_v3_large(weights=weights)

        self.features = backbone.features
        self.avgpool = nn.AdaptiveAvgPool2d(1)

        self.register_buffer("mean", torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1))
        self.register_buffer("std", torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1))

        self.head = nn.Sequential(
            nn.Linear(960, 256),
            nn.Hardswish(),
            nn.Dropout(p=0.15),
            nn.Linear(256, 64),
            nn.Hardswish(),
            nn.Linear(64, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x_norm = (x - self.mean) / self.std
        feat = self.features(x_norm)
        pooled = self.avgpool(feat)
        flat = torch.flatten(pooled, 1)
        raw = self.head(flat)
        age = 15.0 + 75.0 * torch.sigmoid(raw)
        return age


# ─────────────────────────────────────────────────────────────────────────────
# Data Augmentation
# ─────────────────────────────────────────────────────────────────────────────
class CalibratedAugmenter(nn.Module):
    """Augmentación conservadora que no deforma la edad fisiológica percibida."""

    def __init__(self):
        super().__init__()
        self.transforms = v2.Compose([
            v2.RandomHorizontalFlip(p=0.5),
            v2.RandomResizedCrop(size=(224, 224), scale=(0.88, 1.0), ratio=(0.98, 1.02), antialias=True),
            v2.ColorJitter(brightness=0.10, contrast=0.10, saturation=0.08),
        ])

    def forward(self, imgs: torch.Tensor) -> torch.Tensor:
        return self.transforms(imgs)


# ─────────────────────────────────────────────────────────────────────────────
# Dataset
# ─────────────────────────────────────────────────────────────────────────────
class FastUTKFaceDataset(Dataset):
    def __init__(self, images_tensor: torch.Tensor, ages_tensor: torch.Tensor):
        self.images = images_tensor  # [N, 3, 224, 224] uint8
        self.ages = ages_tensor      # [N, 1] float32

    def __len__(self):
        return len(self.ages)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        return self.images[idx], self.ages[idx]


# ─────────────────────────────────────────────────────────────────────────────
# Early Stopping
# ─────────────────────────────────────────────────────────────────────────────
class EarlyStopping:
    """
    Detiene el entrenamiento cuando el val_mae deja de mejorar.
    patience: épocas de espera sin mejora antes de parar.
    min_delta: mejora mínima requerida para considerar progreso.
    """

    def __init__(self, patience: int = 4, min_delta: float = 0.05):
        self.patience = patience
        self.min_delta = min_delta
        self.best_score: Optional[float] = None
        self.counter = 0
        self.stop = False

    def __call__(self, val_mae: float) -> bool:
        score = -val_mae  # mayor score = mejor (invertimos MAE)
        if self.best_score is None:
            self.best_score = score
        elif score < self.best_score + self.min_delta:
            self.counter += 1
            if self.counter >= self.patience:
                self.stop = True
        else:
            self.best_score = score
            self.counter = 0
        return self.stop


# ─────────────────────────────────────────────────────────────────────────────
# Generación de Cache desde datos crudos
# ─────────────────────────────────────────────────────────────────────────────
def build_cache(data_dir: Path, cache_path: Path, image_size: int = 224, max_workers: int = 8):
    """
    Genera el cache tensor desde imágenes UTKFace.
    Formato nombre: AGE_GENDER_RACE_DATE.jpg
    """
    from PIL import Image
    from concurrent.futures import ThreadPoolExecutor
    import re

    print(f"  Construyendo cache desde: {data_dir}")
    extensions = {".jpg", ".jpeg", ".png"}
    all_files = []

    if data_dir.is_dir():
        # Buscar recursivamente (estructura: dataset/part1/part1/*.jpg)
        for path in sorted(data_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in extensions:
                all_files.append(path)

    if not all_files:
        raise FileNotFoundError(f"No se encontraron imágenes en {data_dir}")

    print(f"  Encontradas {len(all_files):,} imágenes. Procesando...")

    pattern = re.compile(r"^(\d+)_")

    def process_file(f: Path):
        m = pattern.match(f.name)
        if not m:
            return None
        age = int(m.group(1))
        if not (1 <= age <= 100):
            return None
        try:
            img = Image.open(f).convert("RGB").resize((image_size, image_size), Image.BILINEAR)
            arr = np.array(img, dtype=np.uint8)  # [H, W, 3]
            return arr, float(age)
        except Exception:
            return None

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for r in tqdm(ex.map(process_file, all_files), total=len(all_files), desc="Cargando imágenes"):
            if r is not None:
                results.append(r)

    images = np.stack([r[0] for r in results])  # [N, H, W, 3]
    ages = np.array([r[1] for r in results], dtype=np.float32)

    # Convertir a [N, 3, H, W] uint8
    images_t = torch.from_numpy(images).permute(0, 3, 1, 2)  # uint8
    ages_t = torch.from_numpy(ages).unsqueeze(1)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"images": images_t, "ages": ages_t}, str(cache_path))
    print(f"  ✓ Cache guardado: {cache_path.name} ({len(results):,} muestras válidas)")
    return images_t, ages_t


# ─────────────────────────────────────────────────────────────────────────────
# Exportación ONNX + INT8
# ─────────────────────────────────────────────────────────────────────────────
def export_all_onnx(weights_path: Path):
    """
    Exporta FP32 ONNX con PyTorch, luego cuantiza a INT8 con ORT quantize_dynamic.
    NOTA: NO usar torch.quantization.quantize_dynamic antes de exportar ONNX — genera
    operadores 'quantized::linear_dynamic' no soportados por el exportador ONNX.
    Flujo correcto: PyTorch FP32 → ONNX FP32 → ORT quantize_dynamic → ONNX INT8.
    """
    from onnxruntime.quantization import quantize_dynamic as ort_quantize_dynamic
    from onnxruntime.quantization import QuantType
    import warnings

    print(f"\n[5/5] Exportando modelos ONNX desde {weights_path.name}...")
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    model = BoundedAgeEstimator(pretrained=False).cpu()
    model.load_state_dict(torch.load(weights_path, map_location="cpu", weights_only=True))
    model.eval()

    dummy = torch.randn(1, 3, 224, 224, dtype=torch.float32)

    # ── FP32 ONNX (exportado directamente desde el modelo PyTorch FP32)
    for onnx_path in ONNX_PATHS:
        torch.onnx.export(
            model,
            dummy,
            str(onnx_path),
            export_params=True,
            opset_version=17,
            do_constant_folding=True,
            input_names=["input"],
            output_names=["age"],
            dynamic_axes={"input": {0: "batch_size"}, "age": {0: "batch_size"}},
            dynamo=False,
        )
        size_mb = onnx_path.stat().st_size / (1024 * 1024)
        print(f"  ✓ FP32 ONNX: {onnx_path.name} ({size_mb:.2f} MB)")

    # ── INT8 ONNX: cuantizar el FP32 ONNX con ORT (soporta todos los ops de MobileNetV3)
    fp32_src = ONNX_PATHS[0]
    for int8_path in INT8_ONNX_PATHS:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ort_quantize_dynamic(str(fp32_src), str(int8_path), weight_type=QuantType.QUInt8)
        size_mb = int8_path.stat().st_size / (1024 * 1024)
        print(f"  ✓ INT8 ONNX: {int8_path.name} ({size_mb:.2f} MB)")

    # ── Verificación runtime
    print("\n  Verificando ONNX Runtime...")
    test_input = np.random.rand(1, 3, 224, 224).astype(np.float32)
    for p in [*ONNX_PATHS, *INT8_ONNX_PATHS]:
        if p.exists():
            sess = ort.InferenceSession(str(p), providers=["CPUExecutionProvider"])
            out = sess.run(None, {"input": test_input})[0]
            print(f"  ✓ {p.name}: {float(np.squeeze(out)):.1f} años")


# ─────────────────────────────────────────────────────────────────────────────
# Fine-tuning Principal
# ─────────────────────────────────────────────────────────────────────────────
def run_finetuning(
    epochs: int = 30,
    batch_size: int = 64,
    lr_head: float = 1.2e-4,
    lr_backbone: float = 6e-6,
    val_split: float = 0.15,
    early_stopping_patience: int = 4,
    early_stopping_min_delta: float = 0.05,
    plateau_patience: int = 2,
    plateau_factor: float = 0.5,
):
    print("=" * 75)
    print("🎯 FINE-TUNING DE ALTA PRECISIÓN: ESTIMADOR DE EDAD BIOLÓGICA v2")
    print("   Mejoras: Early Stopping | ReduceLROnPlateau | WeightedSampler | SmoothL1")
    print(f"   Dispositivo: {'CUDA (' + torch.cuda.get_device_name(0) + ')' if torch.cuda.is_available() else 'CPU'}")
    print(f"   Épocas máx: {epochs} | Batch: {batch_size} | ES patience: {early_stopping_patience}")
    print("=" * 75)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Cargar / Generar cache
    print(f"\n[1/5] Preparando dataset...")
    if not CACHE_FILE.exists():
        print(f"  Cache no encontrado. Buscando dataset crudo...")
        raw_dir = None
        for candidate in DATASET_DIRS:
            if candidate.exists():
                raw_dir = candidate
                break
        if raw_dir is None:
            raise FileNotFoundError(
                f"No se encontró el dataset UTKFace en ninguna ubicación conocida: {DATASET_DIRS}"
            )
        images_all, ages_all = build_cache(raw_dir, CACHE_FILE)
    else:
        print(f"  Cargando cache existente {CACHE_FILE.name}...")
        cache_data = torch.load(CACHE_FILE, weights_only=False)
        images_all = cache_data["images"]
        ages_all = cache_data["ages"]

    total_samples = len(images_all)
    print(f"  ✓ {total_samples:,} muestras listas.")

    # ── Split reproducible
    generator = torch.Generator().manual_seed(42)
    indices = torch.randperm(total_samples, generator=generator)
    val_size = int(total_samples * val_split)
    train_indices = indices[val_size:]
    val_indices = indices[:val_size]

    # ── WeightedRandomSampler (Inverse Frequency raíz cuadrada)
    train_ages_int = ages_all[train_indices].numpy().flatten().clip(0, 100).astype(int)
    counts = np.bincount(train_ages_int, minlength=101)
    smoothed = np.maximum(counts, 1)
    weights_np = 1.0 / np.sqrt(smoothed[train_ages_int])
    sampler = WeightedRandomSampler(
        weights=torch.as_tensor(weights_np, dtype=torch.double),
        num_samples=len(train_indices),
        replacement=True,
        generator=torch.Generator().manual_seed(42),
    )

    train_ds = FastUTKFaceDataset(images_all[train_indices], ages_all[train_indices])
    val_ds   = FastUTKFaceDataset(images_all[val_indices],   ages_all[val_indices])

    train_loader = DataLoader(train_ds, batch_size=batch_size, sampler=sampler,
                              num_workers=4, pin_memory=True, drop_last=True)
    val_loader   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False,
                              num_workers=4, pin_memory=True)

    print(f"  ✓ Train: {len(train_ds):,} | Val: {len(val_ds):,} | Batches/época: {len(train_loader)}")

    # ── 2. Modelo
    print(f"\n[2/5] Cargando pesos base...")
    model = BoundedAgeEstimator(pretrained=False).to(device)
    if INITIAL_WEIGHTS.exists():
        model.load_state_dict(torch.load(INITIAL_WEIGHTS, map_location=device, weights_only=True))
        print(f"  ✓ Cargado: {INITIAL_WEIGHTS.name}")
    elif FINETUNED_WEIGHTS.exists():
        model.load_state_dict(torch.load(FINETUNED_WEIGHTS, map_location=device, weights_only=True))
        print(f"  ✓ Cargado checkpoint previo: {FINETUNED_WEIGHTS.name}")
    else:
        print("  ⚠️  Sin checkpoint previo → inicializando ImageNet pretrained")
        model = BoundedAgeEstimator(pretrained=True).to(device)

    augmenter = CalibratedAugmenter().to(device)

    # ── 3. Evaluación baseline
    print(f"\n[3/5] Evaluación baseline pre-finetune...")
    def evaluate(loader, mod):
        mod.eval()
        preds_all, targets_all = [], []
        with torch.no_grad():
            for imgs_u8, tgts in loader:
                imgs = imgs_u8.to(device, non_blocking=True).float().div_(255.0)
                p = mod(imgs).cpu().numpy().flatten()
                preds_all.extend(p)
                targets_all.extend(tgts.numpy().flatten())
        preds_all = np.array(preds_all)
        targets_all = np.array(targets_all)
        mae = float(np.mean(np.abs(preds_all - targets_all)))
        return mae, preds_all, targets_all

    baseline_mae, bp, bt = evaluate(val_loader, model)
    print(f"  • Baseline Val MAE: {baseline_mae:.2f} años")

    # ── 4. Entrenamiento con Early Stopping
    print(f"\n[4/5] Fine-Tuning (max {epochs} épocas, ES patience={early_stopping_patience})...")

    criterion  = nn.SmoothL1Loss(beta=0.4)
    optimizer  = torch.optim.AdamW([
        {"params": model.features.parameters(), "lr": lr_backbone, "weight_decay": 5e-5},
        {"params": model.head.parameters(),     "lr": lr_head,     "weight_decay": 5e-5},
    ])
    # ReduceLROnPlateau: reduce LR cuando val_mae se estanca
    plateau_sched = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=plateau_factor, patience=plateau_patience,
        min_lr=1e-7, verbose=True,
    )
    scaler = torch.amp.GradScaler("cuda", enabled=(device.type == "cuda"))

    early_stop = EarlyStopping(patience=early_stopping_patience, min_delta=early_stopping_min_delta)
    best_val_mae = float("inf")
    history = []

    for epoch in range(1, epochs + 1):
        t0 = time.perf_counter()
        model.train()
        train_mae_sum, num_train = 0.0, 0

        pbar = tqdm(train_loader, desc=f"Época {epoch:03d}/{epochs:03d}", leave=False)
        for imgs_u8, targets in pbar:
            imgs    = imgs_u8.to(device, non_blocking=True).float().div_(255.0)
            imgs    = augmenter(imgs)
            targets = targets.to(device, non_blocking=True)

            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
                pred = model(imgs)
                loss = criterion(pred, targets)

            scaler.scale(loss).backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=2.0)
            scaler.step(optimizer)
            scaler.update()

            bs = imgs.size(0)
            train_mae_sum += torch.abs(pred.detach() - targets).sum().item()
            num_train     += bs
            pbar.set_postfix({"loss": f"{loss.item():.3f}"})

        train_mae = train_mae_sum / num_train

        # Validación
        val_mae, vp, vt = evaluate(val_loader, model)

        # Métricas sub-grupos
        m18 = (vt >= 17.5) & (vt <= 18.5)
        mae_18 = float(np.mean(np.abs(vp[m18] - vt[m18]))) if m18.any() else 0.0
        m_young = (vt >= 18) & (vt <= 30)
        mae_young = float(np.mean(np.abs(vp[m_young] - vt[m_young]))) if m_young.any() else 0.0

        elapsed = time.perf_counter() - t0
        plateau_sched.step(val_mae)

        # Guardar best checkpoint
        is_best = val_mae < best_val_mae - early_stopping_min_delta
        marker  = " 🌟 NUEVO MEJOR" if is_best else ""
        if is_best:
            best_val_mae = val_mae
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            torch.save(model.state_dict(), str(FINETUNED_WEIGHTS))

        lr_now = optimizer.param_groups[1]["lr"]
        history.append({"epoch": epoch, "train_mae": train_mae, "val_mae": val_mae})
        print(
            f"  📊 E{epoch:03d} | Train {train_mae:.2f}a | Val {val_mae:.2f}a | "
            f"18yo {mae_18:.2f}a | 18-30 {mae_young:.2f}a | LR={lr_now:.2e} | {elapsed:.1f}s{marker}"
        )

        # Early stopping
        if early_stop(val_mae):
            print(f"\n  🛑 Early Stopping activado en época {epoch} "
                  f"(sin mejora por {early_stopping_patience} épocas)")
            break

    print("\n" + "=" * 75)
    print(f"✅ Fine-tuning completado. Mejor Val MAE: {best_val_mae:.2f} años")
    print(f"   Baseline: {baseline_mae:.2f} → Final: {best_val_mae:.2f} "
          f"(Δ = {baseline_mae - best_val_mae:+.2f} años)")
    print("=" * 75)

    # ── 5. Exportar ONNX
    if FINETUNED_WEIGHTS.exists():
        export_all_onnx(FINETUNED_WEIGHTS)
    else:
        print("  ⚠️  No se generó checkpoint finetuned (modelo no mejoró baseline)")


if __name__ == "__main__":
    run_finetuning(epochs=30)
