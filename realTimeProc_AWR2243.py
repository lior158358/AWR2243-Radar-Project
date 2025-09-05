import traceback
import time
from mmwave.dataloader import DCA1000
# import fpga_udp;fpga_udp.AWR2243_firmwareDownload()
import fpga_udp as radar
import numpy as np
import datetime
import matplotlib.pyplot as plt
import os
'''
# General process for collecting raw data with AWR2243
1. Reset the radar and DCA1000 (reset_radar, reset_fpga)
2. Initialize the radar via SPI and configure the corresponding parameters (AWR2243_init, AWR2243_setFrameCfg) (requires root privileges on Linux)
3. Send FPGA configuration commands via Ethernet UDP (config_fpga)
4. Send record data packet configuration commands via Ethernet UDP (config_record)
5. Send start capture commands via Ethernet UDP (stream_start)
6. Start the radar via SPI (AWR2243_sensorStart)
7. Loop to receive UDP data packets + parse raw data + real-time data processing (fastRead_in_Cpp, postProc)
8.1. (optional, required if numFrame == 0) Stop the radar via SPI (AWR2243_sensorStop)
8.2. (optional, not allowed if numFrame == 0) Wait for the radar to finish capturing (AWR2243_waitSensorStop)
9. (optional, required if numFrame == 0) Send stop capture commands via Ethernet UDP (stream_stop)
10. Turn off radar power and configuration files via SPI (AWR2243_poweroff)

# Requirements for the "mmwaveconfig.txt" millimeter-wave radar configuration file
TBD

# Requirements for the "cf.json" data acquisition card configuration file
For specific information, refer to TI_DCA1000EVM_CLI_Software_UserGuide.pdf
LVDS Mode:
LVDS mode specifies the lane configuration for LVDS. This field is valid only when dataTransferMode is "LVDSCapture".
The valid options are:
• 1 (4 lanes)
• 2 (2 lanes)
Packet delay:
Under default conditions, Ethernet throughput varies up to 325 Mbps speed with a 25-µs Ethernet packet delay. 
The user can change the Ethernet packet delay from 5 µs to 500 µs to achieve different throughputs.
"packetDelay_us":  5 (us)   ~   706 (Mbps)
"packetDelay_us": 10 (us)   ~   545 (Mbps)
"packetDelay_us": 25 (us)   ~   325 (Mbps)
"packetDelay_us": 50 (us)   ~   193 (Mbps)
'''

def PrintCalcParams(ADC_PARAMS):

    # Calculating bandwidth of the chirp, accounting for unit conversion
    chirp_bandwidth = (ADC_PARAMS['freq_slope'] * 1e12 * ADC_PARAMS['samples']) / (ADC_PARAMS['sample_rate'] * 1e3)
    # Using our derived equation for range resolution
    range_res = 3e8 / (2 * chirp_bandwidth)
    print(f'Range Resolution: {range_res} [meters]')

    # Max range calculation
    max_range = np.round(np.arange(ADC_PARAMS['samples']) * range_res, 2)[-1]
    print(f'Max Range: {max_range} [meters]')

    StartWaveLenght = (3e8 / (ADC_PARAMS['startFreq'] * 1e9))
    TimeChirp = 1e-6 *(ADC_PARAMS['idleTime'] + ADC_PARAMS['rampEndTime'])
    TimeFrame = TimeChirp * ADC_PARAMS['chirps']
    VelocityRes = (StartWaveLenght) / (2 * (TimeFrame))
    print(f'Velocity Resolution: {VelocityRes} [meters/sec]')
    MaxVelocity = StartWaveLenght / (4 * TimeChirp)
    print(f'Max Velocity: {MaxVelocity} [meters/sec]')

def postProc(adc_data, ADC_PARAMS, frame_index=1, save_prefix="frame", show_plots=False):
    """
    Full radar data post-processing: time-domain, range-FFT, Doppler-FFT, Azimuth-FFT.
    Saves all plots as PNGs. Optionally shows them interactively.
    """

    # Reshape and parse ADC data
    adc_data = np.reshape(adc_data, (-1, ADC_PARAMS['chirps'], ADC_PARAMS['tx'], ADC_PARAMS['samples'], ADC_PARAMS['IQ'], ADC_PARAMS['rx']))
    adc_data = np.transpose(adc_data, (0, 1, 2, 5, 3, 4))  # (frames, chirps, tx, rx, samples, IQ)
    adc_data = (1j * adc_data[..., 1] + adc_data[..., 0]).astype(np.complex64)  # (frames, chirps, tx, rx, samples)

    # Select frame
    if frame_index < 0 or frame_index >= adc_data.shape[0]:
        raise IndexError(f"frame_index {frame_index} out of range (0-{adc_data.shape[0]-1})")
    frame = adc_data[frame_index]  # (chirps, tx, rx, samples)

    # Plot time-domain IQ waveform for [chirp 0, tx 0, rx 0]
    plt.figure()
    plt.plot(np.real(frame[0,0,0,:]), label="I")
    plt.plot(np.imag(frame[0,0,0,:]), label="Q")
    plt.legend()
    plt.title("Time-domain IQ waveform (frame {}, chirp 0, tx 0, rx 0)".format(frame_index))
    plt.savefig(f"{save_prefix}time_domain_IQ.png")
    if show_plots: plt.show()
    plt.close()

    # Range-FFT
    window = np.kaiser(ADC_PARAMS['samples'], 4)
    frame_win = frame * window  # Broadcasting over last axis

    range_fft = np.fft.fft(frame_win, axis=-1)  # (chirps, tx, rx, samples)
    # Range resolution and bins
    chirp_bandwidth = (ADC_PARAMS['freq_slope'] * 1e12 * ADC_PARAMS['samples']) / (ADC_PARAMS['sample_rate'] * 1e3)
    range_res = 3e8 / (2 * chirp_bandwidth)
    ranges = np.round(np.arange(ADC_PARAMS['samples']) * range_res, 2)

    # --- Add Range Profile FFT Plot ---
    range_profile = np.abs(range_fft).sum(axis=(0,1,2))  # Sum over chirps, tx, rx
    range_profile_db = 20 * np.log10(range_profile + 1e-12)  # dB scale

    # Find max magnitude and its range
    max_idx = np.argmax(range_profile)
    max_range = ranges[max_idx]
    max_magnitude_db = range_profile_db[max_idx]
    print(f"Max magnitude in range profile: {max_magnitude_db:.2f} dB at {max_range:.2f} meters (bin {max_idx})")

    plt.figure(figsize=(10, 6))
    plt.plot(ranges, range_profile_db, color='b', linewidth=1)
    plt.scatter([max_range], [max_magnitude_db], color='r', s=80, label='Target')
    plt.annotate(f"{max_range:.2f} m", 
                 xy=(max_range, max_magnitude_db), 
                 xytext=(max_range, max_magnitude_db+5),
                 arrowprops=dict(facecolor='red', shrink=0.05),
                 fontsize=12, color='red', ha='center')
    plt.title(f"Range Profile FFT (frame {frame_index})")
    plt.xlabel("Range (m)")
    plt.ylabel("Magnitude (dB)")
    plt.grid(True)
    plt.legend()
    plt.savefig(f"{save_prefix}range_profile_fft.png")
    if show_plots: plt.show()
    plt.close()
    # --- End Range Profile FFT Plot ---

    # Plot Range-FFT (sum over tx, rx)
    plt.figure(figsize=(10,6))
    plt.imshow(np.log(np.abs(range_fft[:,0,:,:].sum(1)).T), aspect='auto')
    plt.ylabel('Range Bins/m')
    plt.yticks(np.arange(ADC_PARAMS['samples'])[::7], ranges[::7])
    plt.title(f'Range FFT (frame {frame_index})')
    plt.colorbar(label='log(magnitude)')
    plt.savefig(f"{save_prefix}range_fft.png")
    if show_plots: plt.show()
    plt.close()

    # Doppler-FFT
    window_d = np.kaiser(ADC_PARAMS['chirps'], 2)
    range_fft_w = (range_fft.T * window_d).T  # window along chirp axis

    range_doppler = np.fft.fft(range_fft_w, axis=0)
    range_doppler = np.fft.fftshift(range_doppler, axes=0)

    # Doppler axis
    StartWaveLenght = (3e8 / (ADC_PARAMS['startFreq'] * 1e9))
    TimeChirp = 1e-6 * (ADC_PARAMS['idleTime'] + ADC_PARAMS['rampEndTime'])
    TimeFrame = TimeChirp * ADC_PARAMS['chirps']
    VelocityRes = (StartWaveLenght) / (2 * (TimeFrame))
    MaxVelocity = StartWaveLenght / (4 * TimeChirp)
    doppler_bins = np.linspace(-MaxVelocity, MaxVelocity, ADC_PARAMS['chirps'])

    # Plot Doppler-FFT (sum over tx, rx)
    plt.figure(figsize=(10,6))
    plt.imshow(np.log(np.abs(range_doppler[:,0,:,:]).T).sum(1), aspect='auto')
    plt.xlabel('Doppler Bins')
    plt.ylabel('Range Bins/m')
    plt.yticks(np.arange(ADC_PARAMS['samples'])[::7], ranges[::7])
    plt.title(f'Doppler FFT (frame {frame_index})')
    plt.colorbar(label='log(magnitude)')
    plt.savefig(f"{save_prefix}doppler_fft.png")
    if show_plots: plt.show()
    plt.close()

    # Azimuth-FFT
    num_angle_bins = 64
    # Use first 2 tx for azimuth (as in notebook)
    range_azimuth = range_doppler[:,:2,:,:].reshape((ADC_PARAMS['chirps'],-1,ADC_PARAMS['samples']))
    range_azimuth = np.fft.fft(range_azimuth, num_angle_bins, axis=1)
    range_azimuth = np.fft.fftshift(range_azimuth, axes=1)

    # Azimuth image
    range_azimuth_img = np.log(np.abs(range_azimuth).sum(0).T)
    range_azimuth_img = range_azimuth_img - np.min(range_azimuth_img)
    range_azimuth_img = range_azimuth_img / np.max(range_azimuth_img)

    plt.figure(figsize=(10,6))
    plt.imshow(range_azimuth_img, aspect='auto')
    plt.xlabel('Azimuth (Angle) Bins')
    plt.ylabel('Range Bins/m')
    plt.yticks(np.arange(ADC_PARAMS['samples'])[::7], ranges[::7])
    plt.title(f'Azimuth FFT (frame {frame_index})')
    plt.colorbar(label='normalized log(magnitude)')
    plt.savefig(f"{save_prefix}azimuth_fft.png")
    if show_plots: plt.show()
    plt.close()

    # Fan scan visualization
    def fanScan(im, r0=0, angle=180, k=7, top=True):
        h, w = im.shape
        if r0 > 0:
            bg = np.zeros((r0, w))
            im = np.append(bg, im, axis=0) if top else np.append(im, bg, axis=0)
        h, w = im.shape
        r = 2*h-1
        im_fan = np.zeros((r, r))
        idx = np.arange(h) if top else np.arange(h)[::-1]
        alpha = np.radians(np.linspace(-angle/2, angle/2, k*w))
        for i in range(k*w):
            rows = np.int32(np.ceil(np.cos(alpha[i])*idx)) + r//2
            cols = np.int32(np.ceil(np.sin(alpha[i])*idx)) + r//2
            im_fan[(rows, cols)] = im[:,i//k]
        if 360 > angle >= 180:
            im_fan = im_fan[int(h*(1-np.sin(np.radians((angle/2-90))))):]
        if not top:
            im_fan = im_fan[::-1]
        return im_fan

    im_fan = fanScan(range_azimuth_img, r0=0, angle=180, k=50, top=True)
    plt.figure(figsize=(8,8))
    plt.imshow(im_fan)
    ax = plt.gca()
    ax.xaxis.set_ticks_position('top')
    lableNum = 7
    range_xlable = np.arange(0, ranges[-1], ranges[-1]/lableNum)
    range_xlable = np.round(np.concatenate((range_xlable[:0:-1], range_xlable)),2)
    range_xticks_l = np.arange((ADC_PARAMS['samples']*2-1)/2,0,-(ADC_PARAMS['samples']*2-1)/(2*lableNum-1))
    range_xticks_h = np.arange((ADC_PARAMS['samples']*2-1)/2,ADC_PARAMS['samples']*2-1,(ADC_PARAMS['samples']*2-1)/(2*lableNum-1))
    range_xticks = np.concatenate((range_xticks_l[:0:-1], range_xticks_h))
    plt.xticks(range_xticks, range_xlable)
    plt.yticks([])
    plt.title('Range Bins/m')
    plt.ylabel('Azimuth (Angle) Bins')
    plt.xlabel('Azimuth fan scan')
    plt.savefig(f"{save_prefix}azimuth_fan.png")
    if show_plots: plt.show()
    plt.close()

dca = None

try:
    dca = DCA1000()

    # 1. Reset the radar and DCA1000
    dca.reset_radar()
    dca.reset_fpga()
    print("wait for reset")
    time.sleep(1)
    
    # 2. Initialize the radar via SPI and configure the corresponding parameters
    radar_config_file = "configFiles/AWR2243_mmwaveconfig.txt"      # If laneEn=15, LVDS is in 4-lane mode
    dca_config_file = "configFiles/cf.json"                         # If LVDS is set to 4-lane mode, ensure lvdsMode in cf.json is set to 1

    radar.AWR2243_init(radar_config_file)
    numLoops= 1
    frameNumInBuf=8
    numframes=8                                                   # numframes must be <= frameNumInBuf
    radar.AWR2243_setFrameCfg(0)                                    # Valid range: 0 to 65535 (0 for infinite frames)
    
    # Check LVDS parameters
    LVDSDataSizePerChirp_l, maxSendBytesPerChirp_l, ADC_PARAMS_l, CFG_PARAMS_l = dca.AWR2243_read_config(radar_config_file)
    dca.refresh_parameter()
    print(ADC_PARAMS_l)
    print(CFG_PARAMS_l)
    print("LVDSDataSizePerChirp:%d must <= maxSendBytesPerChirp:%d" % (LVDSDataSizePerChirp_l, maxSendBytesPerChirp_l))
    # Check if the FPGA is connected and working properly
    print("System connection check:", dca.sys_alive_check())
    print(dca.read_fpga_version())
    # 3. Send FPGA configuration commands via Ethernet UDP
    print("Config fpga:", dca.config_fpga(dca_config_file))
    # 4. Send record data packet configuration commands via Ethernet UDP
    print("Config record packet delay:", dca.config_record(dca_config_file))

    PrintCalcParams(ADC_PARAMS_l)               

    input("press ENTER to start capture...")
    
    # 5. Send start capture commands via Ethernet UDP
    dca.stream_start()
    dca.fastRead_in_Cpp_thread_start(frameNumInBuf) # Start the UDP capture thread

    # 6. Start the radar via SPI
    radar.AWR2243_sensorStart()

    # 7. Receive UDP data packets + parse raw data + real-time data processing
    start = time.time()
    for i in range(numLoops):
        print("current loop:", i)
        startTime = datetime.datetime.now()
        start1 = time.time()
        # data_buf = dca.fastRead_in_Cpp(1,sortInC=True)
        # data_buf = dca.fastRead_in_Cpp_noDisp(1)
        data_buf = dca.fastRead_in_Cpp_thread_get(numframes, verbose=True, sortInC=True)

        end1 = time.time()
        print("capture time elapsed(s):", end1 - start1)
        print("capture performance: %.2f FPS" % (numframes / (end1 - start1)))

        # Create a folder for this capture
        folder_name = "Test_" + startTime.strftime('%Y-%m-%d-%H-%M-%S')
        os.makedirs(folder_name, exist_ok=True)

        # Save bin file in the folder
        filename = os.path.join(folder_name, "raw_data" + ".bin")
        data_buf.tofile(filename)
        print("file saved to", filename)

        # Save all plots in the same folder
        save_prefix = os.path.join(folder_name, "")
        start2 = time.time()
        postProc(data_buf, ADC_PARAMS_l, save_prefix=save_prefix)
        end2 = time.time()

        print("postProc time elapsed(s):", end2 - start2)
        print("postProc performance: %.2f FPS" % (numframes / (end2 - start2)))
    end = time.time()
    print("Performance: %.2f Loops per Sec" % (numLoops / (end - start)))


except Exception as e:
    traceback.print_exc()
finally:
    # 8.1 Stop the radar via SPI
    radar.AWR2243_sensorStop()
    # 8.2 Wait for the radar to finish capturing
    radar.AWR2243_waitSensorStop()
    if dca is not None:
        # 9. Send stop capture commands via Ethernet UDP
        dca.fastRead_in_Cpp_thread_stop() # Stop the UDP capture thread (must be called before stream_stop, i.e., UDP reception cannot occur simultaneously with sending)
        dca.stream_stop()  # Stop DCA capture
        dca.close()
        
    # 10. Turn off radar power and configuration files via SPI
    radar.AWR2243_poweroff()