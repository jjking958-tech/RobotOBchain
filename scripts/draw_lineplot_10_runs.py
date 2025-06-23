import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
import os


def plot_result(result_path, label):
    warnings.filterwarnings('ignore')
    plt.style.use('ggplot')
    plt.rcParams['font.family'] = ['sans-serif']
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus']=False

    if label == "sim_time":
        outputFilename = "time"
        label_cn = '时间'
    else:
        outputFilename = label
        label_cn = '比例估计值'
    inputFiledir = result_path
    files = os.listdir(inputFiledir)
    files.sort()
    tbb=[[],[]]
    print(tbb)
    clm=[]
    for file in files:
        if os.path.splitext(file)[1] == '.csv':
            clm.append(int(os.path.splitext(file)[0]))
            data = pd.read_csv(inputFiledir+file)
            df = pd.DataFrame(data)
            group_obj = df.groupby(by='is_filtered')
            j = 0
            for group_key, group_val in group_obj:
                a=[]
                group_val = group_val.reset_index()
                for i in range(9, len(group_val[label]), 10):
                    a.append(i)

                tbb[j].append(group_val.loc[a, label])
                j += 1
    print(f'--------------------------------------')
    print(tbb)
    f0=pd.DataFrame(tbb[0])
    f0_T= pd.DataFrame(f0.T)
    f0_T.columns = clm
    f0_T.insert(0,"方法",["None"]*10)
    df0=f0_T

    f1=pd.DataFrame(tbb[1])
    f1_T= pd.DataFrame(f1.T)
    f1_T.columns = clm
    f1_T.insert(0,"方法",["Filtered"]*10)
    df1=f1_T
    df = pd.concat([df0,df1],axis=0)
    print(df)
    df_melt = pd.melt(df,id_vars='方法')
    # print(df_melt)
    df_melt.columns = ['方法', '拜占庭机器人个数', label_cn]
    print(df_melt)
    # a=df.stack().reset_index().set_axis(['实验序次','游骑兵机器人个数','退出时间 (秒)'],axis=1)
    # print(a)
    # ax=sns.boxplot(x='拜占庭机器人个数',y='比例估计值', hue='方法', data=df_melt)
    ax=sns.lineplot(x='拜占庭机器人个数',y=label_cn, hue='方法',style="方法",
        markers=True, dashes=False, data=df_melt, ci='sd')
    # ax.text(1, -0.12, '每组实验重复10次',
    #         horizontalalignment='right',
    #         verticalalignment='bottom',
    #         transform=ax.transAxes)
    plt.xticks([i for i in range(6)])
    if label == 'sim_time':
        plt.ylim(0, 250)
    else:
        plt.ylim(0, 1)
    plt.title('10次实验平均值')
    plt.savefig(inputFiledir+outputFilename+".pdf")

    # plt.show()

if __name__ == "__main__":
    result_path = "../data/20230909212553/"
    plot_result(result_path, label="mean")