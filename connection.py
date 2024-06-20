import serial
import struct
from typing import Union, List
from multiprocessing import Process, Queue, Event
from queue import Empty

errors = {
  1 : "Frame-Not-Acknowledge: Incorrect syntax",
  2 : "Timeout: Communication-timeout (less data than expected)",
  4 : "Wake-Up Message: System boot ready",
  17 :  "TCP-Socket: Valid TCP client-socket connection",
  129 : "Not-Acknowledge: Command has not been executed",
  130 : "Not-Acknowledge: Command could not be recognized",
  132 : "System-Ready Message: System is operational and ready to receive data",
  140 : "Data holdup: Measurement data could not be sent via the master interface"
}

# ser = serial.Serial(port='COM3', baudrate=9600, timeout=1)
def init_serial():
  ser = serial.Serial('COM3', baudrate=9600, timeout=2,parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,bytesize=serial.EIGHTBITS)
  if ser.is_open:
    print(f"Serial port {ser.port} opened successfully.")
    return ser
  else:
      print(f"Failed to open serial port {ser.port}.")
      return None

def valid_argument(setting, value, ser):
  output = list(ser.readline())
  if output[2] == 131:
    print(f'{setting} Set To: {value}')
  else:
    print(f'Error Setting {setting}: {errors[output[2]]}')

def read_measurment(ser):
  output = list(ser.readline())
  if output[-2] == 131:
    return output[:-4]
  else:
    print(f'Error: {errors[output[-2]]}')
    return []

def convert_to_hex(args, num, types):
  conversions = {
    '2u' : '<H', # 2 Byte Unsigned Int
    '4f' : '<f', # 4 Byte Float
    '1u' : '<B', # 1 Byte Unisigned In
    '8f' : '<d' # 8 Byte Float
  }
  value = struct.pack(conversions[types[0]], num[0])
  for i in range(1, len(num)):
    value += struct.pack(conversions[types[i]], num[i])
  prefix = struct.pack('B', args[0])
  for i in range(1,len(args)):
    prefix += struct.pack('B', args[i])
  final = prefix + value
  return final

