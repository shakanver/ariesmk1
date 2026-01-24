#!/usr/bin/env python3
from flask import Flask, render_template, Response, request, jsonify, redirect, url_for, make_response
import cv2
import logging #TODO: use logging lib to make better logs? 
import time
import os
import threading
import asyncio
import numpy as np
from pymavlink import mavutil

'''
#TODO:	
- add failsafe in case wifi drops, need to do some sort of emergency landing
- Figure out how to stream video without ROS
'''
SERVER_IP = "192.168.50.1"
THROTTLE_INCREMENT = 50

logging.basicConfig(format='%(asctime)s %(message)s')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class RemoteControlApi():

	def __init__(self):

		'''Create a Python Flask app that will provide a livestream from the raspberry pi camera and except rc controls from the user'''
		templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
		self.app = Flask(__name__, template_folder=templates_dir)
		self._register_routes()
		self.curr_throttle = 1000
		self.last_throttle_channel_msg = None 
		self.last_command_ack = None
		self.user_armed_motors = False

		'''Initialize connection to flight controller to send command via mavlink protocol '''
		try:
			self.mavlink_connection = mavutil.mavlink_connection('/dev/ttyAMA0', baud=921600)
			heartbeat = self.mavlink_connection.wait_heartbeat(timeout=3)
			if not heartbeat:
				logger.error("No heartbeat received from flight controller. Mavlink connection failed.")
			else:
				logger.info("Hearbeat received from flight controller. Mavlink connection successful.")
				self._start_mavlink_reader()

		except Exception as e:
			logger.error(f"Failed to connect to flight controller via mavlink: {e}")

	def _start_mavlink_reader(self):
		def reader():
			while True:
				try:
					msg = self.mavlink_connection.recv_match(blocking=True, timeout=1)
					if msg:
						if msg.get_type() == 'RC_CHANNELS':
							self.last_throttle_channel_msg = msg.chan3_raw
						elif msg.get_type() == 'COMMAND_ACK':
							self.last_command_ack = msg
				except Exception as e:
					logger.error(f"MAVLink reader error: {e}")
					# try to recover after short delay
					time.sleep(1)
				finally:
					time.sleep(0.01)  # prevent tight loop

		t = threading.Thread(target=reader, daemon=True)
		t.start()

	'''
	Flask API Methods
	'''
	def run_flask_app(self):
		self.app.run(host=SERVER_IP, debug=False, use_reloader=False)
	
	def _try_get_curr_frame(self):
		img = np.zeros((480, 640, 3), dtype=np.uint8)
		_, encodedImage = cv2.imencode(".jpg", img)

		yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
		bytearray(encodedImage) + b'\r\n')

	def _try_get_curr_thrust(self):
			msg = self.mavlink_connection.recv_match(type='RC_CHANNELS', blocking=True, timeout=3)
			if msg and msg.get_type() == 'RC_CHANNELS':
				return msg.chan3_raw
			return None

	def _arm_motors(self):
		logger.info("Arming motors")
        
		# MAV_CMD_COMPONENT_ARM_DISARM = 400
		# param1: 1 = ARM, 0 = DISARM
		self.mavlink_connection.mav.command_long_send(
			self.mavlink_connection.target_system,
			self.mavlink_connection.target_component,
			mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
			0, # confirmation
			1, # param1 (1=ARM)
			0, 0, 0, 0, 0, 0 # param2-7 (unused)
		)

		# Check for the confirmation message
		try:
			if self.last_command_ack and self.last_command_ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
					self.user_armed_motors = True
					return make_response(jsonify({"message": "Arming command accepted."}), 200)
			else:
					return make_response(jsonify({"message": "Arming failed or command not acknowledged."}), 500)
		except Exception as e:
			error_msg = f"Error during arming: {e}"
			logger.error(error_msg)
			return make_response(jsonify({"message": error_msg}), 500)
		
	def _set_thrust(self):
		params = request.get_json()
		if not params:
			return jsonify({"error": "JSON data received was null or empty"}, 400)

		if not self.user_armed_motors:
			return jsonify({"error": "Motors not armed. Please arm motors before setting thrust."}, 400)

		direction = params["direction"]
		if not direction:
			return jsonify({"error": "JSON data received does not contain thrust direction"}, 400)

		direction = direction.lower()

		if direction.lower() not in ['up', 'down']:
			return jsonify({"error": "JSON data received does not contain thrust direction"}, 400)

		# rc_msg = self._try_get_curr_thrust()
		# print(f"rc message received: {rc_msg}")
		# if rc_msg is None or rc_msg == 0:
		# 	curr_throttle = 1000
		# else:
		# 	curr_throttle = rc_msg

		if direction == 'up':
			self.curr_throttle += THROTTLE_INCREMENT
		elif direction == 'down':
			self.curr_throttle -= THROTTLE_INCREMENT
		
		# Clamp throttle to valid range
		self.curr_throttle = max(1000, min(2000, self.curr_throttle))

		logger.info(f"Sending curr throttle: {self.curr_throttle}")
		NO_OVERRIDE = 65535	
		self.mavlink_connection.mav.rc_channels_override_send(
			self.mavlink_connection.target_system,
			self.mavlink_connection.target_component,
			NO_OVERRIDE,NO_OVERRIDE,
			self.curr_throttle,
			NO_OVERRIDE,NO_OVERRIDE,NO_OVERRIDE,NO_OVERRIDE,NO_OVERRIDE
		)

		return Response()
		
	def _register_routes(self):
		self.app.add_url_rule("/", "index", lambda: render_template('index.html'))
		self.app.add_url_rule("/video_feed", "video_feed", lambda:  Response(self._try_get_curr_frame(), mimetype='multipart/x-mixed-replace; boundary=frame'))
		self.app.add_url_rule("/arm_motors", "arm_motors", self._arm_motors, methods=['POST'])
		self.app.add_url_rule("/thrust", "thrust", self._set_thrust, methods=['POST'])


def main(args=None):
	remote_controller_api = RemoteControlApi()
	remote_controller_api.run_flask_app()

if __name__ == '__main__':
    main()