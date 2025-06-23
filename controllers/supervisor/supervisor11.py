# coding=UTF-8
import sys
import os
sys.path.append('/usr/local/webots/lib/controller/python39')
sys.path.append('/opt/ros/melodic/lib/python2.7/dist-packages')
sys.path.append(os.path.dirname(os.path.realpath(__file__)))
from controller import Supervisor
from torch.utils.tensorboard import SummaryWriter
import math,random
import socket
import os
import time
import threading
import logging
import traceback
import hashlib



# create the Robot instance.
def init():
    USE_FLAT_TILE = True
    black_ratio_real = 0.40
    blacktiles = random.sample(range(400),int(400*black_ratio_real)) 
    if USE_FLAT_TILE:
        x_z = [(-1.05+0.1*(i+1),-1.05+0.1*(j+1)) for i in range(20) for j in range(20)]
    else:
        x_z = [(-1.05+0.1*(i+1),-1.05+0.1*(j+1)) for i in range(20) for j in range(20) if i*20+j not in blacktiles]
    y_=[0 for i in range(N)]    
    rolist = [i / 100.0 for i in range(0,628,int(628/N))]
    rgblist = []
    rgblist = ['{:08b}'.format(i+1) if i in ranger_robots else "none" for i in swarm]
    
    random.shuffle(rolist)
    random.shuffle(x_z)

    objects=[]
    drawtiles(blacktiles, objects, USE_FLAT_TILE)
    for i in range(N):
        j = swarm.index(i)
        print("import robot %2d " % j)
        if i in byzantine_robots:
            ctrl = "smallrange_moving"
        else:
            ctrl = "data_sampling"
        importRobot(i,x_z[j][0],y_[j],x_z[j][1],rolist[j],rgblist[j],ctrl) # import Robot


            
def resetAll():
    print("all reset")
    robot.simulationReset()
    supervisornode = robot.getFromDef("EnvSet")
    supervisornode.restartController()

def writeTime():
    ctime=robot.getTime()
    print("reset at %f"% ctime)
    with open("../../data/all_robot/all_estimate.csv",'a') as fp:
        fp.write(str(ctime))
        fp.write("\n")
    
def exitAll():
    print("all exit")
    # robot.simulationReset()
    robot.simulationQuit(0)
    
    
def archive():  
    print("archiving...")
    with open("../../data/all_robot/all_estimate.csv",'rb') as fp:
        data = fp.read()
    file_md5 = hashlib.md5(data).hexdigest()
    print("......")
    try:        
        t=time.strftime("%Y%m%d%H%M%S",time.localtime())
        os.system("mv ../../data/all_robot/all_estimate.csv ../../data/all_robot/all_estimate_byz"+str(byzantine_number)+"_t_"+t+"_md5_"+str(file_md5)+".csv")
    except Exception as e:
        print("exception:" + e)
    print(".........")

def archiveAll():
    print("archiving...")
    try:        
        t=time.strftime("%Y%m%d%H%M%S",time.localtime())
        dir = "../../data/all_robot/%s"%t
        os.system("mkdir %s"%dir)
        os.system("mv ../../data/all_robot/all_estimate* %s"%dir)
    except Exception as e:
        print("exception:" + e)
    print(".........")

    
def removeline():
    root = robot.getRoot()
    chFd = root.getField("children")

    while 1:
        count = chFd.getCount()

        if count > 29:
            chFd.removeMF(count-1)
        else:
            break


def getNeighbors():
    pos_list = []
    neighbor=[[0]*N for i in range(N)]
    for i in range(N):
        epuck=robot.getFromDef("epuck"+str(i))
        pos=epuck.getPosition()
        pos_list.append(pos[0:3]) 
        for j in range(i):
            dist=getDistance(pos_list[j],pos_list[i])
            if dist < max(commRange[i],commRange[j]):
                neighbor[j][i]=1
                neighbor[i][j]=1              
    for r in range(N):
        for j in range(N):
            if neighbor[r][j] == 1:
                drawline(pos_list[r],pos_list[j])


def getDistance(pos1,pos2):
    dist=math.sqrt((pos1[0]-pos2[0])**2+(pos1[2]-pos2[2])**2)
    return dist


