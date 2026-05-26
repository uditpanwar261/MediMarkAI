# MediMark AI — Model Files Directory

Place your trained model weights here.

## Expected Files

| File | Description | Size (approx) |
|------|-------------|---------------|
| `yolo_medical.pt` | YOLOv8 medical detection model | 6–140 MB |
| `unet_medical.h5` | U-Net segmentation model (TF/Keras) | 30–120 MB |
| `unet_medical.pt` | U-Net segmentation model (PyTorch) | 30–120 MB |

## Without Model Files

MediMark AI automatically falls back to **mock mode** when no model
files are present. Mock mode generates plausible synthetic annotations
using OpenCV image statistics — useful for development and demos.

## Bringing Your Own Model

### YOLO (Ultralytics)
```python
from ultralytics import YOLO

# Train from scratch or fine-tune
model = YOLO('yolov8n.pt')
model.train(
    data    = 'your_medical_dataset.yaml',
    epochs  = 100,
    imgsz   = 640,
    project = 'runs/medical',
    name    = 'yolo_medical'
)
model.export(format='torchscript')   # optional
# Copy best.pt here:
# cp runs/medical/yolo_medical/weights/best.pt ml_models/yolo_medical.pt
```

### U-Net (TensorFlow / Keras)
```python
import tensorflow as tf

model = build_unet(input_shape=(256, 256, 3))
model.compile(optimizer='adam', loss='binary_crossentropy',
              metrics=['accuracy'])
model.fit(train_ds, validation_data=val_ds, epochs=50)
model.save('ml_models/unet_medical.h5')
```

### U-Net (PyTorch)
```python
import torch

model = UNet(in_channels=3, out_channels=1)
# ... training loop ...
torch.save(model, 'ml_models/unet_medical.pt')
```

## Public Datasets for Training

- **CheXpert** — Stanford chest X-ray dataset (224k images)
- **NIH ChestX-ray14** — 112k chest X-ray images
- **LUNA16** — Lung nodule CT challenge
- **RSNA Pneumonia Detection** — Kaggle challenge dataset
- **KITS21** — Kidney tumour segmentation
