import serial
import struct
import shared_functions as sf
from typing import Union, List
from multiprocessing import Process, Queue, Event
from queue import Empty
from measurment_setup import set_measurement_setup, get_measurement_setup
from output_configs import set_output_config, get_output_config
from datetime import datetime
import os
import traceback

params = {
  "Burst Count" : 2,
  "Frame Rate" : 1,
  "Excitation Frequencies" : {"Fmin" : 50000, "Fmax": 50000, "Ftype": 0},
  "Excitation Amplitude" : 0.001,
  "Excitation Switch Type" : 2,
  "Excitation Sequence" : [(1,17), (2,18)],
  "ADC Range" : 1,
  "Single Ended": {"Mode": 1, "Boundary": 1}
}

configurations = {
  "Excitation Setting" : 1,
  "Current row in the frequency stack" : 0,
  "Timestamp" : 1
}

def SystemMessageCallback(
    serial, prnt_msg: bool = True, ret_hex_int: Union[None, str] = None
):
    """
    Reads the message buffer of a serial connection. Also prints out the general system message.

    Parameters
    ----------
    serial :
        serial connection
    prnt_msg : bool
        if true print message, if false not
    ret_hex_int : Union[None, str]
        use ['none','hex', 'int', 'both'] to return nothing, hex or integer data or both.

    Returns
    -------
    [None, received_hex, received, (received, received_hex)]
        return depens on the ret_hex_int variable
    """
    msg_dict = {
        "0x01": "No message inside the message buffer",
        "0x02": "Timeout: Communication-timeout (less data than expected)",
        "0x04": "Wake-Up Message: System boot ready",
        "0x11": "TCP-Socket: Valid TCP client-socket connection",
        "0x81": "Not-Acknowledge: Command has not been executed",
        "0x82": "Not-Acknowledge: Command could not be recognized",
        "0x83": "Command-Acknowledge: Command has been executed successfully",
        "0x84": "System-Ready Message: System is operational and ready to receive data",
        "0x92": "Data holdup: Measurement data could not be sent via the master interface",
    }
    timeout_count = 0
    received = []
    received_hex = []
    data_count = 0

    while True:
        buffer = serial.read()
        if buffer:
            received.extend(buffer)
            # print(received[-1])
            # print(int.from_bytes(buffer, byteorder='big'))
            data_count += len(buffer)
            timeout_count = 0
            continue
        timeout_count += 1
        if timeout_count >= 1:
            # Break if we haven't received any data
            break

        received = "".join(str(received))  # If you need all the data
    received_hex = [hex(receive) for receive in received]
    try:
        msg_idx = received_hex.index("0x18")
        if prnt_msg:
            print(msg_dict[received_hex[msg_idx + 2]])
    except BaseException:
        if prnt_msg:
            print(msg_dict["0x01"])
        prnt_msg = False
    if prnt_msg:
        print("message buffer:\n", received_hex)
        print("message length:\t", data_count)

    if ret_hex_int is None:
        return
    elif ret_hex_int == "hex":
        return received_hex
    elif ret_hex_int == "int":
        return received
    elif ret_hex_int == "both":
        return received, received_hex
    
def read_from_serial(q, stop_event, ser):
  while True:
    buffer = ser.read()
    if buffer:
      q.put(buffer)
      continue
    stop_event.set()
    break

