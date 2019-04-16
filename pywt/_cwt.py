import numpy as np

from ._extensions._pywt import (DiscreteContinuousWavelet, ContinuousWavelet,
                                Wavelet, _check_dtype)
from ._functions import integrate_wavelet, scale2frequency

__all__ = ["cwt"]


def cwt(data, scales, wavelet, sampling_period=1., method='conv'):
    """
    cwt(data, scales, wavelet)

    One dimensional Continuous Wavelet Transform.

    Parameters
    ----------
    data : array_like
        Input signal
    scales : array_like
        The wavelet scales to use. One can use
        ``f = scale2frequency(scale, wavelet)/sampling_period`` to determine
        what physical frequency, ``f``. Here, ``f`` is in hertz when the
        ``sampling_period`` is given in seconds.
    wavelet : Wavelet object or name
        Wavelet to use
    sampling_period : float
        Sampling period for the frequencies output (optional).
        The values computed for ``coefs`` are independent of the choice of
        ``sampling_period`` (i.e. ``scales`` is not scaled by the sampling
        period).
    method : {'conv', 'fft', 'auto'}, optional
        The method used to compute the CWT. Can be any of:
            - ``conv`` uses ``numpy.convolve``.
            - ``fft`` uses frequency domain convolution via ``numpy.fft.fft``.
            - ``auto`` uses automatic selection based on an estimate of the
              computational complexity at each scale.
        The ``conv`` method complexity is ``O(len(scale) * len(data))``.
        The ``fft`` method is ``O(N * log2(N))`` with
        ``N = len(scale) + len(data) - 1``. It is well suited for large size
        signals but slower than ``conv`` on small ones.

    Returns
    -------
    coefs : array_like
        Continuous wavelet transform of the input signal for the given scales
        and wavelet
    frequencies : array_like
        If the unit of sampling period are seconds and given, than frequencies
        are in hertz. Otherwise, a sampling period of 1 is assumed.

    Notes
    -----
    Size of coefficients arrays depends on the length of the input array and
    the length of given scales.

    Examples
    --------
    >>> import pywt
    >>> import numpy as np
    >>> import matplotlib.pyplot as plt
    >>> x = np.arange(512)
    >>> y = np.sin(2*np.pi*x/32)
    >>> coef, freqs=pywt.cwt(y,np.arange(1,129),'gaus1')
    >>> plt.matshow(coef) # doctest: +SKIP
    >>> plt.show() # doctest: +SKIP
    ----------
    >>> import pywt
    >>> import numpy as np
    >>> import matplotlib.pyplot as plt
    >>> t = np.linspace(-1, 1, 200, endpoint=False)
    >>> sig  = np.cos(2 * np.pi * 7 * t) + np.real(np.exp(-7*(t-0.4)**2)*np.exp(1j*2*np.pi*2*(t-0.4)))
    >>> widths = np.arange(1, 31)
    >>> cwtmatr, freqs = pywt.cwt(sig, widths, 'mexh')
    >>> plt.imshow(cwtmatr, extent=[-1, 1, 1, 31], cmap='PRGn', aspect='auto',
    ...            vmax=abs(cwtmatr).max(), vmin=-abs(cwtmatr).max())  # doctest: +SKIP
    >>> plt.show() # doctest: +SKIP
    """

    # accept array_like input; make a copy to ensure a contiguous array
    dt = _check_dtype(data)
    data = np.array(data, dtype=dt)
    if not isinstance(wavelet, (ContinuousWavelet, Wavelet)):
        wavelet = DiscreteContinuousWavelet(wavelet)
    if np.isscalar(scales):
        scales = np.array([scales])
    dt_out = None  # TODO: fix in/out dtype consistency in a subsequent PR
    if data.ndim == 1:
        if wavelet.complex_cwt:
            dt_out = complex
        out = np.zeros((np.size(scales), data.size), dtype=dt_out)
        precision = 10
        int_psi, x = integrate_wavelet(wavelet, precision=precision)

        if method in ('auto', 'fft'):
            # - to be as large as the sum of data length and and maximum
            #   wavelet support to avoid circular convolution effects
            # - additional padding to reach a power of 2 for CPU-optimal FFT
            size_pad = lambda s: 2**np.int(np.ceil(np.log2(s[0] + s[1])))
            size_scale0 = size_pad((len(data),
                                    np.take(scales, 0) * ((x[-1] - x[0]) + 1)))
            fft_data = None
        elif not method == 'conv':
            raise ValueError("method must be in: 'conv', 'fft' or 'auto'")

        for i in np.arange(np.size(scales)):
            step = x[1] - x[0]
            j = np.floor(
                np.arange(scales[i] * (x[-1] - x[0]) + 1) / (scales[i] * step))
            if np.max(j) >= np.size(int_psi):
                j = np.delete(j, np.where((j >= np.size(int_psi)))[0])
            int_psi_scale = int_psi[j.astype(np.int)][::-1]

            if method == 'conv':
                conv = np.convolve(data, int_psi_scale)
            else:
                size_scale = size_pad((len(data), len(int_psi_scale)))
                if size_scale != size_scale0:
                    # the fft of data changes when padding size changes thus
                    # it has to be recomputed
                    fft_data = None
                size_scale0 = size_scale
                nops_conv = len(data) * len(int_psi_scale)
                nops_fft = (2 + (fft_data is None))
                nops_fft *= size_scale * np.log2(size_scale)
                if (method == 'fft') or (
                        (method == 'auto') and (nops_fft < nops_conv)):
                    if fft_data is None:
                        fft_data = np.fft.fft(data, size_scale)
                    fft_wav = np.fft.fft(int_psi_scale, size_scale)
                    conv = np.fft.ifft(fft_wav * fft_data)
                    conv = conv[:data.size + int_psi_scale.size - 1]
                else:
                    conv = np.convolve(data, int_psi_scale)

            coef = - np.sqrt(scales[i]) * np.diff(conv)
            if not np.iscomplexobj(out):
                coef = np.real(coef)
            d = (coef.size - data.size) / 2.
            if d > 0:
                out[i, :] = coef[int(np.floor(d)):int(-np.ceil(d))]
            elif d == 0.:
                out[i, :] = coef
            else:
                raise ValueError(
                    "Selected scale of {} too small.".format(scales[i]))
        frequencies = scale2frequency(wavelet, scales, precision)
        if np.isscalar(frequencies):
            frequencies = np.array([frequencies])
        for i in np.arange(len(frequencies)):
            frequencies[i] /= sampling_period
        return out, frequencies
    else:
        raise ValueError("Only dim == 1 supported")
