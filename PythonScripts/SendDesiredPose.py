#!/usr/bin/env python

#accepts arguments from command line and parses into desiredPose ROS message for navigation

# system libraries
import time
import sys
import select
import socket

# ROS
import rospy
import std_msgs.msg
from geometry_msgs.msg import Point, Quaternion, PoseStamped
import tf

rospy.init_node("send_desired_pose", anonymous=False) # name the script on the ROS network


# setup publishing pose messages
pose_pub = rospy.Publisher('pose', Pose, queue_size=10)
odom_broadcaster = tf.TransformBroadcaster()

# main program

def main(argv):
    x = float(sys.argv[1])
    y = float(sys.argv[2])
    th = float(sys.argv[3])

    print("x: %.3f  y: %.3f  Th: %.1f") % (x, y, th) # print 2D pose data to terminal
	
    #publish pose data to ros topic
    msg = Pose()

    msg.header.frame_id = 'world'

    q = tf.transformations.quaternion_from_euler(0, 0, th)

    msg.pose.position = Point(x,y,0)

    msg.orientation.x = q[0]
    msg.orientation.y = q[1]
    msg.orientation.z = q[2]
    msg.orientation.w = q[3]

    pose_pub.publish(msg)

    sys.exit()


if __name__ == '__main__':
    main(sys.argv[1:])

