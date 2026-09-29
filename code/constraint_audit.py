import argparse, json
from pathlib import Path
from .optimizer import audit, billing

def check_file(path):
    x=json.loads(Path(path).read_text(encoding="utf-8")); failures=[]
    if "daily" in x:
        if not x["daily"]: failures.append("daily为空")
        for row in x["daily"]:
            if not row.get("audit",{}).get("feasible",False): failures.append(row.get("date","unknown"))
            b=row.get("billing",{}); t=row.get("trajectory",{})
            if not t: failures.append("缺少trajectory")
            else:
                rb=billing(t["p"],t["B"],t["Q"],t["e"])
                if abs(float(b.get("C_actual",float("nan")))-rb["C_actual"])>1e-5: failures.append("账本")
        if not x.get("constraints_ok",False): failures.append("constraints_ok=false")
    elif not x.get("audit",{}).get("feasible",False): failures.append("q1")
    if failures: raise ValueError(f"{path}: {failures}")
    return True

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("run_dir"); a=ap.parse_args(); files=sorted(Path(a.run_dir).glob("*.json")); files=[p for p in files if p.name not in ("results.json",)]
    if not files: raise FileNotFoundError("没有结果文件")
    for p in files: check_file(p)
    print("constraint audit PASS",len(files))
if __name__=="__main__": main()
