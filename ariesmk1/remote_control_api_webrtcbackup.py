#!/usr/bin/env python3
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from cv_bridge import CvBridge
import cv2
from sensor_msgs.msg import Image
from flask import Flask, render_template, Response, request, jsonify, redirect, url_for
import socket
import sdp_transform
from aiortc.rtcicetransport import RTCIceGatherer
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCIceServer, RTCConfiguration, rtcicetransport, RTCIceCandidate
from av import VideoFrame
import cv2
import uuid
import logging
import time
import os
import threading
import asyncio
import numpy as np
import fractions


SERVER_IP = "192.168.50.1"
RTC_VIDEO_STREAM_PORT = 51505

class CameraStreamTrack(VideoStreamTrack):
	kind = "video"
	def __init__(self, get_frame_func):
		super().__init__()
		self.get_frame_func = get_frame_func
		self.frame_count = 0

	async def recv(self):
		self.frame_count += 1
		print(f"===================Sending frame {self.frame_count}=========================")
		frame = self.get_frame_func()
		video_frame = VideoFrame.from_ndarray(frame, format="rgb24")
		video_frame.pts = self.frame_count
		video_frame.time_base = fractions.Fraction(1, 30)
		return video_frame

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

		# self.get_logger().info(f"Received image: height={msg.height}, width={msg.width}")
		# self.get_logger().info(f"FPS: {fps:.2f}")

		try:
			# Convert ROS image to OpenCV
			frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
			# self.get_logger().info(f"Frame received: {frame.shape}, FPS ~{fps:.2f}")
			# Flip image (180° rotation)
			rotated = cv2.flip(frame, -1)
			with self.lock_curr_frame:
				self.curr_frame = rotated	

		except Exception as e:
			self.get_logger().error(f"Error processing image: {e}")
	
	def _get_curr_frame(self):
		with self.lock_curr_frame:
			return self.curr_frame

	def _register_routes(self):
		self.app.add_url_rule("/", "index", lambda: render_template('index.html'))
		self.app.add_url_rule("/video_feed", "video_feed", lambda:  Response(self._generate_video_feed(), mimetype='multipart/x-mixed-replace; boundary=frame'))
		self.app.add_url_rule("/offer", "offer", self._offer, methods=['POST'])
		self.app.add_url_rule("/currpc", "candidate", self._currpc, methods=['GET'])
	
	async def _currpc(self):
		currpc = next(iter(self.peer_connections))
		ret = f"connection state: {currpc.connectionState} ice connection state: {currpc.iceConnectionState}"
		return jsonify({"status": ret})
	
	async def _offer(self):
		params = request.get_json()
		if not params:
			return jsonify({"error": "Invalid JSON data"}), 400

		offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
		
		pc = RTCPeerConnection()
		pc_id = "PeerConnection(%s)" % uuid.uuid4()
		self.peer_connections.add(pc)

		video_track = CameraStreamTrack(self._get_curr_frame)
		pc.addTrack(video_track)

		def log_info(msg, *args):
			self.peer_connection_logger.info(pc_id + " " + msg, *args)

		log_info("Created for %s", request.remote_addr)

		@pc.on("connectionstatechange")
		async def on_connectionstatechange():
			print("Connection State: ", pc.connectionState)
			if pc.connectionState == "failed":
				await pc.close()
				self.peer_connections.discard(pc)
		
		@pc.on("icegatheringstatechange")
		def on_ice_gathering_state_change():
			print("ICE gathering state:", pc.iceGatheringState)

		@pc.on("iceconnectionstatechange")
		def on_ice_connection_state_change():
			print("ICE connection state:", pc.iceConnectionState)

		@pc.on("track")
		def on_track(track):
			print(f"[pc] on_track: kind={track.kind}, id={track.id}")
		
		@pc.on("icecandidate")
		async def on_icecandidate(candidate):
			if candidate:
				# Send to client via signaling (e.g., WebSocket or poll, but for simplicity, log or assume bundled)
				print(f"Server ICE candidate: {candidate.candidate}")
			else:
				print("Server all ICE candidates gathered.")

		await pc.setRemoteDescription(offer)
		answer = await pc.createAnswer()

		# sdp_dict = sdp_transform.parse(answer.sdp)
		# print("SDP DICT KEYS")
		# for media in sdp_dict['media']:
		# 	media['candidates'] = [c for c in media.get('candidates', []) if '192.168.50.' in c['ip']]

		# 	if 'connection' in media:
		# 		media['connection']['ip'] = '192.168.50.1'

		# filtered_sdp = sdp_transform.write(sdp_dict)
		# answer.sdp = filtered_sdp
		await pc.setLocalDescription(answer)

		print("Sleeping for a bit")
		await asyncio.sleep(20)

		print("Sending answer now!")

		return jsonify({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type})	

		
def main(args=None):
	logging.basicConfig(level=logging.INFO)
	logging.getLogger("aiortc").setLevel(logging.DEBUG)
	logging.getLogger("aioice").setLevel(logging.DEBUG)

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