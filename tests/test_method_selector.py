"""Only explicit string selectors can choose the research operator."""
import numpy as np
import pytest

from dranalyser.dsp.core import sliding_dft


def test_numpy_array_cannot_silently_choose_research_operator():
    t = np.arange(200)/3500
    with pytest.raises(ValueError):
        sliding_dft(np.ones(200), t, 3500, 48, method=np.array(['basis']))


def test_numpy_scalar_string_retains_physical_basis_result():
    t = np.arange(200)/3500
    x = np.sqrt(2)*np.real((10-2j)*np.exp(2j*np.pi*48*t))
    result = sliding_dft(x, t, 3500, 48, method=np.str_('basis'))
    np.testing.assert_allclose(result[72:], 10-2j, rtol=0, atol=1e-10)
