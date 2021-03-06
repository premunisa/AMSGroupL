#!/usr/bin/env python

"""
This program drives the robot to a given set of coordinates.

It subscribes to the following topics:

- "currentPose", expects PoseStamped messages containing the current pose of the robot.
- "desiredPose", expects Pose messages containing the desired pose for the robot.

"""

# system libraries
import time
import select
import sys
import socket
import os
import math

import numpy as np

# ROS libraries
import rospy
import std_msgs.msg
from geometry_msgs.msg import Point, Quaternion, PoseStamped, Pose
import tf


threshold = 0.1 # units are in metres, reached target if x & y within 0.1 = 10cm of target position
rot_threshold = 0.1	# angle in radians, consider heading correct if within this number of radians to target point
travel_heading_error_window = 0.5 # If angle to target > this during travel, robot will stop and reorient
base_speed = 100 # Default speed robot travels at. Left and right motors are biased from this value to adjust steering.

#rotation settings
rot_P = 20.0
rot_I = 0.0
rot_D = 0.0
rot_error_sum = 0
rot_speed_offset = 5

#driving angle PID
driving_P = 25.0
driving_I = 0.0
driving_D = 0.0
driving_error_sum = 0
	
#current pose variables
x = 0
y = 0
th = 0

#desired pose variables
d_x = 6
d_y = 2
d_th = 0

delay = 0.1 # update rate for main loop (s)

rospy.init_node("motor_pilot", anonymous=False) # name the script on the ROS network

pub = rospy.Publisher("/%s/set/motor_drive" % socket.gethostname(), std_msgs.msg.UInt8MultiArray, queue_size=10) # sets up the topic for publishing the motor commands

time.sleep(0.2) # make sure publisher setup

# send a command to the motors (direction, left_speed, right_speed)
def publish_motor_command(md_d, md_l, md_r):
	motor_data = std_msgs.msg.UInt8MultiArray() # definitions in std_msgs.msg - data to be published need to be in ROS format
	motor_data.data = [1,0,0,1]
	motor_data.data[0] = int(md_d)
	motor_data.data[1] = int(md_l)
	motor_data.data[2] = int(md_r)
	print ("Direction: %d, Left: %d, Right: %d") % (motor_data.data[0], motor_data.data[1], motor_data.data[2]) # print new motor speed on the terminal
	pub.publish(motor_data) # publish motor command to ROS

def pose_subscriber():
	# subscribe to ROS data updates
	PS = rospy.Subscriber("currentPose", PoseStamped, current_pose_update)
	DP = rospy.Subscriber("desiredPose", Pose, desired_pose_update)
	return (PS, DP)

def current_pose_update(data):
	global x, y, th

	# read in position
	x = data.pose.position.x
	y = data.pose.position.y
	
	# read in orientation
	q = (
	    data.pose.orientation.x,
	    data.pose.orientation.y,
	    data.pose.orientation.z,
	    data.pose.orientation.w)
	
	# convert orientation from quaternion to euler angles, read yaw
	euler = tf.transformations.euler_from_quaternion(q)
	th = euler[2]

def desired_pose_update(data):
	global d_x, d_y, d_th

	# read in position
	d_x = data.position.x
	d_y = data.position.y
	
	# read in orientation
	q = (
	    data.orientation.x,
	    data.orientation.y,
	    data.orientation.z,
	    data.orientation.w)
	    
	# convert orientation from quaternion to euler angles, read yaw
	euler = tf.transformations.euler_from_quaternion(q)
	th = euler[2]

# checks if the target coordinates are reached. Returns true if current x/y are near target x/y within set threshold
def coordinates_reached():
	global threshold
	reached = False
	if(distance_between_points(x,y,d_x,d_y) < threshold):
		reached = True
	return reached
	
#calculates difference between two angles
def angular_difference(angle1, angle2):
	# find the raw angular difference
	diff = angle1 - angle2
	
	#make sure it's the shortest distance around 0 etc
	diff = (diff + math.pi) % (2 * math.pi) - math.pi
		
	return diff	

def angle_between_points(x1, y1, x2, y2):
	dx = x1 - x2
	dy = y1 - y2
	
	heading = math.atan2(-dy,-dx)

	return heading
	
def distance_between_points(x1, y1, x2, y2):
	return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
	
def turn_to_face(heading_error):
	global rot_P, rot_speed_offset
	#rotate to face heading
	# start motors moving based on angular difference
	motor_speed = int(round(rot_P * math.fabs(heading_error))) + rot_speed_offset
	#rot_error_sum += heading_error

	if(heading_error > 0):
		rot = 3
	if(heading_error < 0):
		rot = 2
						
	publish_motor_command(rot,motor_speed,motor_speed)

	

def main(argv):
	global x, y, th, d_x, d_y, d_th, driving_P, driving_I, driving_error_sum

	moving = False	# tracks if we are currently moving towards the target point
	
	(current_pose_update, desired_pose_update) = pose_subscriber()
	
	key_pressed = False
	
	# variables for waypoint navigator test
	coordinates_array = [[6, 2.2, math.pi/2], [6, 2.2, math.pi], [6, 2.2, 3 * math.pi/2], [6, 2.2, 2 * math.pi],[5,2.2, -999], [5,0.8,-999], [6, 0.8,-999]]
	num_points = 6
	
	#num_points = 0
	#coordinates_array = np.zeros((20,3))
	
	#list = [[0 for x in range(10)] for x in range(10)] 
	
	"""
	for i in range(0 , 4):
		for j in range (0, 3):
			coordinates_array[3 * i + j][0] = (4 + i / 2)
			coordinates_array[3 * i + j][1] = (1.5)
			coordinates_array[3 * i + j][2] = (j * math.pi/2)
			num_points += 1
			
	"""
	
	index = 0
	justStarted = True # need to track if we've just started, otherwise we can get stuck on the first waypoint.

	while key_pressed == False:
		loop_start = time.time() # get loop time at start for loop rate calculations
		
		# set current waypoint as navigational target
		d_x = coordinates_array[index][0]
		d_y = coordinates_array[index][1]
		d_th = coordinates_array[index][2]
		
		# calculate angular difference
		target_heading = angle_between_points(x,y,d_x,d_y)
		heading_error = angular_difference(target_heading,th)
		
		print("Current Position: %.3f %.3f %.3f | Target Position: %.3f %.3f %.3f | Heading Error: %.3f") % (x,y,th,d_x,d_y,d_th,heading_error)
				
		if(coordinates_reached() == False):
			if(moving == False):
				if(math.fabs(heading_error) < rot_threshold):
					print("Heading achieved! Beginning move towards target!")
					# we're facing the right way, so stop and drive straight!
					# first, stop motors
					publish_motor_command(1,0,0)
					time.sleep(0.5) # make sure message has time to be enacted
					
					# drive straight
					publish_motor_command(0,base_speed,base_speed)
					moving = True
					
					rot_error_sum = 0 #reset PID integrator
					
					time.sleep(0.5) # make sure message has time to be enacted
				else:
					print("Orienting towards target...")
					#rotate to face heading
					# start motors moving based on angular difference
					#motor_speed = int(round(rot_P * math.fabs(heading_error) + rot_I * rot_error_sum))
					#rot_error_sum += heading_error

					#if(heading_error > 0):
					#	rot = 3
					#if(heading_error < 0):
					#	rot = 2
						
					#publish_motor_command(rot,motor_speed,motor_speed)
					
					turn_to_face(heading_error)
			else:
				#if we are moving but coordinates aren't reached...
				if(heading_error > travel_heading_error_window):
					# if we're off course by too much, stop and re-orientate towards target
					publish_motor_command(0,0,0)
					moving = False
					# loop should take over and make things work now we're stopped away from the target
				else:
					#adjust motors to aim towards target point
					motor_left_speed = base_speed - (heading_error * driving_P + driving_error_sum * driving_I)
					motor_left_right = base_speed + (heading_error * driving_P + driving_error_sum * driving_I)
					driving_error_sum += heading_error
					publish_motor_command(0,motor_left_speed,motor_left_right)
					#publish_motor_command(0,base_speed,base_speed)
					
		else:
			print("Coordinates reached!")
			#if we've just reached the point, stop!
			if(moving == True or justStarted == True):
				justStarted = False
				publish_motor_command(0,0,0)
				moving = False
				driving_error_sum = 0
				print("Motors stopped!")
				
			# now, turn to face the desired heading (if there is one)	
			heading_offset = angular_difference(d_th,th)
			
			if(d_th != -999 and math.fabs(heading_offset) > rot_threshold):	#-999 means orientation doesn't matter, otherwise turn
					print("Matching desired orientation...")

					turn_to_face(heading_offset)
			else:
				# loops through waypoints sequentially for test purposes
				if(index < num_points):
					index+=1
				else:
					index=0
					
		loop_sleep = delay - (time.time() - loop_start) # if loop delay too low then will print data faster than updates are recieved
		
		if loop_sleep > 0:
			time.sleep(loop_sleep)
		
		key_pressed = select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []) # is key pressed?
	
	# finally, stop motors
	time.sleep(0.1) # make sure message has time to be enacted
	publish_motor_command(1,0,0)
	time.sleep(0.5) # make sure message has time to be enacted
	
	print ("Exit script, motors stopped")

if __name__ == '__main__': # main loop
	try: # if no problems
		main(sys.argv[1:])
        
	except rospy.ROSInterruptException: # if a problem
 		pass




