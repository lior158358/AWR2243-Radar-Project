import traceback
import time
from mmwave.dataloader import DCA1000
from mmwave.dataloader.radars import TI
import numpy as np
import datetime
'''
# General process for collecting raw data
1. Reset radar and DCA1000 (reset_radar, reset_fpga)
2. Initialize radar via UART and configure parameters (TI, setFrameCfg)
3. (optional) Create process to receive DSP-processed data from serial port (create_read_process)
4. Send FPGA configuration command via UDP (config_fpga)
5. Send record data packet configuration command via UDP (config_record)
6. (optional) Start serial port receiving process (only for buffer clearing) (start_read_process)
7. Send start capture command via UDP (stream_start)
8. (optional) Start UDP data packet receiving thread (fastRead_in_Cpp_async_start)
9. Start radar via serial port (can also be controlled via FTDI (USB to SPI), currently only implemented on AWR2243) (startSensor)
10. Wait for UDP data packet receiving thread to finish + parse raw data (fastRead_in_Cpp_async_wait/fastRead_in_Cpp)
11. Save raw data to file for offline processing (tofile)
12. (optional) Send stop capture command via UDP (stream_stop)
13. Stop radar via serial port (stopSensor) or send reset radar command via UDP (reset_radar)
14. (optional) Stop receiving serial port data (stop_read_process)
15. (optional) Parse DSP-processed data received from serial port (post_process_data_buf)

# "*.cfg" mmWave radar configuration file requirements
Default profile in Visualizer disables LVDS streaming.
To enable it, export the chosen profile and set the appropriate enable bits.
adcbufCfg should be set as below, the third parameter of lvdsStreamCfg should be set to 1, see mmwave_sdk_user_guide.pdf for details
1. adcbufCfg -1 0 1 1 1
2. lvdsStreamCfg -1 0 1 0 

# "cf.json" data capture card configuration file requirements
When using xWR1843, set lvdsMode to 2, xWR1843 only supports 2 LVDS lanes
See TI_DCA1000EVM_CLI_Software_UserGuide.pdf for details
lvds Mode:
LVDS mode specifies the lane config for LVDS. This field is valid only when dataTransferMode is "LVDSCapture".
The valid options are
• 1 (4lane)
• 2 (2lane)
packet delay:
By default, Ethernet throughput varies up to 325 Mbps speed with a 25-µs Ethernet packet delay. 
You can change the Ethernet packet delay from 5 µs to 500 µs to achieve different throughputs.
"packetDelay_us":  5 (us)   ~   706 (Mbps)
"packetDelay_us": 10 (us)   ~   545 (Mbps)
"packetDelay_us": 25 (us)   ~   325 (Mbps)
"packetDelay_us": 50 (us)   ~   193 (Mbps)
'''
dca = None
radar = None

try:
    dca = DCA1000()

    # 1. Reset radar and DCA1000
    dca.reset_radar()
    dca.reset_fpga()
    print("wait for reset")
    time.sleep(1)

    # 2. Initialize radar via UART and configure parameters
    dca_config_file = "configFiles/cf.json" # Remember to set lvdsMode to 2 in cf.json, xWR1843 only supports 2 LVDS lanes
    radar_config_file = "configFiles/xWR1843_profile_3D.cfg" # Remember to set the third parameter of lvdsStreamCfg to 1 to enable LVDS data transmission
    numframes=10
    # Remember to change the port number, verbose=True will display all serial commands sent to the radar board and responses
    radar = TI(cli_loc='COM4', data_loc='COM5',data_baud=921600,config_file=radar_config_file,verbose=True)
    # After setting the number of frames, radar will automatically stop, no need to send stop command to FPGA, but still need to send stop command to radar
    radar.setFrameCfg(numframes)

    # 3. Create process to receive DSP-processed data from serial port
    radar.create_read_process(numframes)

    # 4. Send FPGA configuration command via UDP
    # 5. Send record data packet configuration command via UDP
    '''
    dca.sys_alive_check()             # Check if FPGA is connected and working properly
    dca.config_fpga(dca_config_file)  # Configure FPGA parameters
    dca.config_record(dca_config_file)# Configure record parameters
    '''
    dca.configure(dca_config_file,radar_config_file)  # This function completes all the above operations

    # Press Enter to start capture
    input("press ENTER to start capture...")

    # 6. Start serial port receiving process (only for buffer clearing, only needed when capturing multiple times in a loop without running stop)
    radar.start_read_process()
    # 7. Send start capture command via UDP
    dca.stream_start()
    # 8. Start UDP data packet receiving thread
    # numframes_out,sortInC_out = dca.fastRead_in_Cpp_async_start(numframes,sortInC=True) # [Capture Method 1] 1. Asynchronous call (requires C++17 or above compiler support)

    # 9. Start radar via serial port
    startTime = datetime.datetime.now()
    start = time.time()
    radar.startSensor()

    # 10. Wait for UDP data packet receiving thread to finish + parse raw data
    # data_buf = dca.fastRead_in_Cpp_async_wait(numframes_out,sortInC_out) # [Capture Method 1] 2. Wait for asynchronous thread to finish
    data_buf = dca.fastRead_in_Cpp(numframes,sortInC=True) # [Capture Method 2] Synchronous call (will lose packets before capture starts, but better compatibility)
    end = time.time()
    print("time elapsed(s):",end-start)

    # 11. Save raw data to file
    filename="raw_data_"+startTime.strftime('%Y-%m-%d-%H-%M-%S')+".bin"
    data_buf.tofile(filename)
    print("file saved to",filename)
    
    # 12. DCA stops capture, after setting number of frames it will automatically stop, no need to send stop command to FPGA
    # dca.stream_stop()
    # 13. Stop radar via serial port
    radar.stopSensor()
    # 14. Stop receiving serial port data
    radar.stop_read_process()

    # 15. Parse DSP-processed data received from serial port, verbose=True will display detailed info for each frame during processing
    DSP_Processed_data=radar.post_process_data_buf(verbose=False)

    # Parsed point cloud and other data are in DSP_Processed_data variable
    # print(DSP_Processed_data)

    # Unparsed raw serial data is in radar.byteBuffer variable
    # print(radar.byteBuffer)
    
    # Save parsed serial data to file, can be loaded with np.load('xxx.npy', allow_pickle=True)
    dspFileName = "DSP_data_"+startTime.strftime('%Y-%m-%d-%H-%M-%S')
    np.save(dspFileName, DSP_Processed_data)
    print(f'file saved to {dspFileName}.npy')

except Exception as e:
    traceback.print_exc()
finally:
    if dca is not None:
        dca.close()
    if radar is not None:
        radar.cli_port.close()
        # radar.data_port.close() # Serial port data receiving is automatically closed when radar.stop_read_process() is called