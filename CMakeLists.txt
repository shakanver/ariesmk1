cmake_minimum_required(VERSION 3.8)
project(ariesmk1)

# Default to C++14
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 14)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclpy REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(image_transport REQUIRED)
find_package(OpenCV REQUIRED)

add_executable(video_processor src/video_processor.cpp)

target_include_directories(video_processor PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include/${PROJECT_NAME}>)
target_compile_features(video_processor PUBLIC c_std_99 cxx_std_17)  # Require C99 and C++17

install(TARGETS video_processor
  DESTINATION lib/${PROJECT_NAME})

# during the build also install the python package located in src/ariesmk1
# TODO: this might not actually be doing anything, need to confirm 
ament_python_install_package(${PROJECT_NAME})

# Install Python executables
install(PROGRAMS
  ariesmk1/remote_control_api.py
  DESTINATION lib/${PROJECT_NAME}
)

install(PROGRAMS
  ariesmk1/templates/index.html
  DESTINATION lib/${PROJECT_NAME}/templates/
)

install(PROGRAMS
  ariesmk1/static/main.js
  DESTINATION lib/${PROJECT_NAME}/static/
)

include_directories(${OpenCV_INCLUDE_DIRS})
target_link_libraries(video_processor PUBLIC
  ${sensor_msgs_TARGETS}
  cv_bridge::cv_bridge
  image_transport::image_transport
  rclcpp::rclcpp
  sensor_msgs::sensor_msgs_library
  ${OpenCV_LIBRARIES}
)


if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # the following line skips the linter which checks for copyrights
  # comment the line when a copyright and license is added to all source files
  set(ament_cmake_copyright_FOUND TRUE)
  # the following line skips cpplint (only works in a git repo)
  # comment the line when this package is in a git repo and when
  # a copyright and license is added to all source files
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()