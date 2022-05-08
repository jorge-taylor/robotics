#!/usr/bin/env python3

from logging import shutdown
from termios import VEOL
import rospy
from com2009_msgs.srv import SetBool,SetBoolResponse
from geometry_msgs.msg import Twist

import cv2
from cv_bridge import CvBridge,CvBridgeError
from sensor_msgs.msg import Image,LaserScan
import numpy as np
import time

import math

# Variable declaration
service_name = "identify_colour_service"
find_colour = False

pub = rospy.Publisher('/cmd_vel', Twist, queue_size=10)
vel = Twist()
cvbridge_interface = CvBridge()
front_min = 999
left_min = 999
right_min = 999

def callback_lidar(lidar_data):
    global front_min,left_min,right_min

    # get the front the robot from a +/- 10 degree arc
    front_left_arc = lidar_data.ranges[0:5]
    front_right_arc = lidar_data.ranges[-5:]
    front_arc = np.array(front_left_arc + front_right_arc)

    # get the left side of the robot
    #left_left_arc = lidar_data.ranges[15:38]
    #left_right_arc = lidar_data.ranges[38:60]
    left_left_arc = lidar_data.ranges[15:30]
    left_right_arc = lidar_data.ranges[30:45]
    left_arc = np.array(left_left_arc + left_right_arc)

    # get the right side of the robot
    right_left_arc = lidar_data.ranges[300:323]
    right_right_arc = lidar_data.ranges[323:345]
    right_arc = np.array(right_left_arc + right_right_arc)

    # get the closest distance from the arcs
    front_min = front_arc.min()
    left_min = left_arc.min()
    right_min = right_arc.min()


def callback_service(service_request):
    global find_colour,colour
    
    service_response = SetBoolResponse()

    target_degree = math.pi/5
    # check if recive the request signal
    if service_request.request_signal == True:
        # the robot will turn and face to the colour
        print(f"The '{service_name}' Server received a 'true' request") 
        print("--Turn to the cylinder--")
        turning(target_degree,5)

        # and then identify the colour
        print("--Prepare to find the colour--")
        find_colour = True

        # after identify turning back
        print("--Turning back now--")
        turning(-target_degree,5)
        service_response.response_signal = True
        service_response.response_message = colour

        # Start to navigate
        if colour != "":
            rospy.Subscriber('scan', LaserScan, callback_lidar)
            velocity_changing()
        else:
            print("Sorry, doesnt get the goal colour :(")
         
    else:
        service_response.response_signal = False
        service_response.response_message = "Error"
    return service_response


def turning(turning_degree,wait_time):
        
        startTime = rospy.get_rostime()
            
        vel.angular.z = turning_degree
        pub.publish(vel)

        # wait for 5 secs
        while (rospy.get_rostime().secs - startTime.secs) < wait_time:
            continue
            
        # stop the robot
        print("---Stop the robot now---")
        vel.angular.z = 0.0
        pub.publish(vel)

def velocity_changing():
    start_time = time.time()
    execution_time = 0

    while execution_time < 150:

        execution_time = time.time() - start_time
        print(f"Minimum distance from right wall: {right_min}, time: {execution_time}")

        if front_min > 0.4:
        # Nothing is directly in-front!
            if right_min < 0.33:
                # We are too close to the left wall - back up!
                vel.linear.x = 0
                vel.angular.z = 0.8
                
            elif right_min > 0.38:
                    # We are to far away from the left wall - move closer!
                    vel.linear.x = 0.25
                    vel.angular.z = -0.7

            else:
                    vel.linear.x = 0.25
                    vel.angular.z = 0.7

        else:
                # Obstacle detected in front! Turning away
                vel.linear.x = 0.0
                vel.angular.z = 0.8

        pub.publish(vel)
        

def callback_camera(img_data):
    global find_colour, colour

    # Thresholds for ["Blue", "Red", "Green", "Turquoise", "Yellow", "Purple"]
    #lower_list = [(115, 224, 100), (0, 185, 100), 
    # (25, 150, 100), (75, 150, 100), (25,225,100), (145,225,100)]
    #upper_list = [(130, 255, 255), (10, 255, 255), 
    # (70, 255, 255), (100, 255, 255), (35,255,255), (155,255,255)]
    
    blue_lower = (115, 224, 100)
    blue_upper = (130, 255, 255)
    red_lower = (0, 185, 100)
    red_upper = (10, 255, 255)
    green_lower = (25, 150, 100)
    green_upper = (70, 255, 255)
    turquoise_lower = (75, 150, 100)
    turquoise_upper = (100, 255, 255)
    yellow_lower = (25, 225, 100)
    yellow_upper = (35, 255, 255)
    purple_lower = (145, 225, 100)
    purple_upper = (155, 255, 255)


    try:
        cv_img = cvbridge_interface.imgmsg_to_cv2(img_data, desired_encoding="bgr8")
    except CvBridgeError as e:
        print(e)

    height, width,_ = cv_img.shape
    crop_width = width - 800
    crop_height = 400
    crop_x = int((width/2) - (crop_width/2))
    crop_y = int((height/2) - (crop_height/2))

    crop_img = cv_img[crop_y:crop_y+crop_height, crop_x:crop_x+crop_width]
    hsv_img = cv2.cvtColor(crop_img, cv2.COLOR_BGR2HSV)    
    # create a single mask to accommodate all six dectection colours:
    blue = cv2.inRange(hsv_img, blue_lower, blue_upper).mean(axis=0).mean(axis=0)
    red = cv2.inRange(hsv_img, red_lower, red_upper).mean(axis=0).mean(axis=0)
    green = cv2.inRange(hsv_img, green_lower, green_upper).mean(axis=0).mean(axis=0)
    turquoise = cv2.inRange(hsv_img, turquoise_lower, turquoise_upper).mean(axis=0).mean(axis=0)
    yellow = cv2.inRange(hsv_img, yellow_lower, yellow_upper).mean(axis=0).mean(axis=0)
    purple = cv2.inRange(hsv_img, purple_lower, purple_upper).mean(axis=0).mean(axis=0)
      
    # Start to find the colour
    while find_colour == True:
        if (int(blue) == 255):
            colour = "Blue"
        elif (int(red) == 255):
            colour = "Red"
        elif (int(green) == 255):
            colour = "Green"
        elif (int(yellow) == 255):
            colour = "Yellow"
        elif (int(turquoise) == 255):
            colour = "Turquoise"
        elif (int(purple) == 255):
            colour = "Purple"
        else:
            colour = "can't read the colour"
            
        # Give a feedback
        print (f"SRARCH INITIATED: The target beacon colour is {colour}")
        find_colour = False

rospy.Subscriber("/camera/rgb/image_raw", Image, callback_camera)
rospy.init_node(f"{service_name}_server")
my_service = rospy.Service(service_name, SetBool, callback_service)

rospy.loginfo(f"the '{service_name}' Server is ready to be called...")
rospy.spin()