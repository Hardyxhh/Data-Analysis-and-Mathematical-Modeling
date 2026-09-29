"""确定性、有界的六小时经验情景树。用于记录因果情景输入，最多16叶。"""
import numpy as np

def build_tree(load_hist, pv_hist, price_hist, max_leaves=16, block=36):
    load_hist=np.asarray(load_hist,float); pv_hist=np.asarray(pv_hist,float); price_hist=np.asarray(price_hist,float)
    n=len(load_hist)
    if n==0: return [{"probability":1.0,"load":None,"pv":None,"price":None,"sample_ids":[]}]
    # 以历史日的联合平均净负载排序递归二分；不复制样本，概率按样本比例。
    nodes=[np.arange(n)]; leaves=[]
    while nodes:
        ids=nodes.pop(0)
        if len(ids)<2 or len(leaves)+len(nodes)+2>max_leaves:
            leaves.append(ids); continue
        score=np.mean(load_hist[ids]-pv_hist[ids],axis=1); order=ids[np.argsort(score,kind='mergesort')]; k=len(order)//2
        nodes.extend([order[:k],order[k:]])
    out=[]
    for ids in leaves:
        out.append({"probability":float(len(ids)/n),"load":np.mean(load_hist[ids],axis=0).tolist(),"pv":np.mean(pv_hist[ids],axis=0).tolist(),"price":np.mean(price_hist[ids],axis=0).tolist(),"sample_ids":ids.tolist()})
    s=sum(x["probability"] for x in out)
    for x in out: x["probability"]/=s
    return out
