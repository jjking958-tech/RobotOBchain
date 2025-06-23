import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
import os
warnings.filterwarnings('ignore')
plt.style.use('ggplot')
plt.rcParams['font.family'] = ['sans-serif']
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus']=False

a=[]
label = "sim_time"
if label == "sim_time":
    outputFilename = "time"
    label_cn = '时间'
else:
    outputFilename = label
    label_cn = '比例估计值'
inputFiledir = "../data/20230808170532/"
files = os.listdir(inputFiledir)
files.sort()
tbb=[]
clm=[]
for file in files:
    if os.path.splitext(file)[1] == '.csv':
        clm.append(os.path.splitext(file)[0])
        data = pd.read_csv(inputFiledir+file)
        df = pd.DataFrame(data)
        a=[]
        for i in range(9, len(df[label]), 10):
            a.append(i)
        tbb.append(df.loc[a,label])
f=pd.DataFrame(tbb)

f_T= pd.DataFrame(f.T)
print(f_T)
f_T.columns = clm
# print(clm)

f_T.insert(0,"方法",["有方法"]*10)
df=f_T
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
plt.xticks([i for i in range(6)])
if label == 'sim_time':
    plt.ylim(0, 250)
else:
    plt.ylim(0, 1)
plt.suptitle('拜占庭类型 0')
plt.savefig(inputFiledir+outputFilename+".pdf")

plt.show()

# import pandas as pd
# import numpy as np
#
# df = pd.DataFrame(np.arange(16).reshape(4, 4),
#                   columns=[2016, 2017, 2018, 2019],
#                   index=[*'ABCD'])
#
# print(df)
# a=(
#     df.stack()
#     .reset_index()
#     .set_axis(['个体', '时间', '变量x'], axis=1)
# )
# print(a)