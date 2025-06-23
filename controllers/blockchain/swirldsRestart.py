import json
import os
import pathlib
import time
import traceback

import rospy
from controllers.blockchain.sendMail import sendMail
from scripts.draw_lineplot_10_runs import plot_result
from std_msgs.msg import String


def archive():
    rospy.loginfo("archiving result...")
    try:
        old_path = f'../../data/all_estimate.csv'
        if not os.path.exists(os.path.dirname(old_path)):
            os.makedirs(os.path.dirname(old_path))
        if os.path.exists(old_path):
            if byzantine_number - 1 < 10:
                new_path = f'../../data/0{byzantine_number-1}.csv'
            else:
                new_path = f'../../data/{byzantine_number-1}.csv'
            os.system(f'mv {old_path} {new_path}')
        # subprocess.run(['move', old_path, new_path], shell=True)
    except Exception as e:
        traceback.print_exc(e)
    rospy.loginfo("result archived.")


def archive_all():
    rospy.loginfo("archiving result...")
    try:
        t = time.strftime("%Y%m%d%H%M%S", time.localtime())
        directory = f"../../data/{t}/"
        if not os.path.exists(directory):
            os.makedirs(directory)
        old_path = f'../../data/*.csv'
        new_path = directory
        os.system(f'mv {old_path} {new_path}')

        old_path2 = f'../../data/byz*'
        os.system(f'mv {old_path2} {new_path}')
        # subprocess.run(['move', old_path, new_path], shell=True)
    except Exception as e:
        traceback.print_exc(e)
    rospy.loginfo("all results archived.")
    plot_figure(directory)

def plot_figure(result_path):
    rospy.loginfo("plot result figure")
    plot_result(result_path, label="mean")
    plot_result(result_path, label="sim_time")


if __name__ == '__main__':
    config_path = pathlib.Path(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))) / "config" / "config.json"
    with open(str(config_path), encoding='utf-8') as f:
        config = json.load(f)
    robots_quantity = config["robots_quantity"]
    byzantine_number = config["byzantine_quantity"]
    experiment_serial = config["serial_number"]
    repetitions = config["repetitions"]
    max_byzantine_number = config["max_byzantine_quantity"]

    rospy.init_node("swirld_auxiliary_node")
    rospy.loginfo("swirld process started...")
    pub = rospy.Publisher('/cmd', String, queue_size=1)
    rate = rospy.Rate(10)

    # 通过while循环实现自动重启下一次实验
    while True:
        if experiment_serial == 1:
            # 创建文件all_extimate.csv,记录实验结果
            file_path = f"../../data/all_estimate.csv"
            if not os.path.exists(os.path.dirname(file_path)):
                os.makedirs(os.path.dirname(file_path))
            if not os.path.exists(file_path):
                with open(file_path, "a") as f:
                    f.write("is_filtered,serial,robot_id,consensus,mean,se,real_time,hg_size,hg_height,sim_time")
                    f.write("\n")

        start_time = time.time()  # 开始时间

        # 调用test，启动Hashgraph区块链进程
        print("starting swirld")
        os.system("ps auxww | grep 'swirld_black_white_ratio_estimate.py' | awk '{print $2}' | xargs kill -9")
        os.system("python3 swirld_black_white_ratio_estimate.py")  # block here
        print("#######################################")

        time.sleep(10)

        # 在每次实验结束时向客户端（机器人supervisor控制器）发送重启命令
        try:
            if experiment_serial >= repetitions:
                byzantine_number += 1
                experiment_serial = 1
                config["byzantine_quantity"] = byzantine_number
                config["serial_number"] = experiment_serial
                with open(str(config_path), 'w', encoding='utf-8') as f:
                    json.dump(config, f, sort_keys=True, indent=4, separators=(',', ': '))
                cmd_str = "change"
                archive()
            else:
                experiment_serial += 1
                config["serial_number"] = experiment_serial
                with open(str(config_path), 'w', encoding='utf-8') as f:
                    json.dump(config, f, sort_keys=True, indent=4, separators=(',', ': '))
                cmd_str = "reset"
            if byzantine_number > max_byzantine_number:
                byzantine_number = 0
                experiment_serial = 1
                config["byzantine_quantity"] = byzantine_number
                config["serial_number"] = experiment_serial
                with open(str(config_path), 'w', encoding='utf-8') as f:
                    json.dump(config, f, sort_keys=True, indent=4, separators=(',', ': '))
                cmd_str = "exit"
                archive()
                archive_all()
            pub.publish(cmd_str)
        except Exception as e:
            traceback.print_exc()

        end_time = time.time()
        timediff = end_time - start_time
        rospy.loginfo("time difference %f" % timediff)
        if cmd_str == 'exit':
            break

    msg = "All experiment are done ^_^ "
    rospy.loginfo(msg)
    sendMail(msg)

