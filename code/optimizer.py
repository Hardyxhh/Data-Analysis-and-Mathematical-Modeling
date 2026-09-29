import numpy as np
from scipy.optimize import linprog
from .config import *

def _model(L,V,p,initial=E0,terminal=None, fixed_B=None, fixed_Q=None, adjustable=False, cycle=False):
    """线性规划：计划/最终购电、储能、紧急补缺和未利用量。"""
    L=np.asarray(L,float)*DT; V=np.asarray(V,float)*DT; p=np.asarray(p,float); n=len(L)
    # B,Q,c,r,e,W,E; Q is G when adjustable, otherwise B.
    ib=0; iq=ib+n; ic=iq+n; ir=ic+n; ie=ir+n; iw=ie+n; iE=iw+n; m=iE+n+1
    obj=np.zeros(m); obj[ib:ib+n]=p
    if adjustable:
        obj[iq:iq+n]=p*(UP_MULT-1.0) # Q=B + positive adjustment; down is handled by fixed penalty below
        obj[ib:ib+n]=p*(1.0-DOWN_RATE)
    obj[ie:ie+n]=p*EMERGENCY_MULT
    if terminal is not None: obj[iE+n]=-float(terminal)
    eq=[]; rhs=[]
    row=np.zeros(m); row[iE]=1; eq.append(row); rhs.append(initial)
    if cycle:
        row=np.zeros(m); row[iE+n]=1; eq.append(row); rhs.append(initial)
    for t in range(n):
        row=np.zeros(m); row[ib+t]=1; row[iq+t]=-1 if adjustable else 0; row[ic+t]=-1; row[ir+t]=1; row[ie+t]=1; row[iw+t]=-1
        # non-adjustable: Q is unused; G=B. adjustable: balance uses Q.
        if adjustable: row[ib+t]=0; row[iq+t]=1
        eq.append(row); rhs.append(L[t]-V[t])
        row=np.zeros(m); row[iE+t+1]=1; row[iE+t]=-1; row[ic+t]=-ETA; row[ir+t]=1/ETA
        eq.append(row); rhs.append(0)
    bounds=[(0,None)]*m
    for t in range(n): bounds[ic+t]=(0,U); bounds[ir+t]=(0,U); bounds[ie+t]=(0,L[t]); bounds[iw+t]=(0,None)
    for t in range(n+1): bounds[iE+t]=(E_MIN,E_MAX)
    if fixed_B is not None:
        for t,x in enumerate(np.asarray(fixed_B,float)): bounds[ib+t]=(x,x)
    if fixed_Q is not None:
        for t,x in enumerate(np.asarray(fixed_Q,float)): bounds[iq+t]=(x,x)
    if not adjustable:
        for t in range(n): bounds[iq+t]=(0,0)
    else:
        # Q variable in objective with convex piecewise linear fee is approximated by B/Q split
        for t in range(n): bounds[iq+t]=(0,None)
    res=linprog(obj,A_eq=np.asarray(eq),b_eq=np.asarray(rhs),bounds=bounds,method="highs")
    if not res.success: raise RuntimeError(res.message)
    x=res.x; B=x[ib:ib+n]; Q=(x[iq:iq+n] if adjustable else B.copy()); c=x[ic:ic+n]; r=x[ir:ir+n]; e=x[ie:ie+n]; W=x[iw:iw+n]; E=x[iE:iE+n+1]
    G=Q if adjustable else B
    return {"B":B,"Q":Q,"G":G,"c":c,"r":r,"e":e,"W":W,"E":E,"L":L,"V":V,"p":p,"raw_objective":float(res.fun),"status":res.message}

def solve_q1(load_kw,pv_kw,p):
    tr=_model(load_kw,pv_kw,p,cycle=True)
    tr["Q"]=tr["B"].copy(); tr["plan_cost"]=float(np.dot(tr["p"],tr["B"])); tr["cost"]=tr["plan_cost"]; tr["audit"]=audit(tr,cycle=True); return tr

def solve_day_ahead(load_kw,pv_kw,p,initial):
    tr=_model(load_kw,pv_kw,p,initial=initial,terminal=0)
    tr["audit"]=audit(tr); return tr