def process_data(q, stop_event, configs, dataset_name, directory_path):
  items = []
  frames = []
  current_frame = []
  frame_started = False
  frame_length = 0
  frame_count = 0
  file_output = ['18'],
  the_first = [],
  file_num = 0
  while not stop_event.is_set() or not q.empty():
    try:
      item = q.get(timeout=1)
      num = int.from_bytes(item, byteorder='big')
      items.append(num)
       # Check for the start of a frame
      if num == 180 and not frame_started:
          frame_started = True
          current_frame = [num]
          frame_length = 0
          continue
      
      # If a frame has started, add to the current frame
      if frame_started:
          current_frame.append(num)
          if len(current_frame) == 2:  # second byte indicates the frame length
              frame_length = num + 1

          # Check for the end of the frame
          if len(current_frame) > 2 and len(current_frame) == frame_length + 2:
              frames.append(current_frame)
              frame_count += 1
              if frame_count == 1:
                 the_first = [str(current_frame[3]), str(current_frame[4])]
              if [str(current_frame[3]), str(current_frame[4])] == the_first:
                if current_frame[2] == 1:
                  if frame_count != 1:
                    file_num += 1
                    file_path = os.path.join(directory_path, f'{dataset_name}_{file_num}.txt')
                    with open(file_path, 'w') as file:
                      for line in file_output:
                          file.write(line + '\n')
                  now = datetime.now()
                  file_output = ['18', str(frame_count), dataset_name, now.strftime("%Y.%m.%d. %H:%M:%S.%f")[:-3]] + configs + [str(current_frame[4]) + " " + str(current_frame[3])]
                else:
                  all_data = frames[-1][9:-1] + current_frame[9:-1]
                  floats = []
                  for i in range(0, len(all_data), 4):
                      byte_chunk = all_data[i:i+4]
                      if len(byte_chunk) == 4:
                          float_number = struct.unpack('>f', bytes(byte_chunk))[0]
                          floats.append(float_number)
                  file_output += [' '.join(map(str, floats))]
              else:
                if current_frame[2] == 1:
                  file_output += [str(current_frame[4]) + " " + str(current_frame[3])]
                else:
                  all_data = frames[-1][9:-1] + current_frame[9:-1]
                  floats = []
                  for i in range(0, len(all_data), 4):
                    byte_chunk = all_data[i:i+4]
                    if len(byte_chunk) == 4:
                      float_number = struct.unpack('>f', bytes(byte_chunk))[0]
                      floats.append(float_number)
                  file_output += [' '.join(map(str, floats))]
              frame_started = False
    except Empty:
      continue
    except Exception as e:
      tb = traceback.format_exc()
      print(f"An error occurred: {e}")
      print("Traceback details:")
      print(tb)
      # print(f"Error converting item {item}: {e}")]
  file_num += 1
  file_path = os.path.join(directory_path, f'{dataset_name}_{file_num}.txt')
  with open(file_path, 'w') as file:
    for line in file_output:
        file.write(line + '\n')
  # print(file_output)
    
def StartStopMeasurement(q, stop_event) -> list:
    ser = sf.init_serial()
    print("Starting measurement.")
    ser.write(bytearray([0xB4, 0x01, 0x01, 0xB4]))
    measurement_data_hex = read_from_serial(q, stop_event, ser)
    print("Stopping measurement.")
    ser.write(bytearray([0xB4, 0x01, 0x00, 0xB4]))
    return measurement_data_hex

def measurment(dataset_name, directory_path):
  configs = get_measurement_setup()
  q = Queue()
  stop_event = Event()
  read_process = Process(target=StartStopMeasurement, args=(q, stop_event))
  process_process = Process(target=process_data, args=(q, stop_event, configs, dataset_name, directory_path))
  read_process.start()
  process_process.start()
# set_measurement_setup(params)

if __name__ == '__main__':
   set_measurement_setup(params)
   set_output_config(configurations)
   measurment('hello', '//chips.eng.utah.edu/home/u1462232/.win_desktop/Sciospec-EIT32-Interface/test_output')

# if __name__ == '__main__':
#     q = Queue()
#     stop_event = Event()

#     set_measurement_setup(params)
#     get_measurement_setup()
#     print("--------------------------------")
#     # set_output_config(configurations)
#     # get_output_config()
#     # print("--------------------------------")
#     read_process = Process(target=StartStopMeasurement, args=(q, stop_event))
#     process_process = Process(target=process_data, args=(q, stop_event))

#     read_process.start()
#     process_process.start()
