#!/usr/bin/python

# import libraries
import time

# ROS libraries
import rospy
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Point, Quaternion
from os.path import expanduser
import tf
import socket
import math

#import std_msgs.msg
from std_msgs.msg import *


# define settings
WheelDiameter = 45.0	# wheel diameter in mm
WheelBase = 225.0		# distance between wheels in mm
DistancePerCount = (3.14159 *  WheelDiameter) / (3200) # mm / encoder tick

x = 0.0	# x coordinate in mm
y = 0.0	# y coordinate in mm
th = 0.0	# rotation in radians

vx = 0.0	# instantaneous x velocity
vy = 0.0	# instantaneous y velocity
vth = 0.0	# instantaneous angular velocity

_PreviousLeftEncoderCounts = 0
_PreviousRightEncoderCounts = 0
last_time = 0
current_time = 0

delta_left = 0
delta_right = 0

# setup publishing odometry messages
odom_pub = rospy.Publisher('odom', Odometry, queue_size=10)
rospy.init_node('odom_publisher',anonymous=True)
odom_broadcaster = tf.TransformBroadcaster()

last_time_odom = 0


def wheel_callback(data):
	current_time = time.time()

	left_encoder = data.data[2]
	right_encoder = data.data[3]

	global delta_left, delta_right, _PreviousLeftEncoderCounts, _PreviousRightEncoderCounts, last_time
	
	#calculate the change in encoder values since last message received
	delta_left = left_encoder - _PreviousLeftEncoderCounts
	delta_right = right_encoder - _PreviousRightEncoderCounts
	
	#convert change to distance travelled by each wheel
	vx = delta_left * DistancePerCount
	vy = delta_right * DistancePerCount
	
	#find angular velocity from relative wheel speeds
	vth = -(delta_left - delta_right) / WheelBase

	print('Wheel callback! LE: %d RE: %d DL: %d DR: %d vx: %.3f vy: %.3f vth: %.3f') % (left_encoder, right_encoder, delta_left, delta_right, vx, vy, vth)
	

	#publish calculated values to odometry topic
	publish_odometry(vx, vy, vth)

	#save current values for next time
	_PreviousLeftEncoderCounts = left_encoder
	_PreviousRightEncoderCounts = right_encoder
	last_time = current_time

	
	
	return

def publish_odometry(vx, vy, vth):
	global x, y, th, last_time_odom

	if(last_time_odom == 0):
		last_time_odom = time.time()

	current_time_odom = time.time()
	
	# compute odometry
	dt = (current_time_odom - last_time_odom)# / 1000	# time difference in seconds
	delta_x = (vx * math.cos(th) - vy * math.sin(th)) * dt
	delta_y = (vx * math.sin(th) + vy * math.cos(th)) * dt
	delta_th = vth * dt
	
	
	x += delta_x
	y += delta_y
	th += delta_th

	print('X: %.3f Y: %.3f Theta: %.3f') % (x, y, th)
	
	msg = Odometry()
	msg.header.stamp = rospy.Time.now()
	msg.header.frame_id = 'world'
	
	# create quaternion
	q = tf.transformations.quaternion_from_euler(0, 0, th)
	
	msg.pose.pose.position = Point(x/1000, y/1000, 0)
	msg.pose.pose.orientation.x = q[0]
	msg.pose.pose.orientation.y = q[1]
	msg.pose.pose.orientation.z = q[2]
	msg.pose.pose.orientation.w = q[3]

	#msg.twist.twist.linear.x = vx
	#msg.twist.twist.linear.y = vy
	#msg.twist.twist.angular.z = vth

	odom_pub.publish(msg)

	last_time_odom = current_time_odom


def main():
	
	
	# subscribe to wheel encoder messages
	encoder_ros_update = rospy.Subscriber("/mechbot_12/get/encoder_status", std_msgs.msg.Int32MultiArray, wheel_callback)
	
	
	
	rate = rospy.Rate(1)
	
	while not rospy.is_shutdown():
		rate.sleep()
	
if __name__=='__main__':
	try:
		main()
	except rospy.ROSInterruptException:
		pass