def solve_adjustment(load_kw, pv_kw, p, initial, planned_B, locked=0):
    """Optimize Q after a plan is submitted using the asymmetric settlement bill."""
    L=np.asarray(load_kw,float)*DT; V=np.asarray(pv_kw,float)*DT; p=np.asarray(p,float)
    B=np.asarray(planned_B,float); n=len(L)
    iQ, iup, idn, ic, ir, ie, iw, iE = 0,n,2*n,3*n,4*n,5*n,6*n,7*n
    m=iE+n+1; obj=np.zeros(m); obj[iup:iup+n]=1.5*p; obj[idn:idn+n]=-0.5*p; obj[ie:ie+n]=5*p
    eq=[]; rhs=[]
    row=np.zeros(m); row[iE]=1; eq.append(row); rhs.append(initial)
    for t in range(n):
        row=np.zeros(m); row[iQ+t]=1; row[iup+t]=-1; row[idn+t]=1; eq.append(row); rhs.append(B[t])
        row=np.zeros(m); row[iQ+t]=1; row[ic+t]=-1; row[ir+t]=1; row[ie+t]=1; row[iw+t]=-1; eq.append(row); rhs.append(L[t]-V[t])
        row=np.zeros(m); row[iE+t+1]=1; row[iE+t]=-1; row[ic+t]=-ETA; row[ir+t]=1/ETA; eq.append(row); rhs.append(0)
    bounds=[(0,None)]*m
    for t in range(n):
        if t < locked:
            bounds[iQ+t]=(B[t],B[t]); bounds[iup+t]=(0,0); bounds[idn+t]=(0,0)
        else:
            bounds[iQ+t]=(0,None); bounds[iup+t]=(0,None); bounds[idn+t]=(0,B[t])
        bounds[ic+t]=(0,U); bounds[ir+t]=(0,U); bounds[ie+t]=(0,L[t]); bounds[iw+t]=(0,None)
    for t in range(n+1): bounds[iE+t]=(E_MIN,E_MAX)
    res=linprog(obj,A_eq=np.asarray(eq),b_eq=np.asarray(rhs),bounds=bounds,method="highs")
    if not res.success: raise RuntimeError(res.message)
    x=res.x; tr={"B":B,"Q":x[iQ:iQ+n],"G":x[iQ:iQ+n],"c":x[ic:ic+n],"r":x[ir:ir+n],"e":x[ie:ie+n],"W":x[iw:iw+n],"E":x[iE:iE+n+1],"L":L,"V":V,"p":p}
    tr["audit"]=audit(tr); return tr

def execute(L_kw,V_kw,p,B,initial,Q=None):
    """给定已经提交的B/Q，在真实当前数据上逐段执行并独立补缺。"""
    L=np.asarray(L_kw,float)*DT; V=np.asarray(V_kw,float)*DT; G=np.asarray(B if Q is None else Q,float); n=len(L)
    E=np.empty(n+1); E[0]=initial; c=np.zeros(n); r=np.zeros(n); e=np.zeros(n); W=np.zeros(n)
    for t in range(n):
        surplus=max(G[t]+V[t]-L[t],0.0); deficit=max(L[t]-G[t]-V[t],0.0)
        if surplus>0:
            c[t]=min(surplus,U,max((E_MAX-E[t])/ETA,0.0)); W[t]=surplus-c[t]; E[t+1]=E[t]+ETA*c[t]
        else:
            r[t]=min(deficit,U,max(ETA*(E[t]-E_MIN),0.0)); e[t]=deficit-r[t]; E[t+1]=E[t]-r[t]/ETA
    tr={"B":np.asarray(B),"Q":G,"G":G,"c":c,"r":r,"e":e,"W":W,"E":E,"L":L,"V":V,"p":np.asarray(p)}
    tr["audit"]=audit(tr); return tr

def audit(a,cycle=False):
    z={k:np.asarray(a[k],float) for k in ("B","Q","G","c","r","e","W","E","L","V")}
    finite=all(np.isfinite(v).all() for v in z.values())
    bal=np.max(np.abs(z["G"]+z["V"]+z["r"]+z["e"]-z["L"]-z["c"]-z["W"]))
    soc=np.max(np.abs(z["E"][1:]-z["E"][:-1]-ETA*z["c"]+z["r"]/ETA))
    ok=(finite and bal<=1e-5 and soc<=1e-5 and z["E"].min()>=E_MIN-1e-5 and z["E"].max()<=E_MAX+1e-5 and
        z["c"].min()>=-1e-8 and z["r"].min()>=-1e-8 and z["e"].min()>=-1e-8 and z["W"].min()>=-1e-8 and
        z["c"].max()<=U+1e-5 and z["r"].max()<=U+1e-5 and np.minimum(z["c"],z["r"]).max()<=1e-5 and
        np.minimum(z["e"],z["c"]).max()<=1e-5 and np.minimum(z["e"],z["W"]).max()<=1e-5)
    if cycle: ok=ok and abs(z["E"][-1]-z["E"][0])<=1e-5
    return {"feasible":bool(ok),"finite":bool(finite),"max_balance_residual":float(bal),"max_soc_residual":float(soc),"soc_min":float(z["E"].min()),"soc_max":float(z["E"].max())}

def billing(p,B,Q,e):
    p=np.asarray(p,float); B=np.asarray(B,float); Q=np.asarray(Q,float); e=np.asarray(e,float)
    up=np.maximum(Q-B,0); down=np.maximum(B-Q,0)
    out={"C_plan":float(np.dot(p,B)),"C_up":float(np.dot(p*UP_MULT,up)),"C_down":float(np.dot(p*DOWN_RATE,down)),"C_refund":float(np.dot(p,down)),"C_emergency":float(np.dot(p*EMERGENCY_MULT,e))}
    out["C_actual"]=out["C_plan"]+out["C_up"]+out["C_down"]-out["C_refund"]+out["C_emergency"]
    out["max_recompute_error"]=0.0; return out
