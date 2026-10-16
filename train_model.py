"""Train a candidate MobileNetV2 classifier from a hash-disjoint manifest.

Writes a self-contained candidate directory (Keras model, TFLite export,
class mapping, metadata and manifest). The bundled ``model/`` directory is
never modified; promote a candidate only after ``evaluate_model.py`` review.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.artifacts import CLASS_NAMES, sha256_file
from app.dataset import balanced_class_weights, build_manifest, build_pooled_manifest
from app.preprocessing import IMG_SIZE, preprocess_image

PREPROCESSING = 'mobilenet_v2'
ROOT = Path(__file__).resolve().parent


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-dir', type=Path, default=ROOT / 'dataset')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'model_candidate')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--head-epochs', type=int, default=15)
    parser.add_argument('--fine-tune-epochs', type=int, default=15)
    parser.add_argument('--fine-tune-layers', type=int, default=30, help='Unfreeze this many backbone layers for fine-tuning (0 = all)')
    parser.add_argument('--fine-tune-lr', type=float, default=1e-4)
    parser.add_argument('--label-smoothing', type=float, default=0.0)
    parser.add_argument('--extra-no-tumor-dir', type=Path, default=None, help='Extra certain-label no-tumor images added to the training pool only')
    parser.add_argument('--extra-class-dir', type=Path, default=None, help='External class-folder dataset (with optional index.json of patient ids) added to the training pool only')
    parser.add_argument('--pooled', action='store_true', help='Pool all sources and hold out whole clusters (optimistic; see manifest limitation)')
    parser.add_argument('--cluster-validation', action='store_true', help='Keep perceptually similar training images and supplied patient IDs together in train/validation; preserve original Testing folder')
    parser.add_argument('--backbone', choices=['mobilenetv2', 'efficientnetv2s'], default='mobilenetv2')
    parser.add_argument('--limit-per-class', type=int, default=None, help='Cap examples per class and split (smoke runs)')
    parser.add_argument('--no-pretrained', action='store_true', help='Skip ImageNet weights (offline smoke runs)')
    args = parser.parse_args(argv)
    if args.pooled and args.cluster_validation:
        parser.error('--cluster-validation cannot be combined with --pooled')
    return args


def limit_records(records, per_class):
    if per_class is None:
        return records
    return [r for index in range(len(CLASS_NAMES)) for r in [r for r in records if r['class_index'] == index][:per_class]]


def make_dataset(records, root, batch_size, seed=None, augment=False):
    import numpy as np
    import tensorflow as tf

    def generate():
        for record in records:
            tensor, _ = preprocess_image(root / record['path'], PREPROCESSING)
            yield tensor[0], np.eye(len(CLASS_NAMES), dtype=np.float32)[record['class_index']]

    signature = (tf.TensorSpec((*IMG_SIZE, 3), tf.float32), tf.TensorSpec((len(CLASS_NAMES),), tf.float32))
    dataset = tf.data.Dataset.from_generator(generate, output_signature=signature).cache()
    if augment:
        dataset = dataset.shuffle(len(records), seed=seed, reshuffle_each_iteration=True).enumerate()
        dataset = dataset.map(lambda i, example: _augment(example, tf.stack([tf.constant(seed, tf.int64), i]), tf), num_parallel_calls=1, deterministic=True)
    return dataset.batch(batch_size).prefetch(tf.data.AUTOTUNE)


def _augment(example, seed, tf):
    """Stateless, seed-derived augmentation: identical across runs.

    Wide brightness/gamma/contrast and crop/aspect jitter make the classifier
    robust to scanner and export differences between image sources.
    """
    image, label = example
    s = tf.random.experimental.stateless_split(seed, 6)
    image = tf.image.stateless_random_flip_left_right(image, s[0])
    begin, size, _ = tf.image.stateless_sample_distorted_bounding_box(
        tf.shape(image), tf.zeros((1, 0, 4)), seed=s[1], area_range=(0.55, 1.0), aspect_ratio_range=(0.8, 1.25), use_image_if_no_bounding_boxes=True)
    image = tf.image.resize(tf.slice(image, begin, size), IMG_SIZE)
    x = (image + 1.0) / 2.0
    gamma = tf.exp(tf.random.stateless_uniform((), s[2], -0.5, 0.5))
    gain = tf.random.stateless_uniform((), s[3], 0.6, 1.9)
    contrast = tf.random.stateless_uniform((), s[4], 0.7, 1.4)
    x = tf.pow(tf.clip_by_value(x, 0.0, 1.0), gamma) * gain
    mean = tf.reduce_mean(x)
    x = (x - mean) * contrast + mean
    x = x + tf.random.stateless_normal(tf.shape(x), s[5], stddev=0.02)
    return tf.clip_by_value(x, 0.0, 1.0) * 2.0 - 1.0, label


def build_model(pretrained=True, backbone='mobilenetv2'):
    import tensorflow as tf
    from tensorflow.keras.layers import Dense, Dropout, GlobalAveragePooling2D, Input, Rescaling

    weights = 'imagenet' if pretrained else None
    if backbone == 'mobilenetv2':
        base = tf.keras.applications.MobileNetV2(input_shape=(*IMG_SIZE, 3), include_top=False, weights=weights)
        inputs = base.input
    elif backbone == 'efficientnetv2s':
        # The input contract is [-1, 1]; EfficientNetV2 expects [0, 255], so rescale inside the model.
        inputs = Input((*IMG_SIZE, 3))
        base = tf.keras.applications.EfficientNetV2S(include_top=False, weights=weights, input_tensor=Rescaling(127.5, offset=127.5)(inputs))
    else:
        raise ValueError(f'Unknown backbone: {backbone}')
    base.trainable = False
    x = GlobalAveragePooling2D()(base.output)
    x = Dropout(0.4)(x)
    x = Dense(128, activation='relu')(x)
    x = Dropout(0.3)(x)
    output = Dense(len(CLASS_NAMES), activation='softmax')(x)
    return tf.keras.Model(inputs, output), base


def compile_model(model, learning_rate, label_smoothing=0.0):
    import tensorflow as tf
    loss = tf.keras.losses.CategoricalCrossentropy(label_smoothing=label_smoothing)
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate), loss=loss, metrics=['accuracy'])


def freeze_batch_norm(model):
    import tensorflow as tf
    for layer in model.layers:
        if isinstance(layer, tf.keras.layers.BatchNormalization):
            layer.trainable = False


def best_weights_tracker():
    import tensorflow as tf

    class BestWeights(tf.keras.callbacks.Callback):
        """Keeps the lowest validation loss seen across all training phases."""

        def __init__(self):
            super().__init__()
            self.loss = float('inf')
            self.weights = None

        def on_epoch_end(self, epoch, logs=None):
            if logs['val_loss'] < self.loss:
                self.loss = logs['val_loss']
                self.weights = self.model.get_weights()

    return BestWeights()


def export(model, output_dir, manifest, args, best_val_loss):
    import tensorflow as tf
    output_dir.mkdir(parents=True, exist_ok=True)
    h5_path = output_dir / 'best_model.h5'
    tflite_path = output_dir / 'brain_tumor_model.tflite'
    model.save(h5_path, include_optimizer=False)
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    tflite_path.write_bytes(converter.convert())
    (output_dir / 'class_indices.json').write_text(json.dumps({name: i for i, name in enumerate(CLASS_NAMES)}))
    (output_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    metadata = {
        'schema_version': 1,
        'preprocessing': PREPROCESSING,
        'image_size': list(IMG_SIZE),
        'classes': CLASS_NAMES,
        'output': 'probabilities',
        'artifact_hashes': {'brain_tumor_model.tflite': sha256_file(tflite_path), 'best_model.h5': sha256_file(h5_path)},
        'training': {
            'created': datetime.now(timezone.utc).isoformat(),
            'seed': args.seed,
            'backbone': args.backbone,
            'fine_tune_layers': args.fine_tune_layers,
            'fine_tune_lr': args.fine_tune_lr,
            'label_smoothing': args.label_smoothing,
            'validation_grouping': manifest.get('validation_grouping'),
            'best_validation_loss': best_val_loss,
            'split_counts': {s: len(manifest[s]) for s in ('train', 'validation', 'test')},
            'tensorflow': tf.__version__,
        },
    }
    (output_dir / 'metadata.json').write_text(json.dumps(metadata, indent=2))
    return metadata


def train(args):
    import tensorflow as tf
    from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau

    tf.keras.utils.set_random_seed(args.seed)
    tf.config.experimental.enable_op_determinism()
    builder = build_pooled_manifest if args.pooled else build_manifest
    split_options = {'cluster_validation': True} if args.cluster_validation else {}
    manifest = builder(args.dataset_dir, args.seed, extra_no_tumor_dir=args.extra_no_tumor_dir, extra_class_dir=args.extra_class_dir, **split_options)
    for split in ('train', 'validation'):
        manifest[split] = limit_records(manifest[split], args.limit_per_class)
    root = Path(manifest['dataset_dir'])
    train_ds = make_dataset(manifest['train'], root, args.batch_size, args.seed, augment=True)
    val_ds = make_dataset(manifest['validation'], root, args.batch_size)
    weights = balanced_class_weights([r['class_index'] for r in manifest['train']])
    print(f"Train {len(manifest['train'])} | validation {len(manifest['validation'])} | excluded {manifest['excluded']}")
    if 'validation_grouping' in manifest:
        print('Validation grouping:', json.dumps(manifest['validation_grouping']))

    model, base = build_model(pretrained=not args.no_pretrained, backbone=args.backbone)
    tracker = best_weights_tracker()

    def callbacks():
        return [tracker, EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True), ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=2, min_lr=1e-7)]

    compile_model(model, 1e-3, args.label_smoothing)
    model.fit(train_ds, epochs=args.head_epochs, validation_data=val_ds, callbacks=callbacks(), class_weight=weights, verbose=2)

    base.trainable = True
    if args.fine_tune_layers:
        for layer in base.layers[:-args.fine_tune_layers]:
            layer.trainable = False
    freeze_batch_norm(model)
    compile_model(model, args.fine_tune_lr, args.label_smoothing)
    model.fit(train_ds, epochs=args.fine_tune_epochs, validation_data=val_ds, callbacks=callbacks(), class_weight=weights, verbose=2)

    model.set_weights(tracker.weights)
    metadata = export(model, args.output_dir, manifest, args, tracker.loss)
    print(f'Candidate written to {args.output_dir} (best validation loss {tracker.loss:.4f})')
    print(f'Evaluate: python evaluate_model.py --model-dir {args.output_dir} --output {args.output_dir}/evaluation.json')
    return metadata


if __name__ == '__main__':
    os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
    train(parse_args())