def set_parameters(parameters):
  ser = init_serial()
  # First Reset Parameters to default
  ser.write(bytearray([0xB0, 0x01, 0x01, 0xB0]))
  # time.sleep(0.5)
  # print(ser.readline())
  valid_argument("All Parameters", "Default", ser)

  # Set Burst Count
  if "Burst Count" in parameters:
    ser.write(bytearray([0xB0, 0x03, 0x02] + [int(bt) for bt in struct.pack(">H", parameters["Burst Count"])] + [0xB0]))
    valid_argument("Burst Count", parameters["Burst Count"], ser)
  else:
    print("Burst Count Set To Default: Continuous Streaming")
  
  # Set Frame Rate
  if "Frame Rate" in parameters:
    value = bytearray([0xB0, 0x05, 0x03] + [int(bt) for bt in struct.pack(">f", parameters["Frame Rate"])] + [0xB0])
    ser.write(value)
    valid_argument("Frame Rate", parameters["Frame Rate"], ser)
  else:
    print("Frame Rate Set To Default: 1 Frame/Sec")

  # Set Excitation Frequencies
  if "Excitation Frequencies" in parameters:
    frequencies = []
    if "Fmin" in parameters["Excitation Frequencies"]:
      frequencies.append([int(bt) for bt in struct.pack(">f", parameters["Excitation Frequencies"]["Fmin"])])
    else:
      frequencies.append([int(bt) for bt in struct.pack(">f", 100000)])
    
    if "Fmax" in parameters["Excitation Frequencies"]:
      frequencies.append([int(bt) for bt in struct.pack(">f", parameters["Excitation Frequencies"]["Fmax"])])
    else:
      frequencies.append([int(bt) for bt in struct.pack(">f", 100000)])
    
    if "Fcount" in parameters["Excitation Frequencies"]:
      frequencies.append([int(bt) for bt in struct.pack(">H", parameters["Excitation Frequencies"]["Fcount"])])
    else:
      frequencies.append([int(bt) for bt in struct.pack(">H", 20)])

    if "Ftype" in parameters["Excitation Frequencies"]:
      frequencies.append([parameters["Excitation Frequencies"]["Ftype"]])
    else:
      frequencies.append([1])

    value = bytearray([0xB0, 0x0C, 0x04] + frequencies[0] + frequencies[1] + frequencies[2] + frequencies[3] + [0xB0])
    ser.write(value)
    valid_argument("Excitation Frequency", str(parameters["Excitation Frequencies"]), ser)
  else:
    print("Fmin Set To: 100 kHz")
    print("Fmax Set To: 100 kHz")
    print("Fcount Set To: 1")
    print("Ftype Set To: 0")

  # Set Excitation Amplitude
  if "Excitation Amplitude" in parameters:
    ser.write(bytearray([0xB0, 0x09, 0x05] + [int(bt) for bt in struct.pack(">d", parameters["Excitation Amplitude"])] + [0xB0]))
    valid_argument("Excitation Amplitude", parameters["Excitation Amplitude"], ser)
  else:
    print("Excitation Amplitude Set To Default: 0.01 A")

  # Set Single-Ended or Differential Measure Mode
  if "Single-Ended" in parameters:
    ser.write(bytearray([0xB0, 0x03, 0x08, 0x01, 0x01, 0xB0]))
    # valid_argument()
  if "Differential Measure Mode":
    ser.write(bytearray([0xB0, 0x03, 0x08, parameters["Differential Measure Mode"]["Mode"], parameters["Differential Measure Mode"]["Boundary"], 0xB0]))
    valid_argument("Differential Measure Mode", str(parameters["Differential Measure Mode"]), ser)
  else:
    print("Measure Mode Set To Default: Single-Ended")

  # Set Excitation Sequence
  if "Excitation Sequence" in parameters:
    for sequence in parameters["Excitation Sequence"]:
      Cin, Cout = sequence
      ser.readline()
      ser.write(bytearray([0xB0, 0x05, 0x06] + [int(bt) for bt in struct.pack(">H", Cout)] + [int(bt) for bt in struct.pack(">H", Cin)] + [0xB0]))
    valid_argument("Excitation Sequence", parameters["Excitation Sequence"], ser)
  else:
    print("Excitation Sequence Set To Default: 1→2; 2→3; 3→4; 4→5; 5→6; 6→7; 7→8; 8→9; 9→10; 10→11; 11→12; 12→13; 13→14; 14→15; 15→16; 16→1")

  # Set Excitation Switch Type
  if "Excitation Switch Type" in parameters and parameters["Excitation Switch Type"] == 2:
    ser.write(bytearray([0xB0, 0x02, 0x0C, 0x02, 0xB0]))
    valid_argument("Excitation Switch Type", "Semiconductor Switch", ser)
  else:
    print("Excitation Switch Type Set To Default: ReedRelais")
  
  if "ADC Range" in parameters:
    ser.write(bytearray([0xB0, 0x02, 0x0D, parameters["ADC Range"], 0xB0]))
    valid_argument("ADC Range", parameters["ADC Range"], ser)
  else:
    print("ADC Range Set To Defailt: +- 10V")

