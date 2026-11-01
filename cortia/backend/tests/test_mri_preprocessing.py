import numpy as np
import pytest
from PIL import Image

from cortia.mri.preprocessing import preprocess, display_pixels, description


@pytest.mark.parametrize('contract, expected',[
    ('legacy_rgb_0_1',[0.,127/255,1.]),
    ('mobilenet_v2',[-1.,127/127.5-1,1.]),
])
def test_declared_contract_normalizes_exact_rgb_values(contract,expected):
    tensor = preprocess(Image.new('RGB',(224,224),(0,127,255)),contract)
    assert tensor.shape == (1,224,224,3)
    assert tensor.dtype == np.float32
    assert tensor[0,0,0].tolist() == pytest.approx(expected)
    assert display_pixels(tensor,contract)[0,0].tolist() == pytest.approx([0.,127/255,1.])


def test_unknown_preprocessing_fails_instead_of_guessing():
    image = Image.new('RGB',(224,224))
    for function,args in ((preprocess,(image,'unknown')),
                          (display_pixels,(np.zeros((1,224,224,3)),'unknown')),
                          (description,('unknown',))):
        with pytest.raises(ValueError,match='preprocessing'):
            function(*args)


def test_signed_contract_is_identified_in_report_description():
    assert '/127.5 - 1' in description('mobilenet_v2')
    assert '/255' in description('legacy_rgb_0_1')
