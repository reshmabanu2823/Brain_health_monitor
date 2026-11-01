from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient

pydicom = pytest.importorskip('pydicom',reason='Optional MR DICOM decoder not installed')
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, MRImageStorage, generate_uid

from cortia.config import Settings
from cortia.main import create_app
from cortia.mri.service import validate_image
from test_api import signup


def dicom_bytes(pixels, **changes):
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = MRImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    ds = FileDataset('',{},file_meta=meta,preamble=b'\0'*128)
    ds.SOPClassUID = meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    ds.Modality = 'MR'
    ds.PatientName = 'Fixture^MetadataOnly'
    ds.PatientID = 'TEST-ONLY-PATIENT'
    ds.Rows,ds.Columns = pixels.shape
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = 'MONOCHROME2'
    ds.BitsAllocated = pixels.dtype.itemsize*8
    ds.BitsStored = ds.BitsAllocated
    ds.HighBit = ds.BitsStored-1
    ds.PixelRepresentation = 0
    ds.PixelData = pixels.tobytes()
    for name,value in changes.items():
        setattr(ds,name,value)
    buffer = BytesIO()
    pydicom.dcmwrite(buffer,ds,enforce_file_format=True)
    return buffer.getvalue()


@pytest.mark.parametrize('photo,expected',[
    ('MONOCHROME2',[[0,64],[128,255]]),
    ('MONOCHROME1',[[255,191],[128,0]]),
])
def test_single_frame_mr_normalizes_and_inverts_declared_pixels(photo,expected):
    content = dicom_bytes(np.array([[0,50],[100,200]],dtype='<u2'),
                          PhotometricInterpretation=photo,RescaleSlope=2,RescaleIntercept=-100)
    image = validate_image(content,'scan.DCM')
    assert image.mode == 'RGB'
    assert np.asarray(image)[:,:,0].tolist() == expected
    assert image.info == {}


@pytest.mark.parametrize('changes',[
    {'Modality':'CT'},
    {'NumberOfFrames':2},
    {'PhotometricInterpretation':'PALETTE COLOR'},
    {'PixelData':b'\0'},
])
def test_invalid_or_unsupported_dicom_never_yields_an_image(changes):
    content = dicom_bytes(np.array([[0,50],[100,200]],dtype='<u2'),**changes)
    with pytest.raises(ValueError):
        validate_image(content,'scan.dcm')


def test_uniform_dicom_never_yields_interpretable_image():
    content = dicom_bytes(np.ones((4,4),dtype='<u2'))
    with pytest.raises(ValueError):
        validate_image(content,'scan.dcm')


def test_real_mri_in_dicom_upload_retains_only_pixels_and_source_digest(tmp_path):
    source = Path('/home/vinay/brain_health_monitor/dataset/no/N1.JPG')
    if not source.exists():
        pytest.skip('Original MRI fixture absent')
    with Image.open(source) as original:
        pixels = np.asarray(original.convert('L'),dtype='uint8')
    content = dicom_bytes(pixels)
    app = create_app(Settings(data_dir=tmp_path,testing=True))
    with TestClient(app) as client:
        signup(client,'dicomowner')
        response = client.post('/api/mri/predict',files={'file':('fixture.dcm',content,'application/dicom')})
        assert response.status_code == 201,response.text
        result = response.json()
        assert 'Fixture^MetadataOnly' not in response.text
        assert 'TEST-ONLY-PATIENT' not in response.text
        image_response = client.get(f'/api/mri/{result["id"]}/image')
        assert image_response.status_code == 200
        assert b'TEST-ONLY-PATIENT' not in image_response.content
        with Image.open(BytesIO(image_response.content)) as stored:
            assert stored.format == 'PNG'
            assert stored.info == {}
            assert stored.getexif() == {}
        report = client.get(f'/api/mri/{result["id"]}/report').json()
        import hashlib
        assert report['source_sha256'] == hashlib.sha256(content).hexdigest()
        assert report['result']['kind'] == 'model_prediction'
        assert len(list((tmp_path/'mri').iterdir())) == 1
