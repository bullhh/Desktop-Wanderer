# LeKiwi 配置参数详解

## config.yaml

项目根目录的配置文件：

```yaml
port: /dev/ttyACM0      # 串口设备路径
fps: 20                 # 控制频率 (Hz)
log_level: INFO         # 日志级别：DEBUG, INFO, WARNING, ERROR
hardware_mode: normal    # 硬件模式：normal (PC), rk3588 (控制板)
control_mode: inverse    # 控制模式：inverse (逆运动学), act (ACT策略)
```

### 配置项说明

| 配置项 | 可选值 | 说明 |
|--------|--------|------|
| `port` | `/dev/ttyACM0`, `/dev/ttyUSB0` 等 | 串口设备路径 |
| `fps` | 正整数 | 控制频率，建议 20Hz |
| `log_level` | DEBUG, INFO, WARNING, ERROR | 日志详细程度 |
| `hardware_mode` | normal, rk3588 | normal=PC调试，rk3588=控制板运行 |
| `control_mode` | inverse, act | inverse=逆运动学，act=ACT策略 |

## LeKiwiConfig 配置类

**文件**: `lekiwi/lekiwi_config.py`

```python
@dataclass
class LeKiwiConfig(RobotConfig):
    port: str = "/dev/ttyACM0"           # 串口端口
    disable_torque_on_disconnect: bool = True  # 断开时禁用扭矩
    max_relative_target: float | dict = None    # 相对目标限制
    cameras: dict = lekiwi_cameras_config()    # 摄像头配置
    use_degrees: bool = False            # 是否使用角度制
```

## 摄像头配置

**文件**: `lekiwi/lekiwi_config.py`

```python
def lekiwi_cameras_config() -> dict[str, CameraConfig]:
    return {
        "front": OpenCVCameraConfig(
            index_or_path=0,    # 摄像头索引（0, 1, 2...）
            fps=30,             # 帧率
            width=640,          # 图像宽度
            height=480,         # 图像高度
            color_mode=ColorMode.BGR
        ),
    }
```

## 电机参数配置

**文件**: `lekiwi/lekiwi.py`

### 机械臂电机（位置模式）

```python
for name in self.arm_motors:
    self.bus.write("Operating_Mode", name, OperatingMode.POSITION.value)
    self.bus.write("P_Coefficient", name, 16)   # P控制系数
    self.bus.write("I_Coefficient", name, 0)    # I控制系数
    self.bus.write("D_Coefficient", name, 32)  # D控制系数
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| P_Coefficient | 16 | 比例系数，调低可减少抖动 |
| I_Coefficient | 0 | 积分系数 |
| D_Coefficient | 32 | 微分系数 |

### 底盘电机（速度模式）

```python
for name in self.base_motors:
    self.bus.write("Operating_Mode", name, OperatingMode.VELOCITY.value)
```

## 关节校准参数

**文件**: `arm_inverse_controller.py`

```python
JOINT_CALIBRATION = [
    ['arm_shoulder_pan', 6.0, 1.0],      # [电机名, 零位偏移, 缩放因子]
    ['arm_shoulder_lift', 2.0, 0.97],
    ['arm_elbow_flex', 0.0, 1.05],
    ['arm_wrist_flex', 0.0, 0.94],
    ['arm_wrist_roll', 0.0, 0.5],
    ['arm_gripper', 0.0, 1.0],
]
```

| 参数 | 说明 |
|------|------|
| 零位偏移 | 校正电机零点误差 |
| 缩放因子 | 校正角度缩放比例 |

## 运动控制参数

**文件**: `arm_inverse_controller.py`

```python
MOTION_PARAMS = {
    'max_step': 0.01,    # 最大步长 (m/帧)
    'min_step': 0.001,   # 最小步长 (m/帧)
    'slow_dist': 0.05,   # 减速距离 (m)
    'dead_zone': 0.0005  # 死区 (m)
}
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| max_step | 0.01 | 远距离时每帧移动 2cm |
| min_step | 0.001 | 精细调整时每帧移动 1mm |
| slow_dist | 0.05 | 距离目标 5cm 以内开始减速 |
| dead_zone | 0.0005 | 误差小于 0.5mm 认为到达 |

## 逆运动学参数

**文件**: `arm_inverse_controller.py`

```python
def inverse_kinematics(x, y, l1=0.1159, l2=0.1350):
    # l1: 上臂长度 (m)，肩部到肘部
    # l2: 下臂长度 (m)，肘部到腕部
```

| 参数 | 值 | 说明 |
|------|-----|------|
| l1 | 0.1159 m | 上臂长度 |
| l2 | 0.1350 m | 下臂长度 |

## 校准文件格式

**路径**: `~/.cache/huggingface/lerobot/calibration/robots/lekiwi/None.json`

```json
{
  "arm_shoulder_pan": {
    "id": 1,
    "drive_mode": 0,
    "homing_offset": 1234,
    "range_min": 0,
    "range_max": 4095
  },
  "arm_shoulder_lift": {
    "id": 2,
    "drive_mode": 0,
    "homing_offset": -567,
    "range_min": 0,
    "range_max": 4095
  }
}
```

| 字段 | 说明 |
|------|------|
| id | 电机 ID（在总线上的标识） |
| drive_mode | 驱动模式（0=电机模式） |
| homing_offset | 零位偏移量 |
| range_min | 关节最小位置值 |
| range_max | 关节最大位置值 |