def get_measurement_setup():
  ser = init_serial()
  # Get Burst Count
  ser.write(bytearray([0xB1, 0x01, 0x02, 0xB1]))
  output = read_measurment(ser)
  if output != []:
    print(f'Burst Count: {(output[3] << 8) | output[4]}')

  # Get Frame Rate
  ser.write(bytearray([0xB1, 0x01, 0x03, 0xB1]))
  output = read_measurment(ser)
  print("Frame Rate: " + str(struct.unpack('>f', bytes(list(output[3:7])))[0]))

  # Get Excitation Frequencies
  ser.write(bytearray([0xB1, 0x01, 0x04, 0xB1]))
  output = read_measurment(ser)
  if output != []:
    print("Minimum Frequency: " + str(round(struct.unpack(">f", bytearray(output[3:7]))[0], 8)))
    print("Maximum Frequency: " + str(round(struct.unpack(">f", bytearray(output[7:11]))[0], 8)))
    print("Frequency Count: " + str(((output[11] << 8) | output[12])))
    if output[13] == 0:
      print("Frequency Type: Linear Frequency Distribution")
    else:
      print("Frequency Type: Logarithmic Frequency Distribution")

  # Get Excitation Amplitude
  ser.write(bytearray([0xB1, 0x01, 0x05, 0xB1]))
  output = read_measurment(ser)
  if output != []:
    print("Excitation Amplitude: " + str(round(struct.unpack(">f", bytearray(output[3:7]))[0], 8)))

  # Get Excitation Sequence
  ser.write(bytearray([0xB1, 0x01, 0x06, 0xB1]))
  output = read_measurment(ser)
  print("Excitation Sequence:")
  for i in range(0, len(output), 8):
    curr = output[i:i+8]
    print(f'({((curr[5]<< 8) | curr[6])},{((curr[3] << 8) | curr[4])})')

  # Get Single-Ended or Differential Measure Mode
  ser.write(bytearray([0xB1, 0x01, 0x08, 0xB1]))
  output = read_measurment(ser)
  if output != []:
    if output[3] == 1:
      print("Differential Measure Mode: Single ended")
    elif output[3] == 2:
      print("Differential Measure Mode: Differential Skip 0")
    elif output[3] == 3:
      print("Differential Measure Mode: Differential Skip 2")
    elif output[3] == 4:
      print("Differential Measure Mode: Differential Skip 4")
    
    if (output[3] == 2 or output[3] == 3 or output[3] == 4) and output[4] == 1:
      print("Differential Measure Boundary: Internal")   
    elif (output[3] == 2 or output[3] == 3 or output[3] == 4) and output[4] == 1:
      print("Differential Measure Boundary: External")  

  # Get Gain Settings
  ser.write(bytearray([0xB1, 0x01, 0x09, 0xB1]))
  output = read_measurment(ser)
  if output != []:
    print("Gain Settings")
  else:
    print("Gain Setting Were Not Set")

  # Get Excitation Switch Type
  ser.write(bytearray([0xB1, 0x01, 0x0C, 0xB1]))
  output = read_measurment(ser)
  if output != []:
    if output[3] == 1:
      print("Excitation Switch Type: Reed Relay Switches")
    elif output[3] == 2:
      print("Excitation Switch Type: Semiconductor Switches")

  # Get ADC Range
  ser.write(bytearray([0xB1, 0x01, 0x0D, 0xB1]))
  output = read_measurment(ser)
  if output != []:
    if output[3] == 1:
      print("ADC Range: +- 1V")
    elif output[3] == 2:
      print("ADC Range: +- 5V")
    elif output[3] == 3:
      print("ADC Range: +- 10V")

def set_output_config(configs):
  ser = init_serial()
  # Set Excitation Setting
  if "Excitation Setting" in configs:
    ser.write(bytearray([0xB2, 0x02, 0x01, configs["Excitation Setting"], 0xB2]))
    value = "True" if configs["Excitation Setting"] == 1 else "False"
    valid_argument("Excitation Setting", value, ser)
  
  # Set Current row in the frequency stack
  if "Current row in the frequency stack" in configs:
    ser.write(bytearray([0xB2, 0x02, 0x02, configs["Current row in the frequency stack"], 0xB2]))
    value = "True" if configs["Current row in the frequency stack"] == 1 else "False"
    valid_argument("Current row in the frequency stack", value, ser)
  
  # Set Timestamp
  if "Timestamp" in configs:
    ser.write(bytearray([0xB2, 0x02, 0x03, configs["Timestamp"], 0xB2]))
    value = "True" if configs["Timestamp"] == 1 else "False"
    valid_argument("Timestamp", value, ser)

