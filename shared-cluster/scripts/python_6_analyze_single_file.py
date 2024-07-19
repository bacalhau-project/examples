import os
import sys
from pathlib import Path

import h5py
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal
from scipy.stats import describe


def analyze_scientific_data(h5file):
    """
    Perform various analyses on scientific data stored in an HDF5 file.
    :param h5file: An open h5py File object
    :return: A dictionary containing analysis results
    """
    results = {}

    # Assuming 'data' is your main dataset
    data = h5file["data"][:]

    # Basic statistical analysis
    results["basic_stats"] = basic_statistical_analysis(data)

    # Frequency analysis
    results["frequency_analysis"] = frequency_analysis(data)

    # Signal-to-noise ratio
    results["snr"] = calculate_snr(data)

    # Time series analysis
    results["time_series"] = time_series_analysis(data)

    # Spectral analysis
    results["spectral_analysis"] = spectral_analysis(data)

    # Create plots
    results["plots"] = create_plots(h5file)

    return results


def basic_statistical_analysis(data):
    """Perform basic statistical analysis on the data."""
    stats = describe(data.flatten())
    return {
        "mean": stats.mean,
        "variance": stats.variance,
        "skewness": stats.skewness,
        "kurtosis": stats.kurtosis,
        "min": stats.minmax[0],
        "max": stats.minmax[1],
    }


def frequency_analysis(data):
    """Perform frequency analysis on the data."""
    freq_data = np.mean(data, axis=(0, 1))
    fft_result = np.fft.fft(freq_data)
    fft_freq = np.fft.fftfreq(len(freq_data))
    dominant_freq_idx = np.argmax(np.abs(fft_result))
    dominant_freq = fft_freq[dominant_freq_idx]
    return {
        "dominant_frequency": dominant_freq,
        "fft_result": np.abs(fft_result),
        "fft_freq": fft_freq,
    }


def calculate_snr(data):
    """Calculate the signal-to-noise ratio."""
    signal_power = np.mean(data**2)
    noise = data - np.mean(data)
    noise_power = np.mean(noise**2)
    snr = 10 * np.log10(signal_power / noise_power)
    return snr


def time_series_analysis(data):
    """Perform time series analysis on the data."""
    time_series = np.mean(data, axis=(1, 2))
    window_size = 10
    moving_average = np.convolve(
        time_series, np.ones(window_size) / window_size, mode="valid"
    )
    peaks, _ = signal.find_peaks(time_series, height=np.mean(time_series))
    return {
        "time_series": time_series,
        "moving_average": moving_average,
        "peaks": peaks,
    }


def spectral_analysis(data):
    """Perform spectral analysis on the data."""
    spectrum = np.mean(data, axis=0).squeeze()
    freqs, psd = signal.welch(spectrum)
    return {"spectrum": spectrum, "freqs": freqs, "psd": psd}


def create_plots(h5file):
    """Create and save all plots."""
    data = h5file["data"][:]
    time_axis = np.arange(data.shape[0])
    freq_axis = np.linspace(
        h5file["data"].attrs.get("fch1", 0),
        h5file["data"].attrs.get("fch1", 0)
        + h5file["data"].attrs.get("foff", 1) * data.shape[2],
        data.shape[2],
    )

    plots = {}
    plots["spectrogram"] = plot_spectrogram(data, time_axis, freq_axis)
    plots["average_spectrum"] = plot_average_spectrum(data, freq_axis)
    plots["time_series"] = plot_time_series(data, time_axis)
    plots["waterfall"] = plot_waterfall(data, time_axis, freq_axis)
    plots["intensity_histogram"] = plot_intensity_histogram(data)
    plots["snr_over_time"] = plot_snr_over_time(data, time_axis)
    plots["dedispersed_time_series"] = plot_dedispersed_time_series(
        data, time_axis, freq_axis, 56.7, freq_axis[-1]
    )

    return plots


def plot_spectrogram(data, time_axis, freq_axis, title="Spectrogram"):
    fig, ax = plt.subplots(figsize=(12, 8))
    im = ax.imshow(
        data.T,
        aspect="auto",
        origin="lower",
        extent=[time_axis[0], time_axis[-1], freq_axis[0], freq_axis[-1]],
    )
    plt.colorbar(im, ax=ax, label="Intensity")
    ax.set_xlabel("Time")
    ax.set_ylabel("Frequency")
    ax.set_title(title)
    plt.tight_layout()
    return fig


