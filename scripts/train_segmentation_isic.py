"""
Hermes & Antigravity ML Training Pipeline v2:
Segmentación de Manchas e Hiperpigmentación Cutánea con U-Net Nano + ISIC 2024.

Mejoras v2:
- Rutas Linux correctas (se detectan automáticamente)
- Early Stopping (patience=5, min_delta=0.002 Dice)
- ReduceLROnPlateau (factor=0.5, patience=2)
- Carga paralela con num_workers=4
- Export ONNX con dynamo=False + ORT quantize_dynamic (flujo correcto)
- Soporte tanto benignas como malignas (clasificador binario en máscara)
- Métricas adicionales: Precision, Recall por época

Dataset:
- ISIC 2024: 401,059 lesiones dermatoscópicas reales
- UTKFace cache 224: 24,106 rostros como fondos de composición

Arquitectura: SpotSegmenterUNetNano (Depthwise Separable Convolutions ARM NEON)
"""

import os
import sys
import csv
import time
import argparse
import random
import warnings
from pathlib import Path
from typing import List, Tuple, Optional

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from tqdm import tqdm

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
DATA_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# ── Rutas del dataset (Linux)
ISIC_CSV  = Path("/media/metrx/DITT 2025/Rostros/ISIC_2024_Training_Supplement.csv")
ISIC_DIR  = Path("/media/metrx/DITT 2025/Rostros/ISIC_2024_Training_Input")
FACES_CACHE = DATA_DIR / "utkface_cache_224.pt"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Arquitectura U-Net Nano
# ─────────────────────────────────────────────────────────────────────────────
class DSConvBlock(nn.Module):
    """
    Bloque Depthwise-Separable optimizado para ARM NEON y Edge AI.
    Reduce FLOPs ~88% frente a convolución estándar.
    """
    def __init__(self, in_c: int, out_c: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_c, in_c, kernel_size=3, padding=1, groups=in_c, bias=False),
            nn.BatchNorm2d(in_c),
            nn.ReLU(inplace=True),
            nn.Conv2d(in_c, out_c, kernel_size=1, bias=False),
            nn.BatchNorm2d(out_c),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(x)


