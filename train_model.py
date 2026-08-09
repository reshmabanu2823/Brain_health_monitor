import os
import numpy as np
import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout
from tensorflow.keras.models import Model
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping, ReduceLROnPlateau
import json

# ── CONFIG ────────────────────────────────────────────────────────
DATASET_PATH  = r"C:\Users\MSEC-018-38\Desktop\brain_project\dataset\Training"
MODEL_DIR     = r"C:\Users\MSEC-018-38\Desktop\brain_project\model"
IMG_SIZE      = (224, 224)
BATCH_SIZE    = 16
EPOCHS        = 30
NUM_CLASSES   = 4

CLASS_NAMES = ['glioma_tumor', 'meningioma_tumor', 'no_tumor', 'pituitary_tumor']

print("=" * 60)
print("   BRAIN TUMOR DETECTION — MODEL TRAINING")
print("=" * 60)
print(f"\n Dataset : {DATASET_PATH}")
print(f" Model   : {MODEL_DIR}")
print(f" Epochs  : {EPOCHS}")
print(f" Classes : {CLASS_NAMES}\n")

# ── DATA GENERATORS ───────────────────────────────────────────────
print("[1/5] Setting up data generators...")

train_datagen = ImageDataGenerator(
    rescale=1./255,
    rotation_range=20,
    width_shift_range=0.1,
    height_shift_range=0.1,
    shear_range=0.1,
    zoom_range=0.2,
    horizontal_flip=True,
    fill_mode='nearest',
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

val_generator = train_datagen.flow_from_directory(
    DATASET_PATH,
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode='categorical',
    subset='validation',
    shuffle=False
)

print(f" Training samples   : {train_generator.samples}")
print(f" Validation samples : {val_generator.samples}")
print(f" Class indices      : {train_generator.class_indices}\n")

# Save class indices for the app
class_indices_path = os.path.join(MODEL_DIR, "class_indices.json")
with open(class_indices_path, 'w') as f:
    json.dump(train_generator.class_indices, f)
print(f" Class indices saved to {class_indices_path}\n")

# ── BUILD MODEL ───────────────────────────────────────────────────
print("[2/5] Building MobileNetV2 model...")

base_model = MobileNetV2(
    input_shape=(224, 224, 3),
    include_top=False,
    weights='imagenet'
)
base_model.trainable = False  # Freeze base first

x = base_model.output
x = GlobalAveragePooling2D()(x)
x = Dropout(0.4)(x)
x = Dense(128, activation='relu')(x)
x = Dropout(0.3)(x)
output = Dense(NUM_CLASSES, activation='softmax')(x)

model = Model(inputs=base_model.input, outputs=output)

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
    loss='categorical_crossentropy',
    metrics=['accuracy']
)

print(f" Model built successfully")
print(f" Total parameters : {model.count_params():,}\n")

# ── CALLBACKS ─────────────────────────────────────────────────────
print("[3/5] Setting up training callbacks...")

checkpoint = ModelCheckpoint(
    filepath=os.path.join(MODEL_DIR, 'best_model.h5'),
    monitor='val_accuracy',
    save_best_only=True,
    verbose=1
)

early_stop = EarlyStopping(
    monitor='val_accuracy',
    patience=7,
    restore_best_weights=True,
    verbose=1
)

reduce_lr = ReduceLROnPlateau(
    monitor='val_loss',
    factor=0.5,
    patience=3,
    min_lr=1e-7,
    verbose=1
)

print(" Callbacks ready\n")

# ── TRAIN PHASE 1 (frozen base) ───────────────────────────────────
print("[4/5] Training Phase 1 — Top layers only...")
print("-" * 60)

class_weights = {0: 2.0, 1: 6.0, 2: 4.0, 3: 2.0}
history = model.fit(
    train_generator,
    epochs=15,
    validation_data=val_generator,
    callbacks=[checkpoint, early_stop, reduce_lr],
    class_weight=class_weights,
    verbose=1
)
# ── TRAIN PHASE 2 (fine-tuning) ───────────────────────────────────
print("\n Fine-tuning — Unfreezing top layers of base model...")

base_model.trainable = True
for layer in base_model.layers[:-30]:
    layer.trainable = False

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.0001),
    loss='categorical_crossentropy',
    metrics=['accuracy']
)

history2 = model.fit(
    train_generator,
    epochs=EPOCHS,
    validation_data=val_generator,
    callbacks=[checkpoint, early_stop, reduce_lr],
    verbose=1
)

# ── CONVERT TO TFLITE ─────────────────────────────────────────────
print("\n[5/5] Converting to TFLite format...")

converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
tflite_model = converter.convert()

tflite_path = os.path.join(MODEL_DIR, 'brain_tumor_model.tflite')
with open(tflite_path, 'wb') as f:
    f.write(tflite_model)

print(f"\n{'=' * 60}")
print(f"   TRAINING COMPLETE!")
print(f"{'=' * 60}")
print(f" Model saved  : {tflite_path}")
print(f" Size         : {os.path.getsize(tflite_path) / (1024*1024):.2f} MB")
print(f"\n Final Validation Accuracy : {max(history2.history['val_accuracy']):.2%}")
print(f"{'=' * 60}\n")
