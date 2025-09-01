#**********************************************************************************************
# FileName     : Compare2BinsPlots.py

# Description  : This file implements two bins files post proccessing and comparation.

#**********************************************************************************************


import numpy as np
import matplotlib.pyplot as plt
from mmwave.dataloader import DCA1000
import os

def RageProfileFFTComparation(AdcData1, AdcData2, ADC_PARAMS, FrameIdx=0, Data1Str='File 1', Data2Str='File 2', SavePrefix="RangeProfileFFT"):
    """
    Plots the range profile FFT for a specific frame for two datasets, overlayed for comparison.
    adc_data1, adc_data2: ndarray of shape (frames, chirps, tx, rx, samples)
    """
    # Select frame
    Fram1 = AdcData1[FrameIdx]  # (chirps, tx, rx, samples)
    Frame2 = AdcData2[FrameIdx]

    # Apply window (Kaiser, beta=4)
    window = np.kaiser(ADC_PARAMS['samples'], 4)
    Frame1Win = Fram1[10] * window
    Frame2Win = Frame2[10] * window

    # FFT along last axis (samples)
    range_fft1 = np.fft.fft(Frame1Win, axis=-1)
    range_fft2 = np.fft.fft(Frame2Win, axis=-1)

    # Range resolution and bins
    chirp_bandwidth = (ADC_PARAMS['freq_slope'] * 1e12 * ADC_PARAMS['samples']) / (ADC_PARAMS['sample_rate'] * 1e3)
    range_res = 3e8 / (2 * chirp_bandwidth)
    ranges = np.round(np.arange(ADC_PARAMS['samples']) * range_res, 2)

    # Range profile: sum over tx, rx
    range_profile1 = np.abs(range_fft1).sum(axis=(0,1))
    range_profile2 = np.abs(range_fft2).sum(axis=(0,1))
    range_profile_db1 = 20 * np.log10(range_profile1 + 1e-12)
    range_profile_db2 = 20 * np.log10(range_profile2 + 1e-12)

    plt.figure(figsize=(10, 6))
    plt.plot(ranges, range_profile_db1, color='b', linewidth=2, label=Data1Str)
    plt.plot(ranges, range_profile_db2, color='r', linewidth=1, label=Data2Str)
    plt.title(f"Range Profile FFT Comparison (frame {FrameIdx})")
    plt.xlabel("Range (m)")
    plt.ylabel("Magnitude (dB)")
    plt.grid(True)
    plt.legend()
    plt.savefig(f"{SavePrefix}_Compare.png")
    plt.show()
    plt.close()

def LoadDataBin(bin_file, ADC_PARAMS):

    print(f"====Reading file: {bin_file}====")

    expected_size = ADC_PARAMS['chirps'] * ADC_PARAMS['tx'] * ADC_PARAMS['samples'] * ADC_PARAMS['IQ'] * ADC_PARAMS['rx']
    print(f"chirps: {ADC_PARAMS['chirps']}, tx: {ADC_PARAMS['tx']}, samples: {ADC_PARAMS['samples']}, IQ: {ADC_PARAMS['IQ']}, rx: {ADC_PARAMS['rx']}")
    print(f"Expected size per frame: {expected_size}")

    file_size = os.path.getsize(bin_file)
    print(f"Actual file size (bytes): {file_size}")
    adc_data = np.fromfile(bin_file, dtype=np.int16)
    num_frames = adc_data.size // expected_size
    print(f"Calculated number of frames: {num_frames}")
    if adc_data.size % expected_size != 0:
        print(f"Warning: file size is not a multiple of expected frame size!")
    adc_data = adc_data[:num_frames * expected_size]
    print(f"Reshaping to: (num_frames={num_frames}, chirps={ADC_PARAMS['chirps']}, tx={ADC_PARAMS['tx']}, samples={ADC_PARAMS['samples']}, IQ={ADC_PARAMS['IQ']}, rx={ADC_PARAMS['rx']})")
    adc_data = np.reshape(adc_data, (num_frames, ADC_PARAMS['chirps'], ADC_PARAMS['tx'], ADC_PARAMS['samples'], ADC_PARAMS['IQ'], ADC_PARAMS['rx']))
    print(f"Shape after reshape: {adc_data.shape}")
    print(f"transposing to: (frames={num_frames}, chirps={ADC_PARAMS['chirps']}, tx={ADC_PARAMS['tx']}, rx={ADC_PARAMS['rx']}, samples={ADC_PARAMS['samples']}, IQ={ADC_PARAMS['IQ']})")
    adc_data = np.transpose(adc_data, (0, 1, 2, 5, 3, 4))  # (frames, chirps, tx, rx, samples, IQ)
    print(f"Shape after transpose: {adc_data.shape}")
    adc_data = (1j * adc_data[..., 1] + adc_data[..., 0]).astype(np.complex64)  # (frames, chirps, tx, rx, samples)
    print(f"Shape after IQ combine: {adc_data.shape}")

    return adc_data

