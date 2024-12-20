import os
import sys
from pathlib import Path

import h5py
import hdf5plugin
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal
from scipy.stats import describe

# Define chunk size and max data size
CHUNK_SIZE = 1000  # Adjust this based on your available memory
MAX_DATA_SIZE = 1e7  # 1 GB, adjust as needed

# Define output directory
OUTPUT_DIR = Path("/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# Redirect print output to a file
class PrintRedirect:
    def __init__(self, filename):
        self.output_file = open(filename, "w")
        self.stdout = sys.stdout

    def write(self, text):
        self.stdout.write(text)
        self.output_file.write(text)

    def flush(self):
        self.stdout.flush()
        self.output_file.flush()

    def close(self):
        self.output_file.close()


def analyze_scientific_data(h5file):
    """
    Perform various analyses on scientific data stored in an HDF5 file.
    :param h5file: An open h5py File object
    :return: A dictionary containing analysis results
    """
    results = {}

    # Get dataset info
    data_shape = h5file["data"].shape
    total_size = np.prod(data_shape)

    scale_factor = 1

    # Cap the data size
    if total_size > MAX_DATA_SIZE:
        scale_factor = (MAX_DATA_SIZE / total_size) ** (1 / len(data_shape))
        new_shape = tuple(max(1, int(dim * scale_factor)) for dim in data_shape)
        print(f"Data capped from {data_shape} to {new_shape}")
    else:
        print(f"Data size is {total_size}")
        new_shape = data_shape

    # Prepare for chunked reading
    chunks = [range(0, dim, max(1, min(CHUNK_SIZE, dim))) for dim in new_shape]

    # Initialize aggregators
    data_sum = np.zeros(new_shape[1:])
    data_sum_sq = np.zeros(new_shape[1:])
    count = 0

    # Process data in chunks
    for chunk_start in chunks[0]:
        chunk_end = min(chunk_start + CHUNK_SIZE, new_shape[0])
        chunk_slice = (slice(chunk_start, chunk_end),) + tuple(
            slice(None, dim) for dim in new_shape[1:]
        )

        chunk_data = h5file["data"][chunk_slice]

        # Use slicing instead of resizing
        if chunk_data.shape[1:] != new_shape[1:]:
            chunk_data = chunk_data[:, : new_shape[1], : new_shape[2]]

        data_sum += np.sum(chunk_data, axis=0)
        data_sum_sq += np.sum(chunk_data**2, axis=0)
        count += chunk_data.shape[0]

    # Calculate mean and variance
    data_mean = data_sum / count
    data_var = (data_sum_sq / count) - (data_mean**2)

    # Basic statistical analysis
    results["basic_stats"] = {
        "mean": np.mean(data_mean),
        "variance": np.mean(data_var),
        "min": np.min(data_mean),
        "max": np.max(data_mean),
    }

    # Frequency analysis
    results["frequency_analysis"] = frequency_analysis(data_mean)

    # Signal-to-noise ratio
    results["snr"] = calculate_snr(data_mean, np.sqrt(data_var))

    # Time series analysis
    results["time_series"] = time_series_analysis(
        h5file["data"], new_shape, scale_factor
    )

    # Spectral analysis
    results["spectral_analysis"] = spectral_analysis(data_mean)

    # Create plots
    results["plots"] = create_plots(h5file, new_shape, scale_factor)

    return results


def frequency_analysis(data):
    """Perform frequency analysis on the data."""
    fft_result = np.fft.fft(data)
    fft_freq = np.fft.fftfreq(len(data))
    dominant_freq_idx = np.argmax(np.abs(fft_result))
    dominant_freq = fft_freq[dominant_freq_idx]
    return {
        "dominant_frequency": dominant_freq,
        "fft_result": np.abs(fft_result),
        "fft_freq": fft_freq,
    }


def spectral_analysis(data):
    """Perform spectral analysis on the data."""
    freqs, psd = signal.welch(data)
    return {"spectrum": data, "freqs": freqs, "psd": psd}


def calculate_snr(signal, noise):
    """Calculate the signal-to-noise ratio."""
    signal_power = np.mean(signal**2)
    noise_power = np.mean(noise**2)
    snr = 10 * np.log10(signal_power / noise_power)
    return snr


def create_plots(h5file, new_shape, scale_factor):
    """Create and save all plots."""
    plots = {}

    time_axis = np.arange(new_shape[0])
    freq_axis = np.linspace(
        h5file["data"].attrs.get("fch1", 0),
        h5file["data"].attrs.get("fch1", 0)
        + h5file["data"].attrs.get("foff", 1) * new_shape[-1],
        new_shape[-1],
    )

    # Create plots that can work with chunked data
    plots["average_spectrum"] = plot_average_spectrum(
        h5file["data"], freq_axis, new_shape, scale_factor
    )
    plots["time_series"] = plot_time_series(
        h5file["data"], time_axis, new_shape, scale_factor
    )
    plots["intensity_histogram"] = plot_intensity_histogram(
        h5file["data"], new_shape, scale_factor
    )

    return plots


def plot_average_spectrum(
    dataset, freq_axis, new_shape, scale_factor, title="Average Power Spectrum"
):
    fig, ax = plt.subplots(figsize=(10, 6))

    avg_spectrum = np.zeros(new_shape[-1])
    count = 0
    for i in range(0, new_shape[0], CHUNK_SIZE):
        chunk_end = min(i + CHUNK_SIZE, new_shape[0])
        chunk = dataset[i : chunk_end : int(1 / scale_factor)]
        if chunk.shape[1:] != new_shape[1:]:
            chunk = chunk[:, : new_shape[1], : new_shape[2]]
        avg_spectrum += np.sum(chunk, axis=(0, 1))
        count += chunk.shape[0]
    avg_spectrum /= count

    ax.plot(freq_axis, avg_spectrum)
    ax.set_xlabel("Frequency")
    ax.set_ylabel("Average Power")
    ax.set_title(title)
    plt.tight_layout()
    return fig


def plot_intensity_histogram(
    dataset, new_shape, scale_factor, title="Histogram of Intensity Values"
):
    fig, ax = plt.subplots(figsize=(10, 6))

    intensities = []
    for i in range(0, new_shape[0], CHUNK_SIZE):
        chunk_end = min(i + CHUNK_SIZE, new_shape[0])
        chunk = dataset[i : chunk_end : int(1 / scale_factor)]
        if chunk.shape[1:] != new_shape[1:]:
            chunk = chunk[:, : new_shape[1], : new_shape[2]]
        intensities.extend(chunk.flatten())

    ax.hist(intensities, bins=100, edgecolor="black")
    ax.set_xlabel("Intensity")
    ax.set_ylabel("Count")
    ax.set_title(title)
    plt.tight_layout()
    return fig


def plot_time_series(
    dataset, time_axis, new_shape, scale_factor, title="Time Series of Total Power"
):
    fig, ax = plt.subplots(figsize=(10, 6))

    total_power = np.zeros(new_shape[0])
    for i in range(0, new_shape[0], CHUNK_SIZE):
        chunk_end = min(i + CHUNK_SIZE, new_shape[0])
        chunk = dataset[i : chunk_end : int(1 / scale_factor)]
        if chunk.shape[1:] != new_shape[1:]:
            chunk = chunk[:, : new_shape[1], : new_shape[2]]
        chunk_power = np.sum(chunk, axis=(1, 2))
        total_power[i : i + len(chunk_power)] = chunk_power

    ax.plot(time_axis, total_power)
    ax.set_xlabel("Time")
    ax.set_ylabel("Total Power")
    ax.set_title(title)
    plt.tight_layout()
    return fig


def time_series_analysis(dataset, new_shape, scale_factor):
    """Perform time series analysis on the data."""
    time_series = np.zeros(new_shape[0])
    for i in range(0, new_shape[0], CHUNK_SIZE):
        chunk_end = min(i + CHUNK_SIZE, new_shape[0])
        chunk = dataset[i : chunk_end : int(1 / scale_factor)]
        if chunk.shape[1:] != new_shape[1:]:
            chunk = chunk[:, : new_shape[1], : new_shape[2]]

        # Ensure we don't exceed the time_series array bounds
        chunk_mean = np.mean(chunk, axis=(1, 2))
        time_series[i : i + len(chunk_mean)] = chunk_mean

    window_size = min(10, len(time_series) // 10)
    moving_average = np.convolve(
        time_series, np.ones(window_size) / window_size, mode="valid"
    )
    peaks, _ = signal.find_peaks(time_series, height=np.mean(time_series))
    return {
        "time_series": time_series,
        "moving_average": moving_average,
        "peaks": peaks,
    }


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
        output_path = OUTPUT_DIR / f"{plot_name}.png"
        print(f"- {plot_name}")
        fig.savefig(output_path)
        plt.close(fig)
    print(f"Plots have been saved as PNG files in {OUTPUT_DIR}")


if __name__ == "__main__":
    file_path = os.environ.get("FILE_PATH")

    if file_path is None:
        print("FILE_PATH environment variable is not set.")
        sys.exit(1)

    p = Path(file_path)

    # Redirect print output to a file
    output_file = OUTPUT_DIR / "analysis_output.txt"
    redirect = PrintRedirect(output_file)
    sys.stdout = redirect

    try:
        with h5py.File(p.absolute(), "r") as f:
            results = analyze_scientific_data(f)
            print_summary(results)
    finally:
        # Restore original stdout and close the output file
        sys.stdout = sys.__stdout__
        redirect.close()

    print(f"Analysis complete. Output saved to {OUTPUT_DIR}")