class SpotSegmenterUNetNano(nn.Module):
    """
    U-Net Nano ultraligera para segmentación de manchas y lentigos solares.
    Entrada: [B, 3, 224, 224] → Salida: [B, 1, 224, 224] (sigmoid probabilities)
    ~180K parámetros / ~3 MB FP32 / <50 KB INT8
    """
    def __init__(self):
        super().__init__()
        self.init_conv = nn.Sequential(
            nn.Conv2d(3, 8, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(8),
            nn.ReLU(inplace=True),
        )
        self.enc1 = DSConvBlock(8, 12)
        self.pool1 = nn.MaxPool2d(2)   # 112x112

        self.enc2 = DSConvBlock(12, 24)
        self.pool2 = nn.MaxPool2d(2)   # 56x56

        self.enc3 = DSConvBlock(24, 48)
        self.pool3 = nn.MaxPool2d(2)   # 28x28

        self.bottleneck = DSConvBlock(48, 64)

        self.up3  = nn.Sequential(nn.Upsample(scale_factor=2, mode="nearest"),
                                   nn.Conv2d(64, 32, 1, bias=False))
        self.dec3 = DSConvBlock(32 + 48, 32)

        self.up2  = nn.Sequential(nn.Upsample(scale_factor=2, mode="nearest"),
                                   nn.Conv2d(32, 16, 1, bias=False))
        self.dec2 = DSConvBlock(16 + 24, 16)

        self.up1  = nn.Sequential(nn.Upsample(scale_factor=2, mode="nearest"),
                                   nn.Conv2d(16, 8, 1, bias=False))
        self.dec1 = DSConvBlock(8 + 12, 8)

        self.final_conv = nn.Conv2d(8, 1, kernel_size=1)

    def forward_logits(self, x: torch.Tensor) -> torch.Tensor:
        x0 = self.init_conv(x)
        e1 = self.enc1(x0)
        e2 = self.enc2(self.pool1(e1))
        e3 = self.enc3(self.pool2(e2))
        b  = self.bottleneck(self.pool3(e3))
        d3 = self.dec3(torch.cat([self.up3(b),  e3], dim=1))
        d2 = self.dec2(torch.cat([self.up2(d3), e2], dim=1))
        d1 = self.dec1(torch.cat([self.up1(d2), e1], dim=1))
        return self.final_conv(d1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(self.forward_logits(x))


# ─────────────────────────────────────────────────────────────────────────────
# 2. Pérdida Compuesta BCE + Dice
# ─────────────────────────────────────────────────────────────────────────────
class DiceLoss(nn.Module):
    def __init__(self, smooth: float = 1e-5):
        super().__init__()
        self.smooth = smooth

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        probs = torch.sigmoid(logits)
        pf = probs.view(-1)
        tf = targets.view(-1)
        intersection = (pf * tf).sum()
        return 1.0 - (2.0 * intersection + self.smooth) / (pf.sum() + tf.sum() + self.smooth)


class CombinedBCEDiceLoss(nn.Module):
    def __init__(self, bce_w: float = 0.4, dice_w: float = 0.6):
        super().__init__()
        self.bce_w  = bce_w
        self.dice_w = dice_w
        self.bce  = nn.BCEWithLogitsLoss()
        self.dice = DiceLoss()

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        return self.bce_w * self.bce(logits, targets) + self.dice_w * self.dice(logits, targets)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Early Stopping
# ─────────────────────────────────────────────────────────────────────────────
class EarlyStopping:
    """Detiene cuando val_dice deja de mejorar patience épocas."""
    def __init__(self, patience: int = 5, min_delta: float = 0.002):
        self.patience   = patience
        self.min_delta  = min_delta
        self.best_score: Optional[float] = None
        self.counter    = 0
        self.stop       = False

    def __call__(self, val_dice: float) -> bool:
        score = val_dice
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
# 4. Extracción de Máscara de Lesión ISIC
# ─────────────────────────────────────────────────────────────────────────────
def extract_isic_lesion_mask(img_rgb: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Segmenta la lesión pigmentada central en CIE-Lab + Otsu + morfología.
    Retorna (img_rgb, mask_binaria_uint8, ratio_cobertura%).
    """
    h, w = img_rgb.shape[:2]
    lab  = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2LAB)
    l_ch = lab[:, :, 0]

    pad_h = max(2, int(h * 0.12))
    pad_w = max(2, int(w * 0.12))
    border_mask = np.ones((h, w), dtype=bool)
    border_mask[pad_h:-pad_h, pad_w:-pad_w] = False

    skin_l = float(np.median(l_ch[border_mask])) if border_mask.any() else 128.0
    darkness = np.maximum(0.0, skin_l - l_ch.astype(np.float32))
    max_d = float(darkness.max())

    if max_d < 12.0:
        return img_rgb, np.zeros((h, w), dtype=np.uint8), 0.0

    d_u8 = np.clip(darkness * (255.0 / max_d), 0, 255).astype(np.uint8)
    _, thresh = cv2.threshold(d_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    cleaned = cv2.morphologyEx(cv2.morphologyEx(thresh, cv2.MORPH_OPEN, k), cv2.MORPH_CLOSE, k)

    cy, cx = h // 2, w // 2
    n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(cleaned)
    final_mask = np.zeros((h, w), dtype=np.uint8)
    best_dist, best_lbl = float("inf"), -1
    for lbl in range(1, n_labels):
        dist = (centroids[lbl][0] - cx) ** 2 + (centroids[lbl][1] - cy) ** 2
        if stats[lbl, cv2.CC_STAT_AREA] > 10 and dist < best_dist:
            best_dist, best_lbl = dist, lbl
    if best_lbl > 0:
        final_mask[labels == best_lbl] = 1

    return img_rgb, final_mask, float((final_mask > 0).mean() * 100.0)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Dataset Híbrido: Rostros UTKFace + Lesiones ISIC 2024
# ─────────────────────────────────────────────────────────────────────────────
class ISICDermaSegmentationDataset(Dataset):
    """
    Composición realista de lesiones ISIC 2024 sobre fondos de piel UTKFace.
    Distribución de severidad clínica:
      NINGUNA 20% / LEVE 30% / MODERADA 30% / ALTA 20%
    """
    def __init__(
        self,
        isic_paths: List[str],
        face_tensors: Optional[torch.Tensor] = None,
        num_samples: int = 10000,
        is_train: bool = True,
    ):
        self.isic_paths   = isic_paths
        self.face_tensors = face_tensors
        self.num_samples  = num_samples
        self.is_train     = is_train

    def __len__(self) -> int:
        return self.num_samples

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, float]:
        # Base de piel
        if self.face_tensors is not None and len(self.face_tensors) > 0:
            fi = random.randint(0, len(self.face_tensors) - 1)
            base_img = self.face_tensors[fi].permute(1, 2, 0).numpy().copy()
        else:
            v = random.randint(130, 210)
            base_img = np.full((224, 224, 3), v, dtype=np.uint8)

        gt_mask = np.zeros((224, 224), dtype=np.float32)

        # Número de máculas según severidad
        r = random.random()
        if r < 0.20:
            n_maculae = 0
        elif r < 0.50:
            n_maculae = random.randint(1, 2)
        elif r < 0.80:
            n_maculae = random.randint(2, 4)
        else:
            n_maculae = random.randint(4, 7)

        for _ in range(n_maculae):
            path = random.choice(self.isic_paths)
            img_bgr = cv2.imread(path)
            if img_bgr is None:
                continue
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            _, lesion_mask, coverage = extract_isic_lesion_mask(img_rgb)
            if coverage < 2.0:
                continue

            sz = random.randint(16, 54)
            l_res = cv2.resize(img_rgb,     (sz, sz), interpolation=cv2.INTER_AREA)
            m_res = cv2.resize(lesion_mask, (sz, sz), interpolation=cv2.INTER_NEAREST)

            px = random.randint(20, 224 - sz - 20)
            py = random.randint(20, 224 - sz - 20)

            m_soft = cv2.GaussianBlur(m_res.astype(np.float32), (3, 3), 0.8)
            roi    = base_img[py:py+sz, px:px+sz].astype(np.float32)
            alpha  = np.repeat(m_soft[:, :, None], 3, axis=2)
            blended = roi * (1.0 - alpha * 0.88) + l_res.astype(np.float32) * (alpha * 0.88)
            base_img[py:py+sz, px:px+sz] = np.clip(blended, 0, 255).astype(np.uint8)
            gt_mask[py:py+sz, px:px+sz]  = np.maximum(
                gt_mask[py:py+sz, px:px+sz], m_res.astype(np.float32)
            )

        if self.is_train:
            a = random.uniform(0.85, 1.15)
            b = random.randint(-15, 15)
            base_img = np.clip(base_img.astype(np.float32) * a + b, 0, 255).astype(np.uint8)
            if random.random() > 0.5:
                base_img = np.fliplr(base_img).copy()
                gt_mask  = np.fliplr(gt_mask).copy()
            if random.random() > 0.5:
                base_img = np.flipud(base_img).copy()
                gt_mask  = np.flipud(gt_mask).copy()
            # Rotación aleatoria leve
            angle = random.uniform(-15, 15)
            M = cv2.getRotationMatrix2D((112, 112), angle, 1.0)
            base_img = cv2.warpAffine(base_img, M, (224, 224))
            gt_mask  = cv2.warpAffine(gt_mask,  M, (224, 224))

        img_t  = torch.from_numpy(base_img).permute(2, 0, 1).float() / 255.0
        mask_t = torch.from_numpy(gt_mask).unsqueeze(0).float()
        spot_pct = float((gt_mask > 0.5).mean() * 100.0)
        return img_t, mask_t, spot_pct


# ─────────────────────────────────────────────────────────────────────────────
# 6. Carga de Metadatos ISIC 2024
# ─────────────────────────────────────────────────────────────────────────────
def load_isic_paths(
    csv_path: Path = ISIC_CSV,
    img_dir: Path  = ISIC_DIR,
    max_samples: int = 60000,
    include_malignant: bool = False,
) -> List[str]:
    """
    Carga rutas de imágenes ISIC filtrando por clase.
    Por defecto solo benignas para composición sobre rostros.
    """
    print(f"  Leyendo metadatos ISIC: {csv_path.name}...")
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV no encontrado: {csv_path}")
    if not img_dir.exists():
        raise FileNotFoundError(f"Directorio ISIC no encontrado: {img_dir}")

    valid, skipped = [], 0
    classes = {"benign"}
    if include_malignant:
        classes.add("malignant")

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cls = row.get("iddx_1", "").strip().lower()
            if cls not in classes:
                continue
            isic_id = row.get("isic_id", "").strip()
            if not isic_id:
                continue
            p = img_dir / f"{isic_id}.jpg"
            if p.exists():
                valid.append(str(p))
            else:
                skipped += 1
            if len(valid) >= max_samples:
                break

    print(f"  ✓ {len(valid):,} imágenes encontradas ({skipped:,} sin archivo en disco)")
    return valid


# ─────────────────────────────────────────────────────────────────────────────
# 7. Exportación ONNX FP32 + INT8
# ─────────────────────────────────────────────────────────────────────────────
def export_and_quantize_unet(checkpoint_path: Path):
    """
    PyTorch checkpoint → FP32 ONNX → INT8 ONNX via ORT quantize_dynamic.
    """
    from onnxruntime.quantization import quantize_dynamic, QuantType
    import onnxruntime as ort

    print("\n📦 EXPORTACIÓN ONNX + CUANTIZACIÓN INT8 ON-EDGE")
    model = SpotSegmenterUNetNano().cpu()
    model.load_state_dict(torch.load(checkpoint_path, map_location="cpu", weights_only=True))
    model.eval()

    dummy = torch.randn(1, 3, 224, 224, dtype=torch.float32)

    # FP32
    fp32_path = MODELS_DIR / "spot_segmentation_fp32.onnx"
    torch.onnx.export(
        model, dummy, str(fp32_path),
        export_params=True, opset_version=17,
        do_constant_folding=True,
        input_names=["input"], output_names=["mask"],
        dynamic_axes={"input": {0: "batch_size"}, "mask": {0: "batch_size"}},
        dynamo=False,
    )
    print(f"  ✓ FP32: {fp32_path.name} ({fp32_path.stat().st_size/1024:.1f} KB)")

    # INT8 (ORT quantize_dynamic sobre FP32 ONNX)
    for out_name in ["spot_segmentation.onnx", "spot_segmentation_int8.onnx",
                     "unet_nano_spots_int8.onnx"]:
        int8_path = MODELS_DIR / out_name
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            quantize_dynamic(str(fp32_path), str(int8_path), weight_type=QuantType.QUInt8)
        print(f"  ✓ INT8: {out_name} ({int8_path.stat().st_size/1024:.1f} KB)")

    # Verificación
    test_inp = np.random.rand(1, 3, 224, 224).astype(np.float32)
    for p in [fp32_path, MODELS_DIR / "spot_segmentation_int8.onnx"]:
        sess = ort.InferenceSession(str(p), providers=["CPUExecutionProvider"])
        out  = sess.run(None, {"input": test_inp})[0]
        pct  = float((np.squeeze(out) > 0.5).mean() * 100.0)
        print(f"  ✓ Runtime {p.name}: shape={out.shape}, spots={pct:.2f}%")


# ─────────────────────────────────────────────────────────────────────────────
# 8. Pipeline Principal de Entrenamiento
# ─────────────────────────────────────────────────────────────────────────────
def train_isic_segmentation(
    epochs: int = 25,
    batch_size: int = 64,
    lr: float = 8e-4,
    samples_per_epoch: int = 12000,
    val_samples: int = 2000,
    max_isic_pool: int = 60000,
    es_patience: int = 5,
    es_min_delta: float = 0.002,
    plateau_patience: int = 2,
    export_onnx: bool = True,
):
    print("=" * 70)
    print("🔬 U-NET NANO SEGMENTACIÓN v2 — ISIC 2024 + UTKFace")
    print(f"   Dispositivo: {'CUDA (' + torch.cuda.get_device_name(0) + ')' if torch.cuda.is_available() else 'CPU'}")
    print(f"   Épocas máx: {epochs} | Batch: {batch_size} | LR: {lr} | ES patience: {es_patience}")
    print("=" * 70)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # ── 1. Cargar datos
    print("\n[1/6] Cargando recursos...")
    isic_paths = load_isic_paths(max_samples=max_isic_pool)

    if len(isic_paths) < 100:
        raise RuntimeError("Muy pocas imágenes ISIC encontradas. Verificar disco montado.")

    face_tensors = None
    if FACES_CACHE.exists():
        cache = torch.load(FACES_CACHE, weights_only=False)
        face_tensors = cache.get("images") if isinstance(cache, dict) else None
        if face_tensors is not None:
            print(f"  ✓ {len(face_tensors):,} rostros cargados como fondos clínicos")
    else:
        print("  ⚠️  Cache UTKFace no encontrado — se usarán fondos sintéticos")

    # Dividir pool de imágenes ISIC
    random.seed(42)
    random.shuffle(isic_paths)
    train_pool = isic_paths[:max(len(isic_paths) - 5000, len(isic_paths) // 2)]
    val_pool   = isic_paths[len(train_pool):]

    print(f"  ✓ Pool train: {len(train_pool):,} | Pool val: {len(val_pool):,} ISIC")

    train_ds = ISICDermaSegmentationDataset(train_pool, face_tensors, samples_per_epoch, is_train=True)
    val_ds   = ISICDermaSegmentationDataset(val_pool,   face_tensors, val_samples,       is_train=False)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,
                               num_workers=4, pin_memory=True, persistent_workers=True)
    val_loader   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False,
                               num_workers=4, pin_memory=True, persistent_workers=True)

    print(f"  ✓ Batches/época: {len(train_loader)} train | {len(val_loader)} val")

    # ── 2. Modelo
    print("\n[2/6] Inicializando modelo...")
    model    = SpotSegmenterUNetNano().to(device)
    best_pth = MODELS_DIR / "best_spot_model.pth"

    if best_pth.exists():
        try:
            model.load_state_dict(torch.load(best_pth, map_location=device, weights_only=True))
            print(f"  ✓ Checkpoint previo cargado: {best_pth.name}")
        except Exception as e:
            print(f"  ⚠️  No se pudo cargar checkpoint previo: {e}")

    n_params = sum(p.numel() for p in model.parameters())
    print(f"  ✓ Parámetros: {n_params:,} ({n_params * 4 / 1024**2:.2f} MB FP32)")

    # ── 3. Criterio, optimizador, schedulers
    criterion = CombinedBCEDiceLoss(bce_w=0.4, dice_w=0.6)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    plateau_sched = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="max", factor=0.5, patience=plateau_patience,
        min_lr=1e-6, verbose=True,
    )
    scaler     = torch.amp.GradScaler("cuda", enabled=(device.type == "cuda"))
    early_stop = EarlyStopping(patience=es_patience, min_delta=es_min_delta)

    # ── 4. Baseline del modelo actual
    print("\n[3/6] Evaluando modelo base...")

    def compute_val_metrics(loader, mod):
        mod.eval()
        dice_sum, iou_sum, prec_sum, rec_sum, n = 0.0, 0.0, 0.0, 0.0, 0
        with torch.no_grad():
            for imgs, tgts, _ in loader:
                imgs = imgs.to(device, non_blocking=True)
                tgts = tgts.to(device, non_blocking=True)
                with torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
                    logits = mod.forward_logits(imgs)
                probs = torch.sigmoid(logits)
                preds = (probs > 0.5).float()
                tp = (preds * tgts).sum(dim=(1, 2, 3))
                fp = (preds * (1 - tgts)).sum(dim=(1, 2, 3))
                fn = ((1 - preds) * tgts).sum(dim=(1, 2, 3))
                eps = 1e-5
                dice = (2 * tp + eps) / (2 * tp + fp + fn + eps)
                iou  = (tp + eps) / (tp + fp + fn + eps)
                prec = (tp + eps) / (tp + fp + eps)
                rec  = (tp + eps) / (tp + fn + eps)
                bs = imgs.size(0)
                dice_sum += dice.sum().item(); iou_sum  += iou.sum().item()
                prec_sum += prec.sum().item(); rec_sum  += rec.sum().item()
                n += bs
        return dice_sum / n, iou_sum / n, prec_sum / n, rec_sum / n

    base_dice, base_iou, base_prec, base_rec = compute_val_metrics(val_loader, model)
    print(f"  • Baseline → Dice={base_dice:.4f} | IoU={base_iou:.4f} | Prec={base_prec:.4f} | Rec={base_rec:.4f}")

    # ── 5. Entrenamiento
    print(f"\n[4/6] Entrenando (max {epochs} épocas, ES patience={es_patience})...")
    best_val_dice = base_dice

    for epoch in range(1, epochs + 1):
        t0 = time.perf_counter()
        model.train()
        train_loss = 0.0

        pbar = tqdm(train_loader, desc=f"E{epoch:03d}/{epochs}", leave=False)
        for imgs, tgts, _ in pbar:
            imgs = imgs.to(device, non_blocking=True)
            tgts = tgts.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
                logits = model.forward_logits(imgs)
                loss   = criterion(logits, tgts)
            scaler.scale(loss).backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=2.0)
            scaler.step(optimizer)
            scaler.update()
            train_loss += loss.item() * imgs.size(0)
            pbar.set_postfix({"loss": f"{loss.item():.4f}"})

        train_loss /= len(train_ds)
        val_dice, val_iou, val_prec, val_rec = compute_val_metrics(val_loader, model)
        elapsed = time.perf_counter() - t0

        plateau_sched.step(val_dice)

        is_best = val_dice > best_val_dice
        marker  = " 🌟 NUEVO MEJOR" if is_best else ""
        if is_best:
            best_val_dice = val_dice
            torch.save(model.state_dict(), str(best_pth))

        lr_now = optimizer.param_groups[0]["lr"]
        print(
            f"  📊 E{epoch:03d} | Loss={train_loss:.4f} | "
            f"Dice={val_dice:.4f} | IoU={val_iou:.4f} | "
            f"P={val_prec:.3f} R={val_rec:.3f} | LR={lr_now:.2e} | {elapsed:.1f}s{marker}"
        )

        if early_stop(val_dice):
            print(f"\n  🛑 Early Stopping en época {epoch} (sin mejora por {es_patience} épocas)")
            break

    print("\n" + "=" * 70)
    print(f"✅ Entrenamiento completado.")
    print(f"   Baseline Dice: {base_dice:.4f} → Mejor: {best_val_dice:.4f} "
          f"(Δ = {best_val_dice - base_dice:+.4f})")
    print("=" * 70)

    # ── 6. Exportar
    if export_onnx and best_pth.exists():
        print("\n[5/6] Exportando ONNX FP32 + INT8...")
        export_and_quantize_unet(best_pth)
    print("\n[6/6] ¡Listo!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Entrenamiento U-Net Nano con ISIC 2024 v2")
    parser.add_argument("--epochs",       type=int,   default=25,    help="Épocas máximas")
    parser.add_argument("--batch-size",   type=int,   default=64,    help="Batch size")
    parser.add_argument("--lr",           type=float, default=8e-4,  help="Learning rate inicial")
    parser.add_argument("--samples",      type=int,   default=12000, help="Muestras compuestas por época")
    parser.add_argument("--val-samples",  type=int,   default=2000,  help="Muestras de validación")
    parser.add_argument("--max-isic",     type=int,   default=60000, help="Pool máximo ISIC a indexar")
    parser.add_argument("--es-patience",  type=int,   default=5,     help="Early stopping patience")
    parser.add_argument("--no-export",    action="store_true",       help="Omitir exportación ONNX")
    args = parser.parse_args()

    train_isic_segmentation(
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        samples_per_epoch=args.samples,
        val_samples=args.val_samples,
        max_isic_pool=args.max_isic,
        es_patience=args.es_patience,
        export_onnx=not args.no_export,
    )
