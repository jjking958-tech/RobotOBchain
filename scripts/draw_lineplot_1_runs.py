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
inputFiledir = "../data/20230809122340/"
files = os.listdir(inputFiledir)
files.sort()
tbb=[]
clm=[]
for file in files:
    if os.path.splitext(file)[1] == '.csv':
        # print(file)
        clm.append(os.path.splitext(file)[0])
        data = pd.read_csv(inputFiledir+file)
        df = pd.DataFrame(data)
        a=[]
        for i in range(9, len(df[label]), 10):
            a.append(i)
        tbb.append(df.loc[a,label])
# print(tbb[0])
f=pd.DataFrame(tbb[0])
print(f'f：{f}')
df_melt = pd.melt(f,id_vars='is_filtered')
print(df_melt)
df_melt.columns = ['is_filtered', '拜占庭机器人个数', label_cn]
# print(df_melt)
# a=df.stack().reset_index().set_axis(['实验序次','游骑兵机器人个数','退出时间 (秒)'],axis=1)
# print(a)
# ax=sns.boxplot(x='拜占庭机器人个数',y='比例估计值', hue='方法', data=df_melt)
ax=sns.lineplot(x='拜占庭机器人个数',y=label_cn, hue='is_filtered',style="is_filtered",
    markers=True, dashes=False, data=df_melt, ci='sd')
plt.xticks([i for i in range(6)])
if label == 'sim_time':
    plt.ylim(0, 250)
else:
    plt.ylim(0, 1)
plt.suptitle('拜占庭类型 0')
plt.savefig(inputFiledir+outputFilename+".pdf")

plt.show()

