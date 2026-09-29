import argparse
from .engine import run_all

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--mode",choices=("smoke","full"),default="smoke"); ap.add_argument("--start",default="2025-02-01"); ap.add_argument("--end",default=None); ap.add_argument("--out",default=None)
    a=ap.parse_args(); end=a.end or ("2025-02-03" if a.mode=="smoke" else "2025-12-31")
    path,out=run_all(a.mode,a.start,end,a.out); print("输出:",path); print({k:round(v.get("total_cost",v.get("cost",0)),4) if isinstance(v,dict) else None for k,v in out.items()})
if __name__=="__main__": main()
