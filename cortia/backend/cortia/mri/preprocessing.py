"""Explicit source contracts shared by inference, attribution and verification."""
import numpy as np
from PIL import Image

CONTRACTS = ('legacy_rgb_0_1', 'mobilenet_v2')


def description(contract):
    if contract not in CONTRACTS:
        raise ValueError('Unsupported MRI preprocessing contract')
    normalization = '/255' if contract == 'legacy_rgb_0_1' else '/127.5 - 1'
    return f'RGB, bilinear 224×224, values {normalization}'


def preprocess(image, contract):
    description(contract)
    pixels = np.asarray(image.convert('RGB').resize((224,224),Image.Resampling.BILINEAR),dtype=np.float32)
    return (pixels/255 if contract == 'legacy_rgb_0_1' else pixels/127.5-1)[None,...]


def display_pixels(tensor, contract):
    description(contract)
    pixels = tensor[0] if contract == 'legacy_rgb_0_1' else (tensor[0]+1)/2
    return np.clip(pixels,0,1)
