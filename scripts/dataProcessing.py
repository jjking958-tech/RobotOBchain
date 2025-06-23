import pandas as pd
import os
a=[]
filepath = "../data/all_robot/20230224111335/"
files = os.listdir(filepath)
files.sort()
j = 0
tbb=[]
clm=[]
for file in files:
    if os.path.splitext(file)[1] == '.csv':
        print(file)
        clm.append(os.path.splitext(file)[0])

        data = pd.read_csv(filepath+file)
        df = pd.DataFrame(data)
        print(df[' mean'])
        a=[]
        for i in range(19, len(df[' mean']), 21):
            a.append(i)
        tbb.append(df.iloc[a,3])
f=pd.DataFrame(tbb)
f_T= pd.DataFrame(f.T)
f_T.columns = clm

f_T.insert(0,"方法",["无方法"]*10)
print(f_T)

