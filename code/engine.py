import json, hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from .config import *
from .data_model import load_data
from .optimizer import solve_q1, solve_day_ahead, solve_adjustment, execute, billing, audit

def sig(x): return hashlib.sha256(json.dumps(x,sort_keys=True,default=str).encode()).hexdigest()

def forecast_day(data,i,kind):
    x,n=data.history(i,kind); return np.maximum(x,0.0), n

def pv_issue_forecast(data,i,slot):
    """Map the latest causally available 24 hourly forecasts onto this day.

    Attachment 3 columns are lead hours (issue + 1h ... issue + 24h), not
    clock hours.  Each ten-minute target therefore selects the latest issued
    row whose horizon covers it; uncovered points use the historical prior.
    """
    day0=pd.Timestamp(data.dates[i]); cutoff=day0+pd.Timedelta(minutes=10*slot)
    out,_=forecast_day(data,i,"pv"); used=0
    issues=np.asarray(data.forecast_issue)
    valid=np.array([pd_timestamp(x) is not None for x in issues])
    ordered=np.where(valid & (issues<=cutoff))[0]
    used=int(len(ordered))
    target=[day0+pd.Timedelta(minutes=10*(t+1)) for t in range(144)]
    for t in range(144):
        if not len(ordered): continue
        pos=len(ordered)-1
        while pos>=0 and (issues[ordered[pos]] > target[t] or issues[ordered[pos]]+pd.Timedelta(hours=24)<target[t]): pos-=1
        if pos<0: continue
        k=ordered[pos]; issue=issues[k]; vals=data.forecast[k]
        hours=(target[t]-issue).total_seconds()/3600.0
        out[t]=vals[0] if hours<=1 else np.interp(hours,np.arange(1,25),vals)
    return np.maximum(out,0.0),used

def pd_timestamp(x):
    try:
        ts=pd.Timestamp(x)
        return ts if pd.notna(ts) else None
    except (TypeError, ValueError):
        return None

def run(data, mode, start=0, end=None, save=True):
    end=len(data.dates) if end is None else min(end,len(data.dates)); soc=E0; rows=[]
    for i in range(end):
        day=data.dates[i]
        lh,_=forecast_day(data,i,"load"); vh,_=forecast_day(data,i,"pv")
        if mode in ("q3","q4_q3"): vh,_=pv_issue_forecast(data,i,0)
        # q4 planning uses only prices available from the historical causal prior;
        # settlement always uses the realised attachment-4 price.
        real_p=data.fixed_price if mode in ("q2","q3") else data.price[i]
        plan_p=real_p if mode in ("q2","q3") else forecast_day(data,i,"price")[0]
        if i == 0:
            # No completed day is available on 1 January.  Keep the transparent
            # cold-start plan; the first issued forecast must not rewrite it.
            B=np.zeros(144); Q=B.copy(); forecast_kind="cold_start"
        else:
            da=solve_day_ahead(lh,vh,plan_p,soc); B=da["B"].copy(); forecast_kind="causal"
        if mode not in ("q3","q4_q3") or i == 0:
            tr=execute(data.load[i],data.pv[i],real_p,B,soc)
            Q=B.copy()
        else:
            # Re-optimise only the not-yet-delivered suffix at the four permitted
            # information times, then execute each interval on realised data.
            segs=[]; E=soc; cuts=(0,36,72,108,144)
            for left,right in zip(cuts[:-1],cuts[1:]):
                vh2,_=pv_issue_forecast(data,i,left)
                adj=solve_adjustment(lh[left:],vh2[left:],plan_p[left:],E,B[left:],locked=0)
                qseg=adj["Q"]
                seg=execute(data.load[i][left:right],data.pv[i][left:right],real_p[left:right],B[left:right],E,qseg[:right-left])
                segs.append(seg); E=float(seg["E"][-1])
            Q=np.concatenate([s["Q"] for s in segs]);
            tr={k:np.concatenate([s[k] for s in segs]) for k in ("B","Q","G","c","r","e","W","L","V","p")}
            tr["E"]=np.concatenate([segs[0]["E"]]+[s["E"][1:] for s in segs[1:]]); tr["audit"] = audit(tr)
            tr["B"]=B; tr["Q"]=Q; tr["G"]=Q
        bill=billing(real_p,B,Q,tr["e"]); soc=float(tr["E"][-1])
        if i>=start:
            rows.append({"date":day,"cost":bill["C_actual"],"billing":bill,"soc_start":float(tr["E"][0]),"soc_end":soc,
              "trajectory":{k:np.asarray(tr[k]).tolist() for k in ("B","Q","G","c","r","e","W","E","L","V","p")},"audit":tr["audit"],"forecast_kind":forecast_kind})
    return {"problem_id":mode,"days":len(rows),"total_cost":float(sum(x["cost"] for x in rows)),"total_emergency_kwh":float(sum(sum(x["trajectory"]["e"]) for x in rows)),"daily":rows,"constraints_ok":all(x["audit"]["feasible"] for x in rows),"seed":SEED}

def run_all(mode="smoke", start_date="2025-02-01", end_date="2025-02-03", out_dir=None):
    data=load_data(); dates=data.dates; start=dates.index(start_date) if start_date in dates else 31; end=dates.index(end_date)+1 if end_date in dates else (start+3 if mode=="smoke" else len(dates))
    out=Path(out_dir or OUT)/sig({"mode":mode,"start":start_date,"end":end_date})[:12]; out.mkdir(parents=True,exist_ok=True)
    q1=solve_q1(data.fixed_load,data.fixed_pv,data.fixed_price); q1j={k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in q1.items()}; (out/"q1.json").write_text(json.dumps(q1j,ensure_ascii=False,indent=2),encoding="utf-8")
    allout={"q1":q1j}
    from .export_results import export_result, export_q1
    export_q1(q1,out/"result1.xlsx")
    for m in ("q2","q3","q4_q2","q4_q3"):
        x=run(data,m,start,end); (out/(m+".json")).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8"); allout[m]=x
        export_result(x,out/({"q2":"result2.xlsx","q3":"result3.xlsx","q4_q2":"result4-2.xlsx","q4_q3":"result4-3.xlsx"}[m]),m)
    (out/"results.json").write_text(json.dumps({"run_dir":str(out.relative_to(ROOT)),"problems":allout},ensure_ascii=False,indent=2),encoding="utf-8")
    return out,allout
