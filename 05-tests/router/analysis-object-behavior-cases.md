# Router Analysis Object / Behavior Cases

## Case 01
Input:
Batch Size变化是否影响Accuracy和Loss。

Expected:
Variable + Correlation -> Method 04-2

## Case 02
Input:
比较不同模型在TTFT、吞吐、成本上的表现。

Expected:
Object + Comparison -> Method 05

## Case 03
Input:
Yield异常结合趋势、Wafer Map、Defect定位原因。

Expected:
Object/State + Diagnosis -> Method 04-3；只有提供事件记录时才认定Event，不由Yield异常自动推断事实事件

## Case 04
Input: 有告警和恢复记录，需要回顾异常过程。
Expected: Event + Event Reconstruction -> Method 06；不能仅因Event走04。

## Case 05
Input: 按已有告警规则列出所有异常设备，没有空间约束。
Expected: State + Monitoring/异常筛选 -> Method 02并读取短卡及所需详解；不能仅因State走03。

以上均为待执行预期，非本次运行通过记录。
