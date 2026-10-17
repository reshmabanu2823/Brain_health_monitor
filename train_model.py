import os
import numpy as np
import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout, BatchNormalization
from tensorflow.keras.models import Model
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping, ReduceLROnPlateau
import json

# ── CONFIG ────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH  = os.path.join(BASE_DIR, "dataset", "Training")
MODEL_DIR     = os.path.join(BASE_DIR, "model")
IMG_SIZE      = (224, 224)
BATCH_SIZE    = 32   # Larger batch = more stable gradients
PHASE1_EPOCHS = 25
PHASE2_EPOCHS = 40
NUM_CLASSES   = 4

print("=" * 65)
print("   BRAIN HEALTH MONITOR — RETRAIN WITH CORRECT PREPROCESSING")
print("   Backbone: MobileNetV2 | Proper RGB (no grayscale CLAHE bug)")
print("=" * 65)
print(f"\n Dataset : {DATASET_PATH}")
print(f" Model   : {MODEL_DIR}\n")

os.makedirs(MODEL_DIR, exist_ok=True)

# ── DATA GENERATORS ───────────────────────────────────────────────
# KEY DIFFERENCE FROM OLD MODEL: MobileNetV2 preprocessing is applied
# (scales to [-1, 1]) instead of simple /255.0. This matches what the
# backbone was pre-trained with, giving it proper feature activations.
print("[1/5] Setting up data generators with MobileNetV2 preprocessing...")

# MobileNetV2 expects input in [-1, 1] range
def mobilenet_preprocess(x):
    return tf.keras.applications.mobilenet_v2.preprocess_input(x)

train_datagen = ImageDataGenerator(
    preprocessing_function=mobilenet_preprocess,
    rotation_range=20,
    width_shift_range=0.1,
    height_shift_range=0.1,
    shear_range=0.1,
    zoom_range=0.2,
    horizontal_flip=True,
    fill_mode='nearest',
    validation_split=0.2
)

val_datagen = ImageDataGenerator(
    preprocessing_function=mobilenet_preprocess,
    validation_split=0.2
)

train_generator = train_datagen.flow_from_directory(
    DATASET_PATH,
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode='categorical',
    subset='training',
    shuffle=True
)

val_generator = val_datagen.flow_from_directory(
    DATASET_PATH,
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode='categorical',
    subset='validation',
    shuffle=False
)

print(f" Training   : {train_generator.samples} images")
print(f" Validation : {val_generator.samples} images")
print(f" Classes    : {train_generator.class_indices}\n")

# Save class indices
with open(os.path.join(MODEL_DIR, "class_indices.json"), 'w') as f:
    json.dump(train_generator.class_indices, f)

# ── CLASS WEIGHTS (mild — don't over-penalise) ────────────────────
# Computed from dataset: glioma=826, meningioma=822, no_tumor=395, pituitary=827
# Total=2870, num_classes=4 → balanced = total/(num_classes * count)
total = 826 + 822 + 395 + 827
class_weights = {
    0: total / (4 * 826),   # glioma      ~0.87
    1: total / (4 * 822),   # meningioma  ~0.87
    2: total / (4 * 395),   # no_tumor    ~1.82
    3: total / (4 * 827),   # pituitary   ~0.87
}
print(f" Class weights: {class_weights}\n")

# ── BUILD MODEL ───────────────────────────────────────────────────
print("[2/5] Building MobileNetV2 model...")

base_model = MobileNetV2(
    input_shape=(224, 224, 3),
    include_top=False,
    weights='imagenet'
)
base_model.trainable = False

x = base_model.output
x = GlobalAveragePooling2D()(x)
x = Dense(256, activation='relu')(x)
x = Dropout(0.5)(x)
x = Dense(128, activation='relu')(x)
x = Dropout(0.3)(x)
output = Dense(NUM_CLASSES, activation='softmax')(x)

model = Model(inputs=base_model.input, outputs=output)

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
    loss='categorical_crossentropy',
    metrics=['accuracy']
)

print(f" Parameters : {model.count_params():,}")
print(f" Trainable  : {sum(tf.size(v).numpy() for v in model.trainable_variables):,}\n")

# ── CALLBACKS ─────────────────────────────────────────────────────
print("[3/5] Setting up callbacks...")

checkpoint = ModelCheckpoint(
    filepath=os.path.join(MODEL_DIR, 'best_model.h5'),
    monitor='val_accuracy',
    save_best_only=True,
    verbose=1
)
early_stop = EarlyStopping(
    monitor='val_accuracy',
    patience=8,
    restore_best_weights=True,
    verbose=1
)
reduce_lr = ReduceLROnPlateau(
    monitor='val_loss',
    factor=0.5,
    patience=4,
    min_lr=1e-7,
    verbose=1
)

# ── PHASE 1: Train head only ───────────────────────────────────────
print("[4/5] Phase 1 — Training classification head (frozen backbone)...")
print("-" * 65)

history1 = model.fit(
    train_generator,
    epochs=PHASE1_EPOCHS,
    validation_data=val_generator,
    callbacks=[checkpoint, early_stop, reduce_lr],
    class_weight=class_weights,
    verbose=1
)

best_p1 = max(history1.history.get('val_accuracy', [0]))
print(f"\n Phase 1 Best Val Accuracy: {best_p1:.2%}\n")

# ── PHASE 2: Fine-tune top layers ─────────────────────────────────
print("[5/5] Phase 2 — Fine-tuning top 50 MobileNetV2 layers...")
print("-" * 65)

# Unfreeze top 50 layers
base_model.trainable = True
for layer in base_model.layers[:-50]:
    layer.trainable = False

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=1e-4),
    loss='categorical_crossentropy',
    metrics=['accuracy']
)

early_stop2 = EarlyStopping(
    monitor='val_accuracy',
    patience=10,
    restore_best_weights=True,
    verbose=1
)

history2 = model.fit(
    train_generator,
    epochs=PHASE2_EPOCHS,
    validation_data=val_generator,
    callbacks=[checkpoint, early_stop2, reduce_lr],
    class_weight=class_weights,
    verbose=1
)

best_p2 = max(history2.history.get('val_accuracy', [0]))

# ── EXPORT TFLite ─────────────────────────────────────────────────
print("\n Converting to TFLite...")

model.load_weights(os.path.join(MODEL_DIR, 'best_model.h5'))

converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.target_spec.supported_types = [tf.float16]
tflite_model = converter.convert()

tflite_path = os.path.join(MODEL_DIR, 'brain_tumor_model.tflite')
with open(tflite_path, 'wb') as f:
    f.write(tflite_model)

print(f"\n{'=' * 65}")
print(f"   TRAINING COMPLETE!")
print(f"{'=' * 65}")
print(f" Phase 1 Val Accuracy : {best_p1:.2%}")
print(f" Phase 2 Val Accuracy : {max(best_p1, best_p2):.2%}")
print(f" Model saved          : {tflite_path}")
print(f" TFLite size          : {os.path.getsize(tflite_path)/1024/1024:.2f} MB")
print(f"{'=' * 65}\n")