def get_output_config():
  ser = init_serial()
  # Get Excitation Setting
  ser.write(bytearray([0xB3, 0x01, 0x01, 0xB3]))
  output = list(ser.readline())
  print("Excitation Setting: " + ("True" if output[3] == 1 else "False"))

  # Get Current row in the frequency stack
  ser.write(bytearray([0xB3, 0x01, 0x02, 0xB3]))
  output = list(ser.readline())
  print("Current row in the frequency stack: " + ("True" if output[3] == 1 else "False"))

  # Get Timestamp
  ser.write(bytearray([0xB3, 0x01, 0x03, 0xB3]))
  output = list(ser.readline())
  print("Timestamp: " + ("True" if output[3] == 1 else "False"))


def start_measurement():
  ser.write(bytearray([0xB4, 0x01, 0x01, 0xB4]))


def stop_measurement():
  ser.write(bytearray([0xB4, 0x01, 0x00, 0xB4]))
  print(ser.readline())



params = {
  "Burst Count" : 1,
  "Frame Rate" : 1,
  "Excitation Frequencies" : {"Fmin" : 50000, "Fmax": 50000, "Ftype": 0},
  "Excitation Amplitude" : 0.001,
  "Excitation Switch Type" : 2,
  "Excitation Sequence" : [(1,3)],
  "ADC Range" : 2,
  "Differential Measure Mode": {"Mode": 3, "Boundary": 1}
}

configurations = {
  "Excitation Setting" : 0,
  "Current row in the frequency stack" : 0,
  "Timestamp" : 1
}

# # try:
# while True:
#     print("Iteration")
#     data = ser.read_all()
#     if not data:
#         break
#     time.sleep(0.1)
# # finally:
# #     ser.close()

# ser.close()
# stop_measurement()
# print(ser.read_all())
# # ser.read_all()
# ser.write(bytearray([0x90, 0x00, 0x90]))
# ser.write(bytearray([0xa1, 0x00, 0xa1]))
# print(ser.readline())
# set_parameters(params)
# print("--------------------------------")
# get_measurement_setup()
# print("--------------------------------")
# set_output_config(configurations)
# print("--------------------------------")
# get_output_config()
# print("--------------------------------")
# start_measurement()

# timeout_count = 0

# while True:
#   buffer = ser.read()
#   if buffer:
#       print(list(buffer))
#       timeout_count = 0
#       continue
#   timeout_count += 1
#   if timeout_count >= 1:
#       # Break if we haven't received any data
#       break

# stop_measurement()
# ser.close()

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

def process_data(q, stop_event):
  items = []
  while not stop_event.is_set() or not q.empty():
    try:
      item = q.get(timeout=1)
      num = int.from_bytes(item, byteorder='big')
      items.append(num)
    except Empty:
      continue
    except Exception as e:
      print(f"Error converting item {item}: {e}")
    
def StartStopMeasurement(q, stop_event) -> list:
    ser = init_serial()
    print("Starting measurement.")
    ser.write(bytearray([0xB4, 0x01, 0x01, 0xB4]))
    measurement_data_hex = read_from_serial(q, stop_event, ser)
    print("Stopping measurement.")
    ser.write(bytearray([0xB4, 0x01, 0x00, 0xB4]))
    return measurement_data_hex


if __name__ == '__main__':
    q = Queue()
    stop_event = Event()

    set_parameters(params)
    print("--------------------------------")
    get_measurement_setup()
    print("--------------------------------")
    set_output_config(configurations)
    print("--------------------------------")
    get_output_config()
    print("--------------------------------")
    read_process = Process(target=StartStopMeasurement, args=(q, stop_event))
    process_process = Process(target=process_data, args=(q, stop_event))

    read_process.start()
    process_process.start()
