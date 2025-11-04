#!/usr/bin/env python3
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from cv_bridge import CvBridge
import cv2
from sensor_msgs.msg import Image
from flask import Flask, render_template, Response, request, jsonify, redirect, url_for
import cv2
import logging #TODO: use logging lib to make better logs? 
import time
import os
import threading
import asyncio
import numpy as np


SERVER_IP = "192.168.50.1"

class RemoteControlApi(Node):

	def __init__(self):
		super().__init__('remote_control_api')
		'''Create a subscriber that will receive frames from the ros pi camera node.'''
		self.subscription = self.create_subscription(
			Image,
			'/camera/image_raw',
			self._camera_img_callback,
			10)
		self.subscription 

		self.bridge = CvBridge()
		self.prev_time = self.get_clock().now()
		self.curr_frame = None
		self.lock_curr_frame = threading.Lock()

		'''Create a Python Flask app that will provide a livestream from the raspberry pi camera and except rc controls from the user'''
		templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
		self.app = Flask(__name__, template_folder=templates_dir)
		self._register_routes()

		'''Setting up live streaming using WebRTC'''
		self.peer_connections = set()
		self.peer_connection_logger = logging.getLogger("peerConnection")


	def run_flask_app(self):
		self.app.run(host=SERVER_IP, debug=False, use_reloader=False)

	def _camera_img_callback(self, msg):
        # Compute FPS
		curr_time = self.get_clock().now()
		dt = (curr_time - self.prev_time).nanoseconds / 1e9
		fps = 1.0 / dt if dt > 0 else 0.0
		self.prev_time = curr_time

		'''
		uncomment for debug logs #TODO: find a cleaner way to toggle this log
		'''
		# self.get_logger().info(f"Received image: height={msg.height}, width={msg.width}")
		# self.get_logger().info(f"FPS: {fps:.2f}")

		try:
			# Convert ROS image to OpenCV
			frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
			'''
			uncomment for debug logs #TODO: find a cleaner way to toggle this log
			'''
			self.get_logger().info(f"Frame received: {frame.shape}, FPS ~{fps:.2f}")
			# Flip image (180° rotation)
			rotated = cv2.flip(frame, -1)
			with self.lock_curr_frame:
				self.curr_frame = rotated	

		except Exception as e:
			self.get_logger().error(f"Error processing image: {e}")
	
	def _try_get_curr_frame(self):
		while True:
			with self.lock_curr_frame:
				if self.curr_frame is None:
					continue

				(flag, encodedImage) = cv2.imencode(".jpg", self.curr_frame)
				if not flag:
					continue

			yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
			bytearray(encodedImage) + b'\r\n')

	def _register_routes(self):
		self.app.add_url_rule("/", "index", lambda: render_template('index.html'))
		self.app.add_url_rule("/video_feed", "video_feed", lambda:  Response(self._try_get_curr_frame(), mimetype='multipart/x-mixed-replace; boundary=frame'))

def main(args=None):
	with rclpy.init(args=args):
		remote_controller_api = RemoteControlApi()
		flask_thread = threading.Thread(target=remote_controller_api.run_flask_app)
		try:
				flask_thread.start()
				rclpy.spin(remote_controller_api)
		except (KeyboardInterrupt, ExternalShutdownException):
			pass
		finally:
			flask_thread.join()

if __name__ == '__main__':
    main()