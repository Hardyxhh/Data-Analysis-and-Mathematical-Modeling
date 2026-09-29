from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd
from .config import ROOT

def _read(name, sheet=0):
    p = ROOT / name
    if not p.exists(): raise FileNotFoundError(p)
    x = pd.read_excel(p, sheet_name=sheet, header=0)
    return x.dropna(how="all").dropna(axis=1, how="all")

@dataclass
class Data:
    fixed_price: np.ndarray
    fixed_load: np.ndarray
    fixed_pv: np.ndarray
    dates: list
    load: np.ndarray
    pv: np.ndarray
    price: np.ndarray
    forecast_issue: pd.DatetimeIndex
    forecast: np.ndarray

    def history(self, i, kind, window=28):
        j0=max(0, i-window); ids=np.arange(j0, i)
        if len(ids)==0:
            if kind == "load":
                return self.fixed_load.copy(), 0
            if kind == "pv":
                return self.fixed_pv.copy(), 0
            if kind == "price":
                return self.price[0].copy(), 0
            raise ValueError(f"unknown history kind: {kind}")
        w=2.0**(-(i-ids)/7.0); w=w/w.sum()
        if kind == "load":
            a=self.load
        elif kind == "pv":
            a=self.pv
        elif kind == "price":
            a=self.price
        else:
            raise ValueError(f"unknown history kind: {kind}")
        return np.average(a[ids], axis=0, weights=w), len(ids)

    def available_forecast(self, timestamp):
        m=self.forecast_issue.notna() & (self.forecast_issue <= pd.Timestamp(timestamp))
        if not m.any(): return None
        return self.forecast[np.where(m)[0][-1]]

def load_data():
    a=_read("附件1.xlsx"); fp=pd.to_numeric(a.iloc[:,1], errors="raise").to_numpy(float)
    fl=pd.to_numeric(a.iloc[:,2], errors="raise").to_numpy(float); fv=pd.to_numeric(a.iloc[:,3], errors="raise").to_numpy(float)
    l=_read("附件2.xlsx",0); v=_read("附件2.xlsx",1)
    dates=pd.to_datetime(l.iloc[:,0], errors="raise").dt.strftime("%Y-%m-%d").tolist()
    load=l.iloc[:,1:].apply(pd.to_numeric, errors="raise").to_numpy(float)
    pv=v.iloc[:,1:].apply(pd.to_numeric, errors="raise").to_numpy(float)
    price=_read("附件4.xlsx").iloc[:,1:].apply(pd.to_numeric, errors="raise").to_numpy(float)
    f=_read("附件3.xlsx")
    # 附件3日期只在每天第一行出现；日期向下填充，预报数值不能前填。
    fd=pd.to_datetime(f.iloc[:,0], errors="coerce").ffill()
    ft=f.iloc[:,1].astype(str).str.extract(r'(\d{1,2}):?(\d{2})?')
    fh=pd.to_numeric(ft[0],errors='coerce').fillna(0); fm=pd.to_numeric(ft[1],errors='coerce').fillna(0)
    issue=pd.to_datetime(fd.dt.strftime('%Y-%m-%d')+' '+fh.astype(int).astype(str)+':'+fm.astype(int).astype(str), errors='coerce')
    forecast=f.iloc[:,2:].apply(pd.to_numeric, errors="raise").to_numpy(float)
    if len(fp)!=144 or load.shape[1]!=144 or pv.shape!=load.shape or price.shape!=load.shape or forecast.shape[1]!=24:
        raise ValueError("附件维度不符合 144 段/日或附件3的24点预报结构")
    for x in (fp,fl,fv,load,pv,price,forecast):
        if not np.isfinite(x).all(): raise ValueError("输入含 NaN 或无穷值")
    return Data(fp,fl,fv,dates,load,pv,price,issue,forecast)
