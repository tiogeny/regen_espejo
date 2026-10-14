"""
Hermes ML Training Pipeline: Segmentación de Manchas e Hiperpigmentación Cutánea con U-Net Nano.
Dataset: Muestras Faciales UTKFace (D:\\Rostros) + Calibración Espectral Dermatoscópica
Aceleración: NVIDIA CUDA (Quadro RTX 4000)
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

import cv2
import numpy as np
from PIL import Image
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from tqdm import tqdm

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


# =====================================================================
# 1. Arquitectura de Segmentación (Fast-UNet Nano Depthwise Separable)
# =====================================================================
class DSConvBlock(nn.Module):
    """
    Bloque Depthwise-Separable optimizado para ARM NEON y Edge AI.
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
    U-Net Nano ultraligera para segmentación semántica de manchas y lentigos solares.
    Entrada: [B, 3, 224, 224] -> Salida: [B, 1, 224, 224] (probabilidad sigmoid)
    """
    def __init__(self):
        super().__init__()
        self.init_conv = nn.Sequential(
            nn.Conv2d(3, 8, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(8),
            nn.ReLU(inplace=True),
        )

        self.enc1 = DSConvBlock(8, 12)
        self.pool1 = nn.MaxPool2d(2)  # 112x112

        self.enc2 = DSConvBlock(12, 24)
        self.pool2 = nn.MaxPool2d(2)  # 56x56

        self.enc3 = DSConvBlock(24, 48)
        self.pool3 = nn.MaxPool2d(2)  # 28x28

        self.bottleneck = DSConvBlock(48, 64)

        self.up3 = nn.Sequential(
            nn.Upsample(scale_factor=2, mode="nearest"),
            nn.Conv2d(64, 32, kernel_size=1, bias=False),
        )
        self.dec3 = DSConvBlock(32 + 48, 32)

        self.up2 = nn.Sequential(
            nn.Upsample(scale_factor=2, mode="nearest"),
            nn.Conv2d(32, 16, kernel_size=1, bias=False),
        )
        self.dec2 = DSConvBlock(16 + 24, 16)

        self.up1 = nn.Sequential(
            nn.Upsample(scale_factor=2, mode="nearest"),
            nn.Conv2d(16, 8, kernel_size=1, bias=False),
        )
        self.dec1 = DSConvBlock(8 + 12, 8)

        self.final_conv = nn.Conv2d(8, 1, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [B, 3, 224, 224]
        x0 = self.init_conv(x)
        e1 = self.enc1(x0)
        e2 = self.enc2(self.pool1(e1))
        e3 = self.enc3(self.pool2(e2))

        b = self.bottleneck(self.pool3(e3))

        d3 = self.up3(b)
        d3 = torch.cat([d3, e3], dim=1)
        d3 = self.dec3(d3)

        d2 = self.up2(d3)
        d2 = torch.cat([d2, e2], dim=1)
        d2 = self.dec2(d2)

        d1 = self.up1(d2)
        d1 = torch.cat([d1, e1], dim=1)
        d1 = self.dec1(d1)

        out = torch.sigmoid(self.final_conv(d1))
        return out


# =====================================================================
# 2. Generación Espectral de Datos y Aumentación Dermatoscópica
# =====================================================================
def extract_spectral_spots_and_augment(img_rgb: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Genera pares de entrenamiento (imagen_rgb, mascara_ground_truth) a partir
    de rostros reales usando calibración espectral CIE-Lab e inyección de máculas sintéticas.
    """
    h, w = img_rgb.shape[:2]

    # 1. Máscara del óvalo facial (zona anatómica de interés)
    mask_face = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(mask_face, (w // 2, h // 2), (int(w * 0.36), int(h * 0.44)), 0, 0, 360, 1, -1)

    # 2. Extracción de manchas endógenas reales vía CIELAB Luminance Difference
    lab = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2LAB)
    l_channel = lab[:, :, 0].astype(np.float32) / 255.0
    blur_l = cv2.GaussianBlur(l_channel, (25, 25), 0)
    diff = blur_l - l_channel  # Zonas más oscuras que el promedio local

    natural_spots = (diff > 0.12) & (mask_face > 0)

    # 3. Inyección controlada de máculas sintéticas para enriquecer variabilidad
    synth_mask = np.zeros((h, w), dtype=bool)
    num_maculae = np.random.randint(1, 8)
    augmented_rgb = img_rgb.copy()

    for _ in range(num_maculae):
        # Centro dentro del óvalo facial
        cx = int(np.random.normal(w // 2, w * 0.15))
        cy = int(np.random.normal(h // 2, h * 0.18))
        cx = np.clip(cx, int(w * 0.2), int(w * 0.8))
        cy = np.clip(cy, int(h * 0.2), int(h * 0.8))

        # Tamaño de la mancha (2mm a 10mm en imagen de 224px -> radios 3 a 12px)
        rx = np.random.randint(3, 13)
        ry = np.random.randint(3, 13)
        angle = np.random.randint(0, 180)

        spot_patch = np.zeros((h, w), dtype=np.uint8)
        cv2.ellipse(spot_patch, (cx, cy), (rx, ry), angle, 0, 360, 255, -1)
        spot_patch = cv2.GaussianBlur(spot_patch, (5, 5), 0)

        # Atenuación de melanina (oscurecer en 20-50%)
        melanin_factor = np.random.uniform(0.55, 0.80)
        norm_patch = (spot_patch.astype(np.float32) / 255.0)[..., np.newaxis]

        augmented_rgb = (
            augmented_rgb.astype(np.float32) * (1.0 - norm_patch * (1.0 - melanin_factor))
        ).astype(np.uint8)

        synth_mask |= (spot_patch > 80) & (mask_face > 0)

    # Máscara combinada Ground Truth
    gt_mask = (natural_spots | synth_mask).astype(np.float32)
    return augmented_rgb, gt_mask


def process_segmentation_sample(path: str) -> Tuple[np.ndarray, np.ndarray]:
    """Carga y procesa un par de segmentación (CHW uint8, HW float32)."""
    with Image.open(path) as img:
        img_resized = img.convert("RGB").resize((224, 224), Image.Resampling.BILINEAR)
        arr = np.array(img_resized, dtype=np.uint8)

    aug_rgb, gt_mask = extract_spectral_spots_and_augment(arr)
    # HWC -> CHW
    chw_img = np.transpose(aug_rgb, (2, 0, 1))
    return chw_img, gt_mask[np.newaxis, ...]  # [1, 224, 224]


class RamCachedSegmentationDataset(Dataset):
    """Dataset de segmentación con tensores precargados en memoria RAM."""
    def __init__(self, images: torch.Tensor, masks: torch.Tensor, is_train: bool = True):
        self.images = images  # [N, 3, 224, 224] uint8
        self.masks = masks    # [N, 1, 224, 224] float32
        self.is_train = is_train

    def __len__(self):
        return len(self.images)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        img = self.images[idx].float().div_(255.0)
        mask = self.masks[idx]

        if self.is_train:
            # Flip horizontal sincronizado
            if torch.rand(1).item() > 0.5:
                img = torch.flip(img, dims=[2])
                mask = torch.flip(mask, dims=[2])

        return img, mask


# =====================================================================
# 3. Funciones de Pérdida Especializadas (Dice + BCE)
# =====================================================================
class DiceLoss(nn.Module):
    def __init__(self, smooth: float = 1e-6):
        super().__init__()
        self.smooth = smooth

    def forward(self, preds: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        # preds y targets: [B, 1, H, W]
        preds_flat = preds.view(preds.size(0), -1)
        targets_flat = targets.view(targets.size(0), -1)

        intersection = (preds_flat * targets_flat).sum(dim=1)
        dice = (2.0 * intersection + self.smooth) / (preds_flat.sum(dim=1) + targets_flat.sum(dim=1) + self.smooth)
        return 1.0 - dice.mean()


class CombinedSegLoss(nn.Module):
    def __init__(self):
        super().__init__()
        self.bce = nn.BCELoss()
        self.dice = DiceLoss()

    def forward(self, preds: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        return self.bce(preds, targets) + self.dice(preds, targets)


# =====================================================================
# 4. Pipeline de Entrenamiento y Validación
# =====================================================================
def train_seg_epoch(model, loader, criterion, optimizer, device):
    model.train()
    total_loss = 0.0
    num_samples = 0

    pbar = tqdm(loader, desc="  Train Seg", leave=False)
    for images, masks in pbar:
        images = images.to(device, non_blocking=True)
        masks = masks.to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)
        preds = model(images)
        loss = criterion(preds, masks)
        loss.backward()
        optimizer.step()

        batch_size = images.size(0)
        total_loss += loss.item() * batch_size
        num_samples += batch_size

        pbar.set_postfix(loss=f"{loss.item():.4f}")

    return total_loss / num_samples


@torch.no_grad()
def evaluate_seg(model, loader, criterion, device):
    model.eval()
    total_loss = 0.0
    total_dice = 0.0
    num_samples = 0

    for images, masks in tqdm(loader, desc="  Val Seg  ", leave=False):
        images = images.to(device, non_blocking=True)
        masks = masks.to(device, non_blocking=True)

        preds = model(images)
        loss = criterion(preds, masks)

        # Métrica Dice binaria con threshold > 0.5
        preds_bin = (preds > 0.5).float()
        intersection = (preds_bin * masks).sum(dim=[1, 2, 3])
        dice_score = (2.0 * intersection + 1e-6) / (preds_bin.sum(dim=[1, 2, 3]) + masks.sum(dim=[1, 2, 3]) + 1e-6)

        batch_size = images.size(0)
        total_loss += loss.item() * batch_size
        total_dice += dice_score.sum().item()
        num_samples += batch_size

    return total_loss / num_samples, total_dice / num_samples


# =====================================================================
# 5. Exportación y Cuantización ONNX
# =====================================================================
def export_seg_to_onnx(model, output_dir: Path):
    print("\n" + "=" * 60)
    print("🚀 HERMES ML: Exportación y Cuantización U-Net Nano ONNX INT8")
    print("=" * 60)

    model.eval()
    model_cpu = model.to("cpu")
    dummy_input = torch.randn(1, 3, 224, 224, dtype=torch.float32)

    fp32_path = output_dir / "spot_segmentation_fp32.onnx"
    int8_path = output_dir / "spot_segmentation.onnx"

    print(f"\n[1/3] Exportando grafo ONNX FP32 -> {fp32_path.name}...")
    torch.onnx.export(
        model_cpu,
        dummy_input,
        str(fp32_path),
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["mask"],
        dynamic_axes={"input": {0: "batch_size"}, "mask": {0: "batch_size"}},
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
    out_mask = np.squeeze(out[0])
    print(f"  ✓ Inferencia verificada: Forma={out_mask.shape}, Latencia={avg_lat:.2f} ms")


# =====================================================================
# 6. Punto de Entrada Principal
# =====================================================================
def main():
    parser = argparse.ArgumentParser(description="Entrenamiento de U-Net Nano para Segmentación de Manchas")
    parser.add_argument("--data_dir", type=str, default=r"D:\Rostros", help="Ruta al dataset de rostros")
    parser.add_argument("--max_samples", type=int, default=6000, help="Número de muestras para segmentación")
    parser.add_argument("--epochs", type=int, default=10, help="Número de épocas de entrenamiento")
    parser.add_argument("--batch_size", type=int, default=32, help="Tamaño del batch")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate inicial")
    parser.add_argument("--val_split", type=float, default=0.15, help="Proporción para validación")
    parser.add_argument("--export_onnx", action="store_true", default=True, help="Exportar a ONNX al finalizar")
    args = parser.parse_args()

    print("=" * 60)
    print("🔬 HERMES ML TRAINING: Segmentador U-Net Nano de Manchas Cutáneas")
    print("=" * 60)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Hardware Acelerador: {device}")
    if device.type == "cuda":
        torch.cuda.empty_cache()
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    # 1. Recolección de muestras
    candidates = glob.glob(os.path.join(args.data_dir, "**", "*.jpg"), recursive=True)
    candidates = [c for c in candidates if len(os.path.basename(c).split("_")) >= 4]
    np.random.seed(42)
    np.random.shuffle(candidates)
    selected_paths = candidates[: args.max_samples]
    total_samples = len(selected_paths)
    print(f"\n[1/5] Preparando {total_samples} muestras espectrales con aumentación multihilo...")

    # Precarga paralela
    images_np = np.empty((total_samples, 3, 224, 224), dtype=np.uint8)
    masks_np = np.empty((total_samples, 1, 224, 224), dtype=np.float32)

    with ThreadPoolExecutor(max_workers=16) as executor:
        for idx, (img, mask) in enumerate(tqdm(executor.map(process_segmentation_sample, selected_paths), total=total_samples, desc="  Spectral Proc")):
            images_np[idx] = img
            masks_np[idx] = mask

    images_tensor = torch.from_numpy(images_np)
    masks_tensor = torch.from_numpy(masks_np)

    # 2. Split Train / Validation
    val_size = int(total_samples * args.val_split)
    train_size = total_samples - val_size
    train_dataset = RamCachedSegmentationDataset(images_tensor[:train_size], masks_tensor[:train_size], is_train=True)
    val_dataset = RamCachedSegmentationDataset(images_tensor[train_size:], masks_tensor[train_size:], is_train=False)

    print(f"  ✓ Conjunto Train: {len(train_dataset)} muestras")
    print(f"  ✓ Conjunto Val:   {len(val_dataset)} muestras")

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=0, pin_memory=False, drop_last=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=0, pin_memory=False)

    # 3. Inicializar Modelo, Pérdida y Optimizador
    print("\n[2/5] Inicializando SpotSegmenterUNetNano...")
    model = SpotSegmenterUNetNano().to(device)
    criterion = CombinedSegLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-5)

    # 4. Bucle de Entrenamiento
    print(f"\n[3/5] Entrenando U-Net Nano por {args.epochs} épocas...")
    best_dice = 0.0
    best_weights_path = MODELS_DIR / "best_spot_model.pth"

    for epoch in range(1, args.epochs + 1):
        t_start = time.perf_counter()
        train_loss = train_seg_epoch(model, train_loader, criterion, optimizer, device)
        val_loss, val_dice = evaluate_seg(model, val_loader, criterion, device)
        scheduler.step()
        epoch_sec = time.perf_counter() - t_start

        is_best = val_dice > best_dice
        marker = " [BEST]" if is_best else ""
        if is_best:
            best_dice = val_dice
            torch.save(model.state_dict(), best_weights_path)

        lr_curr = optimizer.param_groups[0]["lr"]
        print(
            f"Época [{epoch:02d}/{args.epochs:02d}] "
            f"Train Loss: {train_loss:.4f} | "
            f"Val Loss: {val_loss:.4f} | Val Dice: {val_dice:.4f} | "
            f"LR: {lr_curr:.1e} | Tiempo: {epoch_sec:.1f}s{marker}"
        )

    print(f"\n[4/5] Entrenamiento finalizado. Mejor Val Dice Score: {best_dice:.4f}")

    # 5. Exportar a ONNX
    if args.export_onnx:
        print(f"\n[5/5] Cargando mejor modelo ({best_weights_path.name}) para exportar a ONNX...")
        model.load_state_dict(torch.load(best_weights_path, map_location="cpu"))
        export_seg_to_onnx(model, MODELS_DIR)

    print("\n✅ Pipeline de entrenamiento de segmentación completado con éxito!")


if __name__ == "__main__":
    main()
