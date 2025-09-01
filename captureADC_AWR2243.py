import traceback
import time
from mmwave.dataloader import DCA1000
import fpga_udp as radar
import numpy as np
import datetime
import fpga_udp;fpga_udp.AWR2243_firmwareDownload()
'''
# General process for collecting raw data with AWR2243
1. Reset the radar and DCA1000 (reset_radar, reset_fpga)
2. Initialize the radar via SPI and configure the corresponding parameters (AWR2243_init, AWR2243_setFrameCfg) (requires root privileges on Linux)
3. Send configuration commands to the FPGA via UDP (config_fpga)
4. Send configuration commands for recording data packets via UDP (config_record)
5. Send start capture commands via UDP (stream_start)
6. Start the UDP data packet reception thread (fastRead_in_Cpp_async_start)
7. Start the radar via SPI (AWR2243_sensorStart)
8.1. (optional, if numFrame == 0, this step is required) Stop the radar via SPI (AWR2243_sensorStop)
8.2. (optional, if numFrame == 0, this step is not allowed) Wait for the radar to finish capturing (AWR2243_waitSensorStop)
9. (optional, if numFrame == 0, this step is required) Send stop capture commands via UDP (stream_stop)
10. Wait for the UDP data packet reception thread to finish and parse the raw data (fastRead_in_Cpp_async_wait)
11. Save the raw data to a file for offline processing (tofile)
12. Turn off the radar power and configuration files via SPI (AWR2243_poweroff)

# Requirements for the "mmwaveconfig.txt" millimeter-wave radar configuration file
TBD

# Requirements for the "cf.json" data acquisition card configuration file
Refer to the TI_DCA1000EVM_CLI_Software_UserGuide.pdf for specific information.
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
dca = None

try:
    dca = DCA1000()

    # 1. Reset the radar and DCA1000
    dca.reset_radar()
    dca.reset_fpga()
    print("wait for reset")
    time.sleep(1)

    
    # 2. Initialize the radar via SPI and configure the corresponding parameters
    radar_config_file = "configFiles/AWR2243_mmwaveconfig.txt"  # If laneEn=15, LVDS is in 4-lane mode
    dca_config_file = "configFiles/cf.json"  # If LVDS is set to 4-lane mode, ensure lvdsMode in cf.json is set to 1
    radar.AWR2243_init(radar_config_file)
    numframes = 1
    radar.AWR2243_setFrameCfg(numframes)  # After setting the number of frames, the radar will stop automatically, no need to send stop commands to FPGA or radar
    
    # Check LVDS parameters
    LVDSDataSizePerChirp_l, maxSendBytesPerChirp_l, ADC_PARAMS_l, CFG_PARAMS_l = dca.AWR2243_read_config(radar_config_file)
    dca.refresh_parameter()
    print(ADC_PARAMS_l)
    print(CFG_PARAMS_l)
    print("LVDSDataSizePerChirp:%d must <= maxSendBytesPerChirp:%d" % (LVDSDataSizePerChirp_l, maxSendBytesPerChirp_l))
    # Check if the FPGA is connected and working properly
    print("System connection check:", dca.sys_alive_check())
    print(dca.read_fpga_version())
    # 3. Send configuration commands to the FPGA via UDP
    print("Config fpga:", dca.config_fpga(dca_config_file))
    # 4. Send configuration commands for recording data packets via UDP
    print("Config record packet delay:", dca.config_record(dca_config_file))
    
    # Press Enter to start capturing
    input("press ENTER to start capture...")

    # 5. Send start capture commands via UDP
    dca.stream_start()
    # 6. Start the UDP data packet reception thread
    numframes_out, sortInC_out = dca.fastRead_in_Cpp_async_start(numframes, sortInC=True)

    # 7. Start the radar via SPI
    startTime = datetime.datetime.now()
    start = time.time()
    radar.AWR2243_sensorStart()
    # 8.1 Stop the radar via SPI
    # radar.AWR2243_sensorStop()
    # 8.2 Wait for the radar to finish capturing
    radar.AWR2243_waitSensorStop()
    end = time.time()
    print("time elapsed(s):", end - start)
    
    # 9. Send stop capture commands via UDP
    # dca.stream_stop()  # DCA stops capturing, no need to send stop commands to FPGA after setting the number of frames

    # 10. Wait for the UDP data packet reception thread to finish and parse the raw data
    data_buf = dca.fastRead_in_Cpp_async_wait(numframes=numframes_out, sortInC=sortInC_out)
    # 11. Save the raw data to a file
    filename = "raw_data_" + startTime.strftime('%Y-%m-%d-%H-%M-%S') + ".bin"
    data_buf.tofile(filename)
    print("file saved to", filename)

except Exception as e:
    traceback.print_exc()
finally:
    if dca is not None:
        dca.close()
    # 12. Turn off the radar power and configuration files via SPI
    radar.AWR2243_poweroff()