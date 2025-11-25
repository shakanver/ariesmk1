from pymavlink import mavutil
import time

'''
TODO: edit this code that I copied from AI lol.
'''

# --- Configuration matching your MAVProxy command ---
DEVICE = '/dev/ttyAMA0'
BAUD_RATE = 921600
MOTOR_NUM = 3   # Motor 3
THROTTLE_TYPE = 0 # 0=Percentage
THROTTLE_VALUE = 20 # 20%
TIMEOUT_SECONDS = 10 # 10 seconds

# The MAVLink command ID for the motor test
MAV_CMD_DO_MOTOR_TEST = 209

"""Connects to the autopilot and sends the MAV_CMD_DO_MOTOR_TEST command."""
print(f"Connecting to {DEVICE} at {BAUD_RATE}...")
try:
	# Establish the MAVLink connection
	master = mavutil.mavlink_connection(DEVICE, baud=BAUD_RATE)
except Exception as e:
	print(f"Error connecting: {e}")
	exit

# Wait for the first heartbeat message to ensure a connection is established
master.wait_heartbeat()
print("Heartbeat received. Connection established.")

for i in range(1, 5):

	# Send the MAV_CMD_DO_MOTOR_TEST command
	# Use master.mav.command_long_send to send any MAVLink command
	master.mav.command_long_send(
		master.target_system,    # Target system (typically 1 for ArduPilot)
		master.target_component, # Target component (typically 1 for ArduPilot)
		MAV_CMD_DO_MOTOR_TEST,   # Command ID
		0,                       # Confirmation (0 is typical, not used for this command)
		MOTOR_NUM,               # param1: Motor sequence number
		THROTTLE_TYPE,           # param2: Throttle type
		THROTTLE_VALUE,          # param3: Throttle value
		TIMEOUT_SECONDS,         # param4: Timeout in seconds
		0, 0, 0                  # param5, param6, param7 (Unused for this command)
	)

	print(f"Sent MAV_CMD_DO_MOTOR_TEST: Motor {MOTOR_NUM} @ {THROTTLE_VALUE}% for {TIMEOUT_SECONDS}s.")

	# Wait for the command acknowledgment
	print("Waiting for command ACK...")
	ack_received = False
	start_time = time.time()
	
	while time.time() - start_time < 5: # Wait up to 5 seconds for ACK
		msg = master.recv_match(type=['COMMAND_ACK'], blocking=True, timeout=0.1)
		if msg:
			if msg.command == MAV_CMD_DO_MOTOR_TEST:
				print(f"Command ACK received: Result {msg.result}")
				ack_received = True
				break
		time.sleep(0.1)

	if not ack_received:
		print("Warning: Did not receive COMMAND_ACK within timeout.")