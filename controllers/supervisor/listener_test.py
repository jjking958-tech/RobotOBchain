# coding=UTF-8
import os
import sys

sys.path.append('/usr/local/webots/lib/controller/python39')
sys.path.append('/opt/ros/melodic/lib/python2.7/dist-packages')
sys.path.append(os.path.dirname(os.path.realpath(__file__)))
import rospy
from std_msgs.msg import String

def callback(data):
    print(data.data)

def listener():
    rospy.init_node('listener', anonymous=True)
    rospy.Subscriber(f'/robot_0/vote', String, callback)
    rospy.spin()

if __name__ == '__main__':
    listener()