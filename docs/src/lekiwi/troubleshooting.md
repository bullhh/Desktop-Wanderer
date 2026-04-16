# LeKiwi 故障排除

## Q1: 提示 "Device not connected" 或找不到设备

**可能原因**：
1. USB 线连接不良
2. 串口端口号错误
3. 串口权限不足
4. 串口被其他程序占用

**解决方案**：

```bash
# 1. 检查 USB 连接
ls -l /dev/ttyACM*

# 2. 重新检测端口
lerobot-find-port

# 3. 更新 config.yaml 中的 port
port: /dev/ttyACM0  # 确认端口号正确

# 4. 添加串口权限
sudo chmod 666 /dev/ttyACM0
```

## Q2: 机械臂运动不顺畅或抖动

**可能原因**：
1. P 控制系数过高
2. 电源电压不稳定
3. 电机线缆接触不良

**解决方案**：

**检查电机线缆**：确保所有电机连接牢固

## Q3: 摄像头无法打开

**可能原因**：
1. 摄像头索引不正确
2. 摄像头被其他程序占用
3. 摄像头驱动问题

**解决方案**：

```bash
# Linux: 查看可用摄像头
v4l2-ctl --list-devices

# macOS: 查看摄像头
system_profiler SPCameraDataType
```

修改 `lekiwi_config.py` 中的摄像头索引：
```python
index_or_path=0,  # 尝试 0, 1, 2...
```

## Q4: 底盘轮子不转动但机械臂正常

**可能原因**：
1. 底盘电机线缆问题
2. 控制模式配置错误
3. 轮子被卡住

**解决方案**：

1. **检查电机控制模式**（`lekiwi.py:199-200`）：
   ```python
   self.bus.write("Operating_Mode", name, OperatingMode.VELOCITY.value)
   ```

2. **查看日志错误**（设置 `log_level: DEBUG`）

3. **手动测试底盘**：
   ```python
   robot.send_action({
       'x.vel': 0.1,
       'y.vel': 0.0,
       'theta.vel': 0.0,
   })
   ```

## Q5: 如何确认校准是否成功？

**检查方法**：

1. 启动后观察机械臂是否**平滑移动到中点位置**
2. 检查日志中是否显示：
   ```
   Calibration saved to ~/.cache/huggingface/lerobot/calibration/robots/lekiwi/None.json
   ```

3. 验证校准文件存在且内容完整：
   ```bash
   cat ~/.cache/huggingface/lerobot/calibration/robots/lekiwi/None.json | head -20
   ```

## Q6: 关节角度与预期不符

**可能原因**：
1. 零位偏移不正确
2. 缩放因子不准确

**解决方案**：

调整 `arm_inverse_controller.py` 中的校准参数：
```python
JOINT_CALIBRATION = [
    ['arm_shoulder_pan', 6.0, 1.0],  # 调整偏移和缩放
    ['arm_shoulder_lift', 2.0, 0.97],
    ...
]
```

或**重新校准**：
```bash
rm ~/.cache/huggingface/lerobot/calibration/robots/lekiwi/None.json
python -m src.main
```

## Q7: 运动时末端执行器轨迹不平滑

**可能原因**：
1. 步长设置过大
2. P 控制增益过高

**解决方案**：

1. **调整运动控制参数**（`arm_inverse_controller.py`）：
   ```python
   MOTION_PARAMS = {
       'max_step': 0.005,   # 减小可提高平滑度
       'slow_dist': 0.08,   # 增大减速距离
       ...
   }
   ```

2. **调整 P 控制增益**：
   ```python
   p_control_loop(..., kp=0.3)  # 降低 kp 提高稳定性
   ```

## Q8: 启动时卡在校准界面

**可能原因**：
1. 机械臂不在中点位置
2. 关节行程记录不完整

**解决方案**：

1. 手动将机械臂所有关节置于**中点位置**
2. 按回车继续
3. 缓慢转动每个关节经过完整行程

## Q9: 校准文件丢失或损坏

**解决方案**：

删除损坏的校准文件并重新启动：
```bash
rm ~/.cache/huggingface/lerobot/calibration/robots/lekiwi/None.json
python -m src.main
```

## 快速恢复

如需完全恢复出厂设置：

```bash
# 删除所有校准缓存
rm -rf ~/.cache/huggingface/lerobot/

# 重置配置
# 编辑 config.yaml 确认参数正确

# 重新启动
python -m src.main
```

## 诊断命令汇总

| 命令 | 用途 |
|------|------|
| `ls -l /dev/ttyACM*` | 检查串口设备 |
| `lerobot-find-port` | 自动查找端口 |
| `cat ~/.cache/huggingface/lerobot/calibration/robots/lekiwi/None.json` | 查看校准文件 |
| `python -m src.main` | 启动程序 |
| `sudo chmod 666 /dev/ttyACM0` | 修复串口权限 |
