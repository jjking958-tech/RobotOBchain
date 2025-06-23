# coding=UTF-8
import json
import os
import pathlib
import sys

sys.path.append('/usr/lib/python2.7/dist-packages')
sys.path.append('/usr/lib/python3/dist-packages')
sys.path.append('/usr/local/webots/lib/controller/python39')
sys.path.append('/opt/ros/melodic/lib/python2.7/dist-packages')
sys.path.append(os.path.dirname(os.path.realpath(__file__)))

from controller import Robot,Camera,LED,Supervisor
from torch.utils.tensorboard import SummaryWriter
import time,random,math,numpy
import socket
import _thread as thread
import traceback
import rospy
import rosbag
from std_msgs.msg import String
import rsa


class RobotController:
    def __init__(self):
        self.robot = Supervisor()
        config_path = pathlib.Path(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))) / "config" / "config.json"
        with open(str(config_path), encoding='utf-8') as f:
            config = json.load(f)
        self.black_ratio = config["black_ratio"]
        self.tiles_quantity = config["tiles_quantity"]
        self.size = config["size"]
        self.robots_quantity = config["robots_quantity"]
        self.time_step = config["time_step"]
        self.byzantine_quantity = config["byzantine_quantity"]
        self.serial_number = config["serial_number"]
        self.group_quantity = config["group_quantity"]
        self.communication_range = config["communication_range"]
        self.max_velocity = config["max_velocity"]
        self.result_path = config["result_path"]
        self.time_factor = self.time_step / 100.0
        self.robot_id = int(self.robot.getCustomData())
        self.TURN = int(5 * 1000 / self.time_step)
        self.LAMDA = int(10 * 1000 / self.time_step)
        self.sigma =int(1 * 1000 / self.time_step)
        self.alpha = 1.0
        self.steps = 0
        self.consensus_reached = False
        self.direction = 0
        self.last_front_obstacle = None
        self.last_right_obstacle = None
        self.last_left_obstacle = None
        self.action_time = 0
        self.do_action = None
        self.do_last_action = None
        self.do_move_back = None
        self.remaining_time = self.LAMDA
        self.remaining_exploration_time = self.sigma
        self.STOPLOOP = False
        self.black_count = 0
        self.white_count = 0
        self.vote_flag = True
        self.quality = None
        self.vote_id = 0
        self.votes = []
        self.neighbors = None
        self.agent_pk = None
        self.robot_pk, self.robot_sk = rsa.newkeys(1024)
        ps_sensor_name = ['ps0', 'ps1', 'ps2', 'ps3', 'ps4', 'ps5', 'ps6', 'ps7']
        # 关联并使能传感器设备
        self.ps_sensor = []
        for i_ in range(len(ps_sensor_name)):
            self.ps_sensor.append(self.robot.getDevice(ps_sensor_name[i_]))
            self.ps_sensor[i_].enable(int(self.time_step / 2))
        # 关联camera
        camera_time_step = int(self.time_step / 2)
        self.camera = self.robot.getDevice('camera')
        self.camera.enable(camera_time_step)
        # 关联LED
        led_name = ['led1', 'led3', 'led5', 'led7']
        led_num = 4
        self.led = []
        for i_ in range(led_num):
            self.led.append(LED(led_name[i_]))
            # 关联电机设备
        self.left_motor = self.robot.getDevice('left wheel motor')
        self.right_motor = self.robot.getDevice('right wheel motor')
        # 设置电机运行模式
        self.left_motor.setPosition(float('inf'))
        self.right_motor.setPosition(float('inf'))

    def reset(self):
        rospy.loginfo(f"robot_{self.robot_id} reset")
        supvisornode = self.robot.getFromDef(f"epuck{self.robot_id}")
        supvisornode.restartController()

    def step(self):
        self.time_stamp = self.robot.getTime()
        self.steps += 1
        self.robot.step(self.time_step)

    def turn_on_led(self):
        if self.black_count < self.white_count:
            self.led[1].set(0x00ff00) #green led, if white
        else:
            self.led[1].set(0xff0000) #red led, if black
        
    def turn_off_led(self):
        self.led[1].set(0x000000)

    def move(self):
        if self.direction == 0:
            self.do_last_action = self.forward
        elif self.direction == 1:
            self.do_last_action=self.turn_right
        elif self.direction == 2:
            self.do_last_action=self.turn_left
        
    def random_move(self):
        random_num = -1+2*random.random()
        self.left_motor.setVelocity(random_num * self.max_velocity)
        self.right_motor.setVelocity(-random_num * self.max_velocity)

    def turn_left(self):
        self.left_motor.setVelocity(-self.max_velocity)
        self.right_motor.setVelocity(self.max_velocity)

    def turn_right(self):
        self.left_motor.setVelocity(self.max_velocity)
        self.right_motor.setVelocity(-self.max_velocity)

    def forward(self):
        self.left_motor.setVelocity(self.max_velocity)
        self.right_motor.setVelocity(self.max_velocity)

    def backward(self):
        self.left_motor.setVelocity(-self.max_velocity)
        self.right_motor.setVelocity(-self.max_velocity)
    
    def stop(self):
        self.left_motor.setVelocity(0.0)
        self.right_motor.setVelocity(0.0)

    def do_action(self):
        rospy.loginfo("do action")

    def do_last_action(self):
        rospy.loginfo("do last action")
    
    def obstacle_avoidance(self):
        ps_sensor_value = []
        for i_ in range(len(self.ps_sensor)):
            ps_sensor_value.append(self.ps_sensor[i_].getValue())
        dis = 100
        right_obstacle = ps_sensor_value[2] > dis or ps_sensor_value[1] > dis or ps_sensor_value[0] > dis
        left_obstacle = ps_sensor_value[5] > dis or ps_sensor_value[6] > dis or ps_sensor_value[7] > dis
        front_obstacle = right_obstacle and left_obstacle
        self.do_random_move = 0
        if front_obstacle:
            self.do_action = self.backward
        elif right_obstacle:
            self.do_action = self.turn_left
        elif left_obstacle:
            self.do_action = self.turn_right
        elif self.last_front_obstacle:
            if random.choice([True, False]):
                self.do_action = self.turn_right
            else:
                self.do_action = self.turn_right
        elif self.do_random_move:
            self.do_action = self.random_move
        elif self.do_last_action == self.random_move:
            self.do_action = self.forward
        else:
            self.do_action = self.do_last_action
        self.last_front_obstacle = front_obstacle
        if self.do_last_action == self.turn_left or self.do_last_action == self.turn_right:
            if self.action_time == 1:
                self.action_time -= 1
                self.do_action = self.random_move
            if self.action_time > 0:
                self.do_action = self.do_last_action
                self.do_action()
                self.action_time -= 1
            else:
                self.action_time = 3
        elif self.do_last_action == self.backward or self.do_last_action == self.forward or self.do_last_action == self.random_move:
            self.do_action()
        self.do_last_action = self.do_action

    def random_walk(self):
        if self.remaining_time <= 0:
            if self.direction == 0:
                p = random.uniform(0, 1)
                p = p * self.TURN
                dir = random.uniform(-1, 1)
                if dir > 0:
                    self.direction = 1
                else:
                    self.direction = 2
                self.remaining_time = math.floor(p)
            else:
                self.remaining_time = math.ceil(numpy.random.exponential(self.LAMDA))

                self.direction = 0
        else:
            self.remaining_time -= 1

    def detect_color(self, array):
        if array[0] < 10 and array[1] < 20 and array[2] < 20:
            return "black"
        elif array[0] > 200 and array[1] > 200 and array[2] >200:
            return "white"
        elif abs(array[0]-197) < 10 and abs(array[1]-60) <20 and abs(array[2]-60)<20:
            return "red"
        elif abs(array[0]-0) < 20 and abs(array[1]-207) <20 and abs(array[2]-207)<20:
            return "blue"
        else:
            return "undefined"

    def image_process(self, img_array, color):
        black_num = 0
        row = len(img_array)
        colum = len(img_array[0])
        half = row * colum / 2
        for i in range(row):
            for j in range(colum):
                if self.detect_color(img_array[i][j]) == color:
                    black_num = black_num + 1
            if black_num > half:
                return 1
        return 0
    
    def detect_cell(self):
        image_array = self.camera.getImageArray()
        flag = self.image_process(image_array, "black")
        if flag:
            self.black_count += 1
        else:
            self.white_count += 1

    def explore(self):
        self.detect_cell()
        self.quality = 1.0 * self.alpha * self.black_count / (self.black_count + self.white_count)
        if self.remaining_exploration_time > 0:
            self.remaining_exploration_time -= 1
        else:
            self.vote_flag = True
            self.remaining_exploration_time = math.ceil(self.sigma)
            #重置reset
            self.black_count = 0
            self.white_count = 0

    def get_position_index(self, pos):
        x = "%.3f"%pos[0]
        z = "%.3f"%pos[2]
        xstr=str(x).split('.')[0]+'.'+str(x).split('.')[1][:1]+'5'
        zstr=str(z).split('.')[0]+'.'+str(z).split('.')[1][:1]+'5'
        return point_index_dict[(xstr,zstr)]
        
    def vote(self):

        self.vote_id += 1

        neighbor_positionDict={}
        for i in range(len(self.neighbors)):
            if self.neighbors[i]==1:
                epuck = self.robot.getFromDef(f"epuck{i}")
                pos=epuck.getPosition()
                neighbor_pos = self.get_position_index(pos)
                neighbor_positionDict[i] = neighbor_pos
        msg="[%2d, %f, %s, %d, %s]" % (self.robot_id,self.time_stamp,self.quality,self.vote_id,str(neighbor_positionDict))
        rospy.loginfo(f"vote:{msg} lenth={len(msg)}")
        self.votes.append(self.quality)

        # #加密数据，并签名
        if self.agent_pk is not None:
            # use receiver's public key encrypt the msg,
            # use hash function create a digital digest
            # and use sender's secret key sign the digest
            encrypted_msg = str(rsa.encrypt(message=msg.encode(), pub_key=self.agent_pk))
            sign = rsa.sign(message=msg.encode(), priv_key=self.robot_sk, hash_method="SHA-256")
            rospy.loginfo(f'sign:{sign}')
            encrypted_msg_with_sign = str({"encrypted_msg": encrypted_msg,"signature": sign})
        else:
            encrypted_msg_with_sign = None
        pub_vote.publish(encrypted_msg_with_sign)

        # #记录数据rosbag
        bag_msg = String()
        bag_msg.data = msg
        bag.write(f'/robot_{self.robot_id}/vote', bag_msg)
        file_path = f'{self.result_path}/byz_{self.byzantine_quantity}/run_{self.serial_number}/robot_{self.robot_id}'
        if not os.path.exists(file_path):
            os.makedirs(file_path)
        with open(f'{file_path}/votes.txt', 'a') as f:
            f.write(str(msg))
            f.write("\n")

    def connect_listen(self):
        self.neighbors = self.get_neighbors()
        if 1 in self.neighbors:
            self.turn_on_led()         #Turn Leds On
        else:
            self.turn_off_led()

        if self.vote_flag:
            self.vote()
            self.vote_flag = False


    def get_distance(self, pos1, pos2):
        dist = math.sqrt((pos1[0]-pos2[0])**2+(pos1[2]-pos2[2])**2)
        return dist
        
    def get_neighbors(self):
        global isConnecting
        pos_list = []
        neighbor=[[0]*self.robots_quantity for i in range(self.robots_quantity)]
        for i in range(self.robots_quantity):
            epuck=self.robot.getFromDef("epuck"+str(i))
            pos=epuck.getPosition()
            pos_list.append(pos[0:3])
            for j in range(i):
                dist=self.get_distance(pos_list[j],pos_list[i])
                if dist < self.communication_range:
                    neighbor[j][i]=1
                    neighbor[i][j]=1
        if neighbor[self.robot_id]:
            isConnecting = True
        else:
            isConnecting = False
        return neighbor[self.robot_id]

    def updateNeighbors(self):
        global oldNeighbors
        newNeighbors = self.get_neighbors()
        diffNeighbors = [1 if a ==1 and b==0 else 0 for a, b in zip(newNeighbors, oldNeighbors)]
        oldNeighbors = newNeighbors
        return diffNeighbors

    def save_result(self, result):
        with open(f'{self.result_path}/all_estimate.csv', "a") as f:
            f.write(result)
            f.write("\n")

    def calculate_mean(self, x):
        global self_count, self_mean, self_m2, self_se
        self_count = self_count + 1
        delta = x - self_mean
        self_mean = self_mean + delta / self_count
        delta2 = x - self_mean
        self_m2 = self_m2 + delta * delta2
        if self_count > 2:
            sd = math.sqrt(self_m2 / (self_count - 1))
            self_se = sd / math.sqrt(self_count)

    def callback_result(self, result):
        data = result.data
        rospy.loginfo(f"robot_{self.robot_id} received a result:{data}")
        if  data != "end":
            resultList = eval(data)  #
            if resultList[3] == True:
                total_time = self.robot.getTime()
                self.save_result(
                    f"{resultList[0]},{resultList[1]},{resultList[2]},{resultList[3]},{resultList[4]},"
                    f"{resultList[5]},{resultList[6]},{resultList[7]},{resultList[8]},{total_time}")

        else:
            rospy.loginfo(f"{self.robot_id} end...")
            self.STOPLOOP = True

    def callback_recv_pk(self, agent_pk):
        self.agent_pk = rsa.key.PublicKey.load_pkcs1(eval(agent_pk.data), format='DER')
        rospy.loginfo(f"agent_{self.robot_id} public key: {self.agent_pk}")


