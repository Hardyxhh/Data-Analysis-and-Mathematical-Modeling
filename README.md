# 运行说明

请在本目录的上一级项目根目录运行，避免把附件路径写成绝对路径。建议使用已安装 requirements.txt 的 Python：

```text
python -m pip install -r code/requirements.txt
python -m code.main --mode smoke --start 2025-02-01 --end 2025-02-03
python -m code.constraint_audit outputs/<运行目录>
python -m code.main --mode full --start 2025-02-01 --end 2025-12-31
```

当前实现使用相对输入路径 `附件1.xlsx`～`附件4.xlsx`，结果写入相对目录 `outputs/`。smoke 默认只处理 2 月前三天；full 才处理全年。所有运行使用固定种子 2026。

主流程包括：问题1确定性储能线性规划、问题2因果历史预测和日前计划、问题3预报批次下的合法未来购电调整、问题4固定/波动价格分支、逐段真实执行、独立物理/账本审计，并在结果目录生成 q1/q2/q3/q4 JSON 和 result1～result4-3 工作簿。执行动作和中间求解摘要不保存完整求解对象。

若使用 Codex 自带 Python，可执行：

```text
& "C:\Users\hp\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m code.main --mode smoke --start 2025-02-01 --end 2025-02-03
```

当前环境若没有 NumPy、pandas、SciPy 或 openpyxl，先按 requirements.txt 安装；缺少依赖时程序应失败并报告，不能切换到未声明的贪心结果冒充优化结果。