def drawline(pos1,pos2):
    root = robot.getRoot()
    chFd = root.getField("children")
    #position = []
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
    chFd.importMFNodeFromString(-1,line_String)
        
def importRobot(id,x,y,z,ro,rgb,ctrl):
    root = robot.getRoot()
    chFd = root.getField("children")
    #position = []
    if rgb == "none":
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
                                }
                                """% (id,x,y,z,ro,id,ctrl,id)
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
                                """% (id,x,y,z,ro,id,ctrl,id,rgb[-1],rgb[-2],rgb[-3],rgb[-4],rgb[-5],rgb[-6])
    chFd.importMFNodeFromString(-1,line_String)

def drawtiles(black_list, object_list, use_flat):
    root = robot.getRoot()
    chFd = root.getField("children")
    #position = []
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
                                        """ % (-1.05+0.1*(i+1),-1.05+0.1*(j+1),0,0,0) if 20*i+j in black_list else 
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
                                        """ % (-1.05+0.1*(i+1),-1.05+0.1*(j+1),1,1,1) for i in range(20) for j in range(20)]
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
                                        """ % (-1.05+0.1*(i+1),-1.05+0.1*(j+1),0,1,1) if 20*i+j in black_list else 
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
                                        """ % (-1.05+0.1*(i+1),-1.05+0.1*(j+1)) if 20*i+j in object_list else
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
                                        """ % (-1.05+0.1*(i+1),-1.05+0.1*(j+1),1,1,1) for i in range(20) for j in range(20)]
    children_str=""
    for i in tiles_list:
        children_str = children_str + i
    line_String = """
                            DEF Floor_Tiles Solid{
                                children [
                                    %s
                                ]
                            }
                            """ % children_str
    chFd.importMFNodeFromString(-1,line_String)

def plot_save(id,ctime,self_estimate,common_estimate):
    summary_writer[id].add_scalar("self_estimate", self_estimate,ctime)
    summary_writer[id].add_scalar("common_estimate", common_estimate,ctime)
    f = open("../../data/robot%d/estimate_result.csv" % id, "a")
    f.write("%d,%f,%f,%f"%(id, ctime, self_estimate, common_estimate))
    f.write("\n")
    f.close()    

def run(n):
    global resetFlag
    global exitFlag
    global changeFlag
    while True:

        try:
            #连接服务端
            IP="localhost"
            PORT=8888
            s = socket.socket()
            s.connect((IP,PORT)) # 建立连接

            print("waiting for server commond...")
            resstr = s.recv(1024).decode()
            print("server commond: %s" % resstr)
            commond = resstr
            if commond=="reset":
                writeTime()
                msg='ready'
                msg=msg.encode()
                s.send(msg) # 向服务端发送“ready"信号
                s.close()
                resetFlag = True
                break
            elif commond=="change":
                writeTime()
                msg='ready2change'
                msg=msg.encode()
                s.send(msg)
                s.close()
                changeFlag=True
                break
            elif commond=="exit":
                writeTime()
                msg='ok'
                msg=msg.encode()
                s.send(msg) 
                s.close()
                exitFlag = True
                break
                
        except Exception as e:
            pass


if __name__=="__main__":
    robot = Supervisor()
    timestep = 640
    N = 10
    with open('../../scripts/Byzantine_counter.txt','r',encoding='utf-8') as f:
        file = f.read()
        byzantine_number = eval(file)
    group_number = 1
    groups = {0:[],1:[],2:[],3:[]}
    swarm =[]
    byzantine_robots=random.sample(range(N),byzantine_number)
    for i in range(N):
        groups[i % group_number].append(i)
    print(groups)    
    for g in groups.keys():
        swarm.extend(groups[g])
    print(swarm)    
           
    X = 0
    ranger_robots=list(range(N)[:X])
    print(ranger_robots)
    commRange =[1 if _ in ranger_robots else 0.5 for _ in swarm] 
    
    resetFlag = False
    changeFlag = False
    exitFlag = False

    init()
    
    t1 = threading.Thread(target=run, args=("thread 1",), daemon=True)
    t1.start()
    
    while robot.step(timestep) != -1:
        if resetFlag or changeFlag or exitFlag:
            break
            
    if resetFlag:
        resetAll()
    if changeFlag:
        resetAll()
    if exitFlag:
        exitAll()