def TimeDomainComparation(AdcData1, AdcData2, FrameIdx=0, ChirpIdx=0, tx=0, rx=0, Data1Str='File 1', Data2Str='File 2', save_prefix="compare"):
    """
    Plots time-domain IQ waveforms from two ADC datasets on the same plot.
    """
    frame1 = AdcData1[FrameIdx]  # (chirps, tx, rx, samples)
    frame2 = AdcData2[FrameIdx]

    iq1 = frame1[ChirpIdx,tx,rx,:]   # (samples)
    iq2 = frame2[ChirpIdx,tx,rx,:]   # (samples)

    evm_value = evm_percent(iq1, iq2)
    

    plt.figure(figsize=(10,6))
    plt.plot(np.real(iq1), label=Data1Str + " Real", color='b', linewidth=3)
    plt.plot(np.imag(iq1), label=Data1Str + " Imaginary", color='b', linestyle='--', linewidth=3)
    plt.plot(np.real(iq2), label=Data2Str + " Real", color='r')
    plt.plot(np.imag(iq2), label=Data2Str + " Imaginary", color='r', linestyle='--')
    plt.legend(loc="upper right")
    plt.text(0.05, 0.95, f"EVM Diff = {evm_value:.2f}%", transform=plt.gca().transAxes,fontsize=12, color="black",verticalalignment="top")
    plt.title(f"Time-domain IQ Comparison (frame {FrameIdx}, chirp {ChirpIdx}, rx {rx}, tx {tx})")
    plt.xlabel("Sample Index")
    plt.ylabel("Amplitude")
    plt.grid(True)
    plt.savefig(f"{save_prefix}_IQ_frame{FrameIdx}_IQ_chirp{ChirpIdx}.png")
    plt.show()
    plt.close()

def evm_percent(x_yours: np.ndarray, x_ti: np.ndarray) -> float:
    """
    Compute complex EVM% across all samples (all chirps × all RX).
    Inputs should be same-shape complex arrays (e.g., complex64).
    """
    if x_yours.shape != x_ti.shape:
        raise ValueError(f"Shape mismatch: {x_yours.shape} vs {x_ti.shape}")
    # Convert to complex (no-op if already complex)
    x_yours_c = x_yours.astype(np.complex64, copy=False)
    x_ti_c    = x_ti.astype(np.complex64, copy=False)

    num = np.sum(np.abs(x_yours_c - x_ti_c)**2, dtype=np.float64)
    den = np.sum(np.abs(x_ti_c)**2, dtype=np.float64)
    if den == 0:
        return 0.0 if num == 0 else np.inf
    return 100.0 * np.sqrt(num / den)

if __name__ == "__main__":
    # --- User: set your file paths here ---
    OurBin = "Test_2025-08-25-19-26-54/raw_data.bin"                                    # <-- Change to your first .bin file
    TIBin = "C:\\ti\\mmwave_studio_03_00_00_14\\mmWaveStudio\\PostProc\\adc_data.bin"   # <-- Change to your second .bin file
    cfg_file = "configFiles/AWR2243_mmwaveconfig.txt"                                   # <-- Change to your configuration file  

    # --- User: set your parameters here ---
    FrameIdx = 2                                                                        # Frame index to analyze
    ChirpIdx = 85                                                                      # Chirp index to analyze        (for time-domain plot)          
    tx = 0                                                                              # Transmitter index to analyze  (for time-domain plot)
    rx = 0                                                                              # Receiver index to analyze     (for time-domain plot)

    _, _, ADC_PARAMS, CFG_PARAMS = DCA1000.AWR2243_read_config(cfg_file)
    
    OurData = LoadDataBin(OurBin, ADC_PARAMS)
    TiData  = LoadDataBin(TIBin, ADC_PARAMS)


    TimeDomainComparation(OurData, TiData, FrameIdx=FrameIdx,  ChirpIdx=ChirpIdx, tx=tx, rx=rx, Data1Str="Our Script", Data2Str="TI", save_prefix="comp")
    RageProfileFFTComparation(OurData, TiData, ADC_PARAMS, FrameIdx=FrameIdx, Data1Str='Our Script', Data2Str='TI', SavePrefix="range_profile_")