def run_loop():
    while rc.step() != -1:
        rate.sleep()
        pub_robot_pk.publish(str(rc.robot_pk.save_pkcs1(format='DER')))
        try:
            if rc.steps > rc.sigma:
                rc.connect_listen()
            rc.move()

            rc.explore()  # explore and estimate

            rc.obstacle_avoidance()
            rc.random_walk()
            if rc.STOPLOOP:
                rc.stop()
                break
        except Exception as e:
            traceback.print_exc(e)

if __name__ == '__main__':
    #global variable
    grids_index = [20*i + j for i in range(20) for j in range(20)]
    grids_points = [('{:.2f}'.format(-1.05+0.1*(i+1)),'{:.2f}'.format(-1.05+0.1*(j+1))) for i in range(20) for j in range(20)]
    point_index_dict = dict(zip(grids_points, grids_index))
    index_point_dict = dict(zip(grids_index, grids_points))

    rc = RobotController()

    rospy.loginfo(f'Success create robot_{rc.robot_id} controller instance')
    rospy.init_node(f"robot_{rc.robot_id}")
    # 数据记录
    file_path = f'{rc.result_path}/byz_{rc.byzantine_quantity}/run_{rc.serial_number}/robot_{rc.robot_id}/dataset.bag'
    if not os.path.exists(os.path.dirname(file_path)):
        os.makedirs(os.path.dirname(file_path))
    if not os.path.exists(file_path):
        with open(file_path, 'w') as f:
            pass
    bag = rosbag.Bag(file_path, 'w')
    pub_vote = rospy.Publisher(f'/robot_{rc.robot_id}/vote', String, queue_size=1)
    pub_robot_pk = rospy.Publisher(f'/robot_{rc.robot_id}/robot_pk', String, queue_size=1)
    rospy.Subscriber(f'/robot_{rc.robot_id}/result', String, rc.callback_result)
    rospy.Subscriber(f'/robot_{rc.robot_id}/agent_pk', String, rc.callback_recv_pk)
    rate = rospy.Rate(10.0)

    run_loop()

    bag.close()
    total_seconds = rc.robot.getTime()
    rospy.loginfo(f"total time is {total_seconds} seconds")