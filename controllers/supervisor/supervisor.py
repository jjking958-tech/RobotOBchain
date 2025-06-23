# coding=UTF-8
import json
import math
import numpy as np
import os
import pathlib
import random
import sys

sys.path.append('/usr/local/webots/lib/controller/python39')
sys.path.append('/opt/ros/melodic/lib/python2.7/dist-packages')
sys.path.append(os.path.dirname(os.path.realpath(__file__)))
from controller import Supervisor
import rospy
from std_msgs.msg import String


class BlackWhiteGridEnv:
    def __init__(self):
        self.supervisor = Supervisor()

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
        self.group_quantity = config["group_quantity"]
        self.communication_range = config["communication_range"]
        blacktiles = random.sample(range(self.tiles_quantity), int(self.tiles_quantity * self.black_ratio))
        edge_number = int(math.sqrt(self.tiles_quantity))
        x_z = [(0.1 * (i + 1) - self.size / 2 - 0.05, 0.1 * (j + 1) - self.size / 2 - 0.05) for i in range(edge_number)
               for j in range(edge_number)]
        y_ = [0 for i in range(self.robots_quantity)]
        rolist = [i / 100.0 for i in range(0, 628, int(628 / self.robots_quantity))]
        rgblist = ["none" for i in range(self.robots_quantity)]
        random.shuffle(rolist)
        random.shuffle(x_z)
        byzantine_robots = random.sample(range(self.robots_quantity), self.byzantine_quantity)
        objects = []
        USE_FLAT_TILE = True
        self.draw_tiles(blacktiles, objects, USE_FLAT_TILE)
        for i in range(self.robots_quantity):
            if i in byzantine_robots:
                controller = "smallrange_moving"
            else:
                controller = "data_sampling"
            self.import_robot(i, x_z[i][0], y_[i], x_z[i][1], rolist[i], rgblist[i], controller)
        rospy.loginfo(f'Environment initialized')

    def reset(self):
        rospy.loginfo("supervisor reset")
        self.supervisor.simulationReset()
        supervisor_node = self.supervisor.getFromDef("EnvSet")
        supervisor_node.restartController()

    def exit(self):
        rospy.loginfo("supervisor exit")
        self.supervisor.simulationQuit(0)

    def step(self):
        self.supervisor.step(self.time_step)

    def get_neighbors(self):
        pos_list = []
        neighbor = [[0] * self.robots_quantity for i in range(self.robots_quantity)]
        for i in range(self.robots_quantity):
            epuck = self.supervisor.getFromDef("epuck" + str(i))
            pos = epuck.getPosition()
            pos_list.append(pos[0:3])
            for j in range(i):
                dist = np.linalg.norm(pos_list[j], pos_list[i])
                if dist < self.communication_range:
                    neighbor[j][i] = 1
                    neighbor[i][j] = 1
        return neighbor

    def draw_tiles(self, black_list, object_list, use_flat):
        root = self.supervisor.getRoot()
        chFd = root.getField("children")
        # position = []
        if use_flat:
            tiles_list = ["""
                                            Solid {
                                                translation %f 0.001 %f
                                                children [
                                                    Shape {
                                                        appearance PBRAppearance {
                                                            baseColor 0 0 0
                                                            emissiveColor %f %f %f
                                                        }
                                                        geometry Box {
                                                            size 0.1 0.001 0.1
                                                        }
                                                    }
                                                ]
                                            }
                                            """ % (
                -1.05 + 0.1 * (i + 1), -1.05 + 0.1 * (j + 1), 0, 0, 0) if 20 * i + j in black_list else
                          """
                          Solid {
                              translation %f 0.001 %f
                              children [
                                  Shape {
                                      appearance PBRAppearance {
                                          baseColor 0 0 0
                                          emissiveColor %f %f %f
                                      }
                                      geometry Box {
                                          size 0.1 0.001 0.1
                                      }
                                  }
                              ]
                          }
                          """ % (-1.05 + 0.1 * (i + 1), -1.05 + 0.1 * (j + 1), 1, 1, 1) for i in range(20) for j in
                          range(20)]
        else:
            tiles_list = ["""
                                            Solid {
                                                translation %f 0.001 %f
                                                children [
                                                    Shape {
                                                        appearance PBRAppearance {
                                                            baseColor 0 0 0
                                                            emissiveColor %f %f %f
                                                        }
                                                        geometry Box {
                                                            size 0.1 0.001 0.1
                                                        }
                                                    }
                                                ]
                                            }
                                            """ % (
                -1.05 + 0.1 * (i + 1), -1.05 + 0.1 * (j + 1), 0, 1, 1) if 20 * i + j in black_list else
                          """
                          Solid {
                              translation %f 0.001 %f
                              children [
                                  Shape {
                                      appearance Appearance {

                                          texture ImageTexture {
                                              url "textures/parquetry/mines2.png"
                                          }

                                      }
                                      geometry Box {
                                          size 0.1 0.001 0.1
                                      }
                                  }
                              ]
                          }
                          """ % (-1.05 + 0.1 * (i + 1), -1.05 + 0.1 * (j + 1)) if 20 * i + j in object_list else
                          """
                          Solid {
                              translation %f 0.001 %f
                              children [
                                  Shape {
                                      appearance PBRAppearance {
                                          baseColor 0 0 0
                                          emissiveColor %f %f %f
                                      }
                                      geometry Box {
                                          size 0.1 0.001 0.1
                                      }
                                  }
                              ]
                          }
                          """ % (-1.05 + 0.1 * (i + 1), -1.05 + 0.1 * (j + 1), 1, 1, 1) for i in range(20) for j in
                          range(20)]
        children_str = ""
        for i in tiles_list:
            children_str = children_str + i
        line_String = """
                                DEF Floor_Tiles Solid{
                                    children [
                                        %s
                                    ]
                                }
                                """ % children_str
        chFd.importMFNodeFromString(-1, line_String)

    def import_robot(self, robot_id, x, y, z, rotation, rgb, controller):
        root = self.supervisor.getRoot()
        chFd = root.getField("children")
        # position = []
        if rgb == "none":
            line_String = """
                                        DEF epuck%d E-puck{
                                            translation %f %f %f
                                            rotation 0 1 0 %f
                                            name "e-puck%d"
                                            controller "%s"
                                            customData "%d"
                                            supervisor TRUE
                                            version "2"
                                            camera_fieldOfView 0.5
                                            camera_width 48
                                            camera_height 48
                                            camera_antiAliasing TRUE
                                            camera_rotation 1 0 0 -1.46
                                        }
                                        """ % (robot_id, x, y, z, rotation, robot_id, controller, robot_id)
        else:
            line_String = """
                                        DEF epuck%d E-puck2{
                                            translation %f %f %f
                                            rotation 0 1 0 %f
                                            name "e-puck%d"
                                            controller "%s"
                                            customData "%d"
                                            supervisor TRUE
                                            version "2"
                                            camera_fieldOfView 0.5
                                            camera_width 48
                                            camera_height 48
                                            camera_antiAliasing TRUE
                                            camera_rotation 1 0 0 -1.46
                                            emissiveColor %s %s %s
                                            emissiveColor2 %s %s %s
                                        }
                                        """ % (
                robot_id, x, y, z, rotation, robot_id, controller, robot_id, rgb[-1], rgb[-2], rgb[-3], rgb[-4],
                rgb[-5], rgb[-6])
        chFd.importMFNodeFromString(-1, line_String)

    def draw_line(self, pos1, pos2):
        root = self.supervisor.getRoot()
        chFd = root.getField("children")
        line_String = """
                                DEF Line Shape{
                                    appearance Appearance{
                                        material Material {
                                            diffuseColor 1 0 0
                                            emissiveColor 1 0 0
                                        }
                                    }
                                    geometry IndexedLineSet {
                                        coord Coordinate {
                                            point [ %f 0.054 %f, %f 0.054 %f ]
                                        }
                                        coordIndex [1 0]
                                    }
                                    isPickable FALSE
                                }
                                """ % (pos1[0], pos1[2], pos2[0], pos2[2])
        chFd.importMFNodeFromString(-1, line_String)

    def callback_cmd(self, cmd):
        data = cmd.data
        rospy.loginfo(f"supervisor received a command:{data}!")
        if data == "change":
            self.reset()
        elif data == "reset":
            self.reset()
        elif data == "exit":
            self.exit()

def run_loop():
    while env.step() != -1:
        rate.sleep()


if __name__ == "__main__":
    rospy.loginfo(f'supervisor started...')
    env = BlackWhiteGridEnv()
    rospy.loginfo(f'Success create env instance')
    rospy.init_node("supervisor")
    rospy.Subscriber('/cmd', String, env.callback_cmd)
    rate = rospy.Rate(10.0)
    run_loop()


