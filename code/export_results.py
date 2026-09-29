from pathlib import Path
import openpyxl
from openpyxl import Workbook

def _times():
    return [f"{h:02d}:{m:02d}-{(h+(m+10)//60):02d}:{(m+10)%60:02d}" for h in range(24) for m in range(0,60,10)]

def export_result(result, path, mode):
    """从已审计的原始轨迹生成独立工作簿；不覆盖输入模板。"""
    wb=Workbook(); ws=wb.active; ws.title='计划购电量'
    ws.append(['日期']+_times())
    for d in result.get('daily',[]): ws.append([d['date']]+d['trajectory']['B'])
    ws2=wb.create_sheet('充放电量'); ws2.append(['日期','区间','充电量(kWh)','放电量(kWh)','0:00储电量','24:00储电量'])
    for d in result.get('daily',[]):
        tr=d['trajectory']; c=tr['c']; r=tr['r']; E=tr['E']
        for j in range(6): ws2.append([d['date'],f'{j*4:02d}:00-{(j+1)*4:02d}:00',sum(c[j*24:(j+1)*24]),sum(r[j*24:(j+1)*24]),E[0] if j==0 else '',E[-1] if j==5 else ''])
    if mode in ('q2','q4_q2','q3','q4_q3'):
        ws3=wb.create_sheet('紧急购电量'); ws3.append(['日期','紧急购电时间段','紧急购电量(kWh)'])
        for d in result.get('daily',[]):
            e=d['trajectory']['e']; run=None
            for t,x in enumerate(e+[0]):
                if x>1e-8 and run is None: run=t
                if run is not None and x<=1e-8:
                    ws3.append([d['date'],_times()[run].split('-')[0]+'-'+_times()[t-1].split('-')[1],sum(e[run:t])]); run=None
    if mode in ('q3','q4_q3'):
        ws4=wb.create_sheet('调整购电量'); ws4.append(['日期','时段','原计划B','最终Q','上调量','下调量'])
        for d in result.get('daily',[]):
            tr=d['trajectory']
            for t,(b,q) in enumerate(zip(tr['B'],tr['Q'])):
                ws4.append([d['date'],_times()[t],b,q,max(q-b,0),max(b-q,0)])
    Path(path).parent.mkdir(parents=True,exist_ok=True); wb.save(path)

def export_q1(result, path):
    """Export the single-day Q1 workbook in the supplied two-sheet layout."""
    wb=Workbook(); ws=wb.active; ws.title='计划购电量'; ws.append(['时间段','购电量'])
    b=result['B']; c=result['c']; r=result['r']; E=result['E']
    for t,x in enumerate(b): ws.append([_times()[t],float(x)])
    ws2=wb.create_sheet('充放电量'); ws2.append(['时间段','充电量','放电量','0:00储电量','24:00储电量'])
    for j in range(6):
        ws2.append([f'{j*4:02d}:00-{(j+1)*4:02d}:00',float(sum(c[j*24:(j+1)*24])),float(sum(r[j*24:(j+1)*24])),float(E[0]) if j==0 else '',float(E[-1]) if j==5 else ''])
    Path(path).parent.mkdir(parents=True,exist_ok=True); wb.save(path)