def plot_average_spectrum(data, freq_axis, title="Average Power Spectrum"):
    fig, ax = plt.subplots(figsize=(10, 6))
    avg_spectrum = np.mean(data, axis=0)
    ax.plot(freq_axis, avg_spectrum)
    ax.set_xlabel("Frequency")
    ax.set_ylabel("Average Power")
    ax.set_title(title)
    plt.tight_layout()
    return fig


def plot_time_series(data, time_axis, title="Time Series of Total Power"):
    fig, ax = plt.subplots(figsize=(10, 6))
    total_power = np.sum(data, axis=1)
    ax.plot(time_axis, total_power)
    ax.set_xlabel("Time")
    ax.set_ylabel("Total Power")
    ax.set_title(title)
    plt.tight_layout()
    return fig


def plot_waterfall(data, time_axis, freq_axis, title="Waterfall Plot"):
    fig, ax = plt.subplots(figsize=(12, 8))
    im = ax.imshow(
        data,
        aspect="auto",
        origin="lower",
        extent=[time_axis[0], time_axis[-1], freq_axis[0], freq_axis[-1]],
    )
    plt.colorbar(im, ax=ax, label="Intensity")
    ax.set_xlabel("Time")
    ax.set_ylabel("Frequency")
    ax.set_title(title)
    plt.tight_layout()
    return fig


def plot_intensity_histogram(data, title="Histogram of Intensity Values"):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(data.flatten(), bins=100, edgecolor="black")
    ax.set_xlabel("Intensity")
    ax.set_ylabel("Count")
    ax.set_title(title)
    plt.tight_layout()
    return fig


def plot_snr_over_time(data, time_axis, title="SNR over Time"):
    fig, ax = plt.subplots(figsize=(10, 6))
    snr = []
    for i in range(data.shape[0]):
        signal_power = np.mean(data[i] ** 2)
        noise = data[i] - np.mean(data[i])
        noise_power = np.mean(noise**2)
        snr.append(10 * np.log10(signal_power / noise_power))
    ax.plot(time_axis, snr)
    ax.set_xlabel("Time")
    ax.set_ylabel("SNR (dB)")
    ax.set_title(title)
    plt.tight_layout()
    return fig


def plot_dedispersed_time_series(
    data, time_axis, freq_axis, dm, f_ref, title="Dedispersed Time Series"
):
    fig, ax = plt.subplots(figsize=(10, 6))

    def delay(f, dm, f_ref):
        return 4.148808 * 1e3 * dm * (1 / f**2 - 1 / f_ref**2)

    dedispersed = np.zeros_like(data)
    for i, f in enumerate(freq_axis):
        shift = int(delay(f, dm, f_ref) / (time_axis[1] - time_axis[0]))
        dedispersed[:, i] = np.roll(data[:, i], -shift)
    dedispersed_sum = np.sum(dedispersed, axis=1)
    ax.plot(time_axis, dedispersed_sum)
    ax.set_xlabel("Time")
    ax.set_ylabel("Intensity")
    ax.set_title(title)
    plt.tight_layout()
    return fig


def print_summary(results):
    print("\nBasic Statistics:")
    for key, value in results["basic_stats"].items():
        print(f"{key}: {value}")

    print("\nFrequency Analysis:")
    print(f"Dominant Frequency: {results['frequency_analysis']['dominant_frequency']}")

    print(f"\nSignal-to-Noise Ratio: {results['snr']} dB")

    print("\nTime Series Analysis:")
    print(f"Number of peaks detected: {len(results['time_series']['peaks'])}")

    print("\nSpectral Analysis:")
    print(f"Number of frequency bins: {len(results['spectral_analysis']['freqs'])}")

    print("\nGenerated Plots:")
    for plot_name, fig in results["plots"].items():
        print(f"- {plot_name}")
        fig.savefig(f"{plot_name}.png")
        plt.close(fig)
    print("Plots have been saved as PNG files in the current directory.")


if __name__ == "__main__":
    file_path = os.environ.get("FILE_PATH")

    if file_path is None:
        print("FILE_PATH environment variable is not set.")
        sys.exit(1)

    HDF5_PLUGIN_PATH = os.environ.get("HDF5_PLUGIN_PATH")
    if HDF5_PLUGIN_PATH is None:
        print("HDF5_PLUGIN_PATH environment variable is not set.")
        sys.exit(1)
    else:
        print(f"HDF5_PLUGIN_PATH: {HDF5_PLUGIN_PATH}")

    p = Path(file_path)

    with h5py.File(p.absolute(), "r") as f:
        results = analyze_scientific_data(f)
        print_summary(results)
