import argparse
from pymavlink import mavutil
from datetime import datetime
import time


arg_parser = argparse.ArgumentParser()
arg_parser.add_argument(
	"--throttle",
	type=int,
	help="Throttle PWM. Range: 1000-2000 (use 1500 to hover)"
)

arg_parser.add_argument(
	"--roll",
	type=int,
	default=1500,
	help="Roll Angle PWM. Range: 1000-2000 (use 1500 for 0 deg)"
)

arg_parser.add_argument(
	"--pitch",
	type=int,
	default=1500,
	help="Pitch Angle PWM. Range: 1000-2000 (use 1500 for 0 deg)"
)
arg_parser.add_argument(
	"--yaw",
	default=1500,
	type=int,
	help="Yaw Angle PWM. Range: 1000-2000 (use 1500 for 0 deg)"
)

arg_parser.add_argument(
	"--hovertime",
	type=int,
	default=5,
	help="Drone Hover Duration in Seconds"
)

args = arg_parser.parse_args()
throttle = args.throttle
roll = args.roll
pitch = args.pitch
yaw = args.yaw
hover_time = args.hovertime

print(throttle)

'''
See: 
https://ardupilot.org/dev/docs/mavlink-rcinput.html
for more information on the RC_CHANNELS_OVERRIDE message parameters.

'''

mavlink_connection = mavutil.mavlink_connection('/dev/ttyAMA0', baud=921600)
mavlink_connection.wait_heartbeat()
print('Hearbeat received. Connection established')

'''
Arm the motors.
'''
"""Sends the MAV_CMD_COMPONENT_ARM_DISARM command to arm the motors."""
print("Arming Motors")
mavlink_connection.mav.command_long_send(
	mavlink_connection.target_system,
	mavlink_connection.target_component,
	mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, # Command ID 400
	0,                                           # Confirmation
	1,                                           # param1: 1 to Arm
	0, 0, 0, 0, 0, 0                             # Unused parameters
)
# Wait for the confirmation message
msg = mavlink_connection.recv_match(type='COMMAND_ACK', blocking=True, timeout=3)
if msg and msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
	print("Arming command accepted.")
else:
	print("Arming failed or command not acknowledged.")


'''
Launch and hover for a desired time period.
'''
print("Launching")
start_time = datetime.now()
while (datetime.now() - start_time).total_seconds() < hover_time:
	mavlink_connection.mav.rc_channels_override_send(
		mavlink_connection.target_system,
		mavlink_connection.target_component,
		roll,
		pitch,
		throttle,
		yaw,
		0,0,0,0
	)

	time.sleep(0.02)


'''
Land.
'''
mavlink_connection.mav.request_data_stream_send(
	mavlink_connection.target_system,
	mavlink_connection.target_component,
	mavutil.mavlink.MAV_DATA_STREAM_RC_CHANNELS,
	10,
	1
)

def get_throttle_from_rc_channel_msg():
	msg = mavlink_connection.recv_match(type='RC_CHANNELS', blocking=True, timeout=3)
	if msg and msg.get_type() == 'RC_CHANNELS':
		return msg.chan3_raw


print("Landing")
curr_throttle = get_throttle_from_rc_channel_msg()
while curr_throttle > 1000:
	desired_throttle = curr_throttle - 50 
	print(f"sending desired throttle: {desired_throttle}")
	mavlink_connection.mav.rc_channels_override_send(
		mavlink_connection.target_system,
		mavlink_connection.target_component,
		roll,
		pitch,
		desired_throttle,
		yaw,
		0,0,0,0
	)
	curr_throttle = get_throttle_from_rc_channel_msg()
	print(f"curr throttle: {curr_throttle}")

print("Sequnce Complete")
