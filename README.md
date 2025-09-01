# ADC/UART Data Capturing Using AWR2243 with DCA1000

* For AWR2243: Capture raw ADC IQ data in Python and C (using pybind11) without mmWave Studio.

---

## Introduction

This module consists of two main parts: `mmwave` and `fpga_udp`:
- **mmwave**: Modified from [OpenRadar](https://github.com/PreSenseRadar/OpenRadar), used for configuration file parsing, UART data transmission and reception, raw data decoding, etc.
- **fpga_udp**: Modified from [pybind11 example](https://github.com/pybind/python_example) and [mmWave-DFP-2G](https://www.ti.com/tool/MMWAVE-DFP), used to receive high-speed raw data from the DCA1000 via Ethernet using C socket code. For models like AWR2243, which lack an onboard DSP and ARM core, it also implements firmware flashing, parameter configuration, and control via SPI using FTDI over USB.

AWR2243 TI's mmWave radar sensors is:
- **RF-only front-end sensors**: Examples include [AWR2243](https://www.ti.com/product/AWR2243).

For RF-only sensors, control and configuration commands are sent via SPI/I2C, and raw data is output via CSI2/LVDS. This repository implements all operations for these sensors, including SPI control via FTDI and raw data capture via DCA1000.

---

## Prerequisites

### Hardware

#### For AWR2243
- Connect the micro-USB port (FTDI) on the DCA1000 to your system.
- Connect the AWR2243 to a 5V barrel jack.
- Set the power connector on the DCA1000 to `RADAR_5V_IN`.
- Put the device in SOP0 mode:
  - Place a jumper on SOP0; all others remain disconnected.
- Connect the RJ45 Ethernet cable to your system.
- Set a fixed IP for the local interface: `192.168.33.30`.

---

### Software

#### Windows
- Install **Microsoft Visual C++ 14.0 or greater**:
  - Download "[Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)" or "[Visual Studio](https://visualstudio.microsoft.com/downloads/)" and choose "Desktop development with C++".
- Install the **FTDI D2XX driver**:
  - Download version [2.12.36.4](https://www.ftdichip.com/Drivers/CDM/CDM%20v2.12.36.4%20WHQL%20Certified.zip) or newer from the [official website](https://ftdichip.com/drivers/d2xx-drivers/).
  - Unzip the file and install `.\ftdibus.inf` by right-clicking it.
  - Copy `.\amd64\ftd2xx64.dll` to `C:\Windows\System32\` and rename it to `ftd2xx.dll`. For 32-bit systems, copy `.\i386\ftd2xx.dll` instead.ff

#### Linux
- Install Python development tools:
  ```bash
  sudo apt install python3-dev
  ```
 - FTDI D2XX driver and .so lib is needed. Download version 1.4.27 or newer from [official website](https://ftdichip.com/drivers/d2xx-drivers/) based on your architecture, e.g. [X86](https://ftdichip.com/wp-content/uploads/2022/07/libftd2xx-x86_32-1.4.27.tgz), [X64](https://ftdichip.com/wp-content/uploads/2022/07/libftd2xx-x86_64-1.4.27.tgz), [armv7](https://ftdichip.com/wp-content/uploads/2022/07/libftd2xx-arm-v7-hf-1.4.27.tgz), [aarch64](https://ftdichip.com/wp-content/uploads/2022/07/libftd2xx-arm-v8-1.4.27.tgz), etc.
 - Then you'll need to install the library:
   - ```
     tar -xzvf libftd2xx-x86_64-1.4.27.tgz
cd release
sudo cp ftd2xx.h /usr/local/include
sudo cp WinTypes.h /usr/local/include
cd build
sudo cp libftd2xx.so.1.4.27 /usr/local/lib
sudo chmod 0755 /usr/local/lib/libftd2xx.so.1.4.27
sudo ln -sf /usr/local/lib/libftd2xx.so.1.4.27 /usr/local/lib/libftd2xx.so
sudo ldconfig -v
     ```


## Installation

 - clone this repository
 - for Windows:
   - `python3 -m pip install --upgrade pip`
   - `python3 -m pip install --upgrade setuptools`
   - `python3 -m pip install ./fpga_udp`
 - for Linux:
   - `sudo python3 -m pip install --upgrade pip`
   - `sudo python3 -m pip install --upgrade setuptools`
   - `sudo python3 -m pip install ./fpga_udp`


## Instructions for Use

#### General
1.  First, set up the environment according to [Prerequisites](#prerequisites).
2.  Then, install the library as described in [Installation](#installation).
3.  For any missing modules, please search and install them if errors occur during runtime.

#### For AWR2243
1.  Flash the firmware patch to external flash (only needed once; rebooting does not erase firmware).
  - for Windows: `python3 -c "import fpga_udp;fpga_udp.AWR2243_firmwareDownload()"`
  - for Linux: `sudo python3 -c "import fpga_udp;fpga_udp.AWR2243_firmwareDownload()"`
  - If you see "MSS Patch version [ 2. 2. 2. 0]", flashing was successful.
2.  Open [captureADC_AWR2243.py](#captureadc_awr2243py), modify as needed, enter the txt config file path, and start data collection.
3.  Modify [text](configFiles/AWR2243_mmwaveconfig.txt) if needed.
4.  If parameters are unsatisfactory, modify and verify with [testParam_AWR2243.ipynb](#testparam_awr2243ipynb).
5.  Open [testDecode_AWR2243.ipynb](#testdecode_awr2243ipynb) to collected and save raw data, post - proccess and plot.

## Example


#### 2. "*.cfg" mmWave radar config file requirements
 - Default profile in Visualizer disables LVDS streaming.
 - To enable, export the profile and set the appropriate enable bits.
 - `adcbufCfg` should be set as below, and the third parameter of `lvdsStreamCfg` should be set to 1. See mmwave_sdk_user_guide.pdf for details:
  - adcbufCfg -1 0 1 1 1
  - lvdsStreamCfg -1 0 1 0 
#### 3. "cf.json" data capture card config file requirements
 - See TI_DCA1000EVM_CLI_Software_UserGuide.pdf for details.
 - LVDS Mode:
  - Specifies lane config for LVDS, valid only when dataTransferMode is "LVDSCapture".
  - Valid options:
    - 1 (4lane)
    - 2 (2lane)
 - Packet delay:
  - Ethernet throughput varies up to 325 Mbps at 25-µs packet delay.
  - You can change Ethernet packet delay from 5 µs to 500 µs for different throughputs:
     - "packetDelay_us":  5 (us)   ~   706 (Mbps)
     - "packetDelay_us": 10 (us)   ~   545 (Mbps)
     - "packetDelay_us": 25 (us)   ~   325 (Mbps)
     - "packetDelay_us": 50 (us)   ~   193 (Mbps)

### ***captureADC_AWR2243.py***
Example code for collecting raw ADC IQ data (AWR2243 only).
#### 1. General workflow for AWR2243 raw data collection
 1. Reset radar and DCA1000 (`reset_radar`, `reset_fpga`)
 2. Initialize radar via SPI and configure parameters (`AWR2243_init`, `AWR2243_setFrameCfg`) (root permission needed on Linux)
 3. Send FPGA configuration commands via UDP (`config_fpga`)
 4. Send record data packet configuration via UDP (`config_record`)
 5. Send start capture command via UDP (`stream_start`)
 6. Start UDP data packet receive thread (`fastRead_in_Cpp_async_start`)
 7. Start radar via SPI (`AWR2243_sensorStart`)
 8. 1. (optional, if numFrame==0 this is required) Stop radar via SPI (`AWR2243_sensorStop`)
  2. (optional, if numFrame==0 this must not be present) Wait for radar capture to finish (`AWR2243_waitSensorStop`)
 9. (optional, if numFrame==0 this is required) Send stop capture command via UDP (`stream_stop`)
 10. Wait for UDP receive thread to finish and parse raw data (`fastRead_in_Cpp_async_wait`)
 11. Save raw data to file for offline processing (`tofile`)
 12. Power off radar and config via SPI (`AWR2243_poweroff`)
#### 2. "mmwaveconfig.txt" mmWave radar config file requirements
 - Modify for your desiered waveform
#### 3. "cf.json" data capture card config file requirements
- See TI_DCA1000EVM_CLI_Software_UserGuide.pdf for details.
- LVDS Mode:
  - Specifies lane config for LVDS, valid only when dataTransferMode is "LVDSCapture".
  - Valid options:
    - 1 (4lane)
    - 2 (2lane)
- Packet delay:
  - Ethernet throughput varies up to 325 Mbps at 25-µs packet delay.
    - You can change Ethernet packet delay from 5 µs to 500 µs for different throughputs:
      - "packetDelay_us":  5 (us)   ~   706 (Mbps)
      - "packetDelay_us": 10 (us)   ~   545 (Mbps)
      - "packetDelay_us": 25 (us)   ~   325 (Mbps)
      - "packetDelay_us": 50 (us)   ~   193 (Mbps)



### ***realTimeProc_AWR2243.py***
Example code for real-time loop collection and online processing of raw ADC IQ data (AWR2243 only).
#### 1. General workflow for AWR2243 raw data collection
 - Omitted
#### 2. "mmwaveconfig.txt" mmWave radar config file requirements
 - Modify for your desiered waveform
#### 3. "cf.json" data capture card config file requirements
 - Omitted


### ***testDecode_AWR2243.ipynb***
Example code for parsing raw ADC IQ data (AWR2243 only). Open with Jupyter (VS Code with Jupyter plugin recommended).
#### 1. Parsing LVDS ADC raw IQ data with numpy
 - Import relevant libraries
 - Set parameters
 - Load and parse saved bin data
 - Plot time-domain IQ waveform
 - Compute Range-FFT
 - Compute Doppler-FFT
 - Compute Azimuth-FFT
 
### ***testParam_AWR2243.ipynb***
AWR2243 mmWave radar configuration parameter validation. Open with Jupyter (VS Code with Jupyter plugin recommended).
 - Validates cfg file for radar and cf.json file for DCA capture board.
 - Constraints are based on IWR1843 device specs; see datasheet, SDK user guide, and chirp programming manual.
 - If parameters meet constraints, debug info is shown in cyan; otherwise, purple or yellow.
 - Note: Constraints may not be fully accurate; even if all parameters pass, operation may still fail in rare cases.

### ***testDecodeADCdata.mlx***
MATLAB example code for parsing raw ADC IQ data.
 - Set parameters
 - Load saved bin raw ADC data
 - Parse and reconstruct data format
 - Plot time-domain IQ waveform
 - Compute Range-FFT (1D FFT + static clutter removal)
 - Compute Doppler-FFT
 - 1D-CA-CFAR Detector on Range-FFT
 - Compute Azimuth-FFT

### ***testGtrack.py***
Test the gTrack algorithm written in C using cppyy. This is TI's group target tracking algorithm: input is point cloud, output is trajectory.

The algorithm tracks multiple targets, each represented by a set of measurement points.
Each measurement point contains detection info, e.g., range, azimuth, elevation (for 3D), and radial velocity.

Instead of tracking individual reflections, the algorithm predicts and updates the location and dispersion of the group.

A group is defined as the set of measurements (typically tens to hundreds) associated with a real-life target.

Supports tracking in 2D or 3D as a build-time option:
 - 2D: inputs range/azimuth/doppler, tracks in 2D cartesian space.
 - 3D: inputs range/azimuth/elevation/doppler, tracks in 3D cartesian space.
#### Input/output
 - Inputs: Point Cloud (hundreds of measurements/reflections)
 - Outputs: Target List (array of target descriptors with properties)
 - Optionally outputs Target Index (array of target IDs for each measurement)
#### Features
 - Uses extended Kalman Filter for target motion in Cartesian coordinates.
 - Supports constant velocity and constant acceleration models.
 - Uses 3D/4D Mahalanobis distances for gating and max-likelihood criteria for point-to-track association.
                                   



