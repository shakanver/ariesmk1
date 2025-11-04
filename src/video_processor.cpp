#include <cstdio>
#include <memory>
#include <cv_bridge/cv_bridge.hpp>
#include <opencv2/highgui/highgui.hpp>
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/image.hpp"
#include <image_transport/image_transport.hpp>


class VideoProcessor : public rclcpp::Node
{
	public:
		VideoProcessor() : Node("video_processor")
		{
			prevTime = now();
			subscription_ = image_transport::create_subscription(
				this,
				"/camera/image_raw",
				std::bind(&VideoProcessor::VideoCallBack, this, std::placeholders::_1),
				"raw",
				rmw_qos_profile_sensor_data);
		}
	
	private:
		rclcpp::Time prevTime;
		image_transport::Subscriber subscription_;

	void VideoCallBack(const sensor_msgs::msg::Image::ConstSharedPtr& msg)  
	{
		auto currTime = this->now();
		auto fps = 1/(currTime - prevTime).seconds();
		prevTime = currTime;
		RCLCPP_INFO(this->get_logger(), " Received image with height: '%d' and width: '%d'", msg->width, msg->height);
		RCLCPP_INFO(this->get_logger(), " fps: '%f'", fps);
		try
		{
			auto frame = cv_bridge::toCvShare(msg, "bgr8")->image;
			cv::Mat rotated;
			// Rotating the images because the pi is currently mounted upside down and I'm too lazy to re-orient it.
			cv::flip(frame, rotated, -1);
			cv::imshow("Camera", rotated);
			cv::waitKey(10);
		}
		catch(const std::exception& e)
		{
			std::cerr << e.what() << '\n';
		}
	}
};

int main([[maybe_unused]] int argc, [[maybe_unused]] char ** argv)
{
	rclcpp::init(argc, argv);
	rclcpp::spin(std::make_shared<VideoProcessor>());
	rclcpp::shutdown();
	return 0;
}
