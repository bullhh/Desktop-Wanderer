# LeKiwi 调试方法

## 日志调试

修改 `config.yaml` 中的 `log_level`：

```yaml
log_level: DEBUG  # 获取最详细的调试信息
```

### 日志级别说明

| 级别 | 输出内容 |
|------|----------|
| DEBUG | 电机状态、观测数据、控制输出等详细信息 |
| INFO | 连接成功、校准完成等关键事件 |
| WARNING | 潜在问题但不影响运行 |
| ERROR | 连接失败、控制异常等错误 |

## 摄像头调试

**文件**: `main.py:91-105`

在 `hardware_mode: normal` 模式下，会显示实时摄像头画面：

```python
if get_hardware_mode() == 'normal':
    cv2.imshow("frame", frame)  # 显示画面
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break  # 按 q 退出
```

### 摄像头相关调试操作

1. **显示画面**: 设置 `hardware_mode: normal`
2. **隐藏画面**: 设置 `hardware_mode: rk3588`
3. **按 q 退出**: 在摄像头窗口按下 q 键

## 串口连接调试

### 查找端口

```bash
# 方法1：使用 lerobot 工具
lerobot-find-port

# 方法2：手动查看
ls -l /dev/ttyACM*  # Linux
ls -l /dev/ttyUSB*  # Linux
ls /dev/cu.*        # macOS
```

### 串口权限问题

```bash
# 添加读写权限
sudo chmod 666 /dev/ttyACM0

# 或将用户添加到 dialout 组
sudo usermod -a -G dialout $USER
```

### 常见串口问题

- **权限不足**: `sudo chmod 666 /dev/ttyACM0`
- **端口被占用**: 检查是否有其他程序占用串口
- **端口名称错误**: 确认 `config.yaml` 中 `port` 与实际一致

## 电机状态调试

### 获取当前电机状态

```python
# 获取当前电机观测数据
obs = robot.get_observation()
print(obs)
```

**输出示例**：
```
{
  'arm_shoulder_pan.pos': 0.5,
  'arm_shoulder_lift.pos': -31.7,
  'arm_elbow_flex.pos': 27.69,
  'arm_wrist_flex.pos': 80.0,
  'arm_wrist_roll.pos': 0.0,
  'arm_gripper.pos': 10.0,
  'x.vel': 0.0,
  'y.vel': 0.0,
  'theta.vel': 0.0,
  'front': <numpy.ndarray shape=(480, 640, 3)>
}
```

### 手动发送控制指令

#### 发送机械臂位置控制

```python
robot.send_action({
    'arm_shoulder_pan.pos': 10.0,
    'arm_shoulder_lift.pos': -20.0,
    'arm_elbow_flex.pos': 15.0,
    'arm_wrist_flex.pos': 80.0,
    'arm_wrist_roll.pos': 0.0,
    'arm_gripper.pos': 50.0,
    'x.vel': 0.0,
    'y.vel': 0.0,
    'theta.vel': 0.0,
})
```

#### 发送底盘速度控制

```python
robot.send_action({
    'x.vel': 0.1,      # 前进 (m/s)
    'y.vel': 0.0,      # 侧移 (m/s)
    'theta.vel': 30.0, # 旋转 (deg/s)
})
```

## P 控制调试

**文件**: `arm_inverse_controller.py`

```python
def p_control_loop(cmd, current_x, current_y, current_obs, kp=0.5):
    # kp: 比例增益
    # 增大 kp：响应更快但可能振荡
    # 减小 kp：响应慢但更平稳
```

### 调参建议

| 问题 | 调整方法 |
|------|----------|
| 响应太慢 | 增大 kp（建议 0.5~1.0） |
| 出现振荡 | 减小 kp（建议 0.2~0.4） |
| 运动不平滑 | 减小 max_step 参数 |

## 校准数据调试

### 查看校准文件

```bash
cat ~/.cache/huggingface/lerobot/calibration/robots/lekiwi/None.json
```

### 验证校准是否成功

1. 启动后观察机械臂是否平滑移动到中点位置
2. 检查日志中是否显示 "Calibration saved"
3. 验证校准文件存在且内容完整

## 独立调试脚本

创建 `debug_robot.py`：

```python
#!/usr/bin/env python
import sys
sys.path.insert(0, 'src')

from lekiwi import LeKiwi, LeKiwiConfig

# 创建机器人实例
config = LeKiwiConfig(port="/dev/ttyACM0")
robot = LeKiwi(config)

# 连接
print("Connecting...")
robot.connect()

# 打印观测数据
print("\n=== Robot Observation ===")
obs = robot.get_observation()
for key, value in obs.items():
    if key != 'front':
        print(f"  {key}: {value}")

# 测试控制
print("\n=== Testing Control ===")
action = {
    'arm_shoulder_lift.pos': -10.0,
    'arm_elbow_flex.pos': 10.0,
    'x.vel': 0.0,
    'y.vel': 0.0,
    'theta.vel': 0.0,
}
robot.send_action(action)

# 断开
robot.disconnect()
print("Done")
```

### 运行调试脚本

```bash
python debug_robot.py
```

## 打印初始化信息

**文件**: `main.py:54-64`

启动时会打印初始关节角度：

```
Reading initial joint angles...
Initial joint angles:
  arm_shoulder_pan: 0°
  arm_shoulder_lift: -31.7°
  arm_elbow_flex: 27.69°
  arm_wrist_flex: 80°
  arm_wrist_roll: 0°
  arm_gripper: 10°
```

## 快速调试检查清单

- [ ] 串口连接正常 (`ls /dev/ttyACM*`)
- [ ] 摄像头可访问 (`cv2.VideoCapture(0).isOpened()`)
- [ ] 校准文件存在
- [ ] 日志级别设置为 DEBUG
- [ ] 电源电压稳定 (12V 8A)
