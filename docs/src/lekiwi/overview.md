# LeKiwi 概述与代码架构

## 硬件组成

| 组件 | 数量 | 说明 |
|------|------|------|
| 机械臂 | 1 | 6自由度，含夹爪 |
| 移动底盘 | 1 | 三全向轮结构 |
| 摄像头 | 1 | 前置 OpenCV 相机 |

## 模块关系

```
main.py (入口)
    │
    ├── setup.py          # 全局配置管理
    │       └── config.yaml
    │
    ├── robot_setup.py    # 机器人初始化
    │       │
    │       └── lekiwi/lekiwi.py  # LeKiwi 机器人类
    │               ├── connect()      # 连接并校准
    │               ├── calibrate()    # 校准流程
    │               ├── configure()    # 配置电机参数
    │               ├── get_observation()  # 获取传感器数据
    │               └── send_action()     # 发送控制指令
    │
    ├── arm_inverse_controller.py  # 逆运动学控制
    │
    ├── arm_act_controller.py      # ACT 模式控制
    │
    └── move_controller.py        # 底盘移动控制
```

## 核心类说明

| 类/模块 | 文件 | 职责 |
|---------|------|------|
| `LeKiwi` | `lekiwi/lekiwi.py` | 机器人主类，管理连接、校准、控制 |
| `LeKiwiConfig` | `lekiwi/lekiwi_config.py` | 机器人配置（端口、摄像头等） |
| `DirectionControl` | `lekiwi/direction_control.py` | 底盘速度方向控制 |
| `KeyboardTeleop` | `lekiwi/key_board_teleop.py` | 键盘遥控输入 |
| `Robot` | `lekiwi/robot.py` | 抽象基类，定义机器人接口 |

## 电机列表

### 机械臂电机（位置模式）

| 电机名称 | ID | 控制模式 | 标准范围 |
|----------|-----|----------|----------|
| `arm_shoulder_pan` | 1 | 位置 | -100~100 |
| `arm_shoulder_lift` | 2 | 位置 | -100~100 |
| `arm_elbow_flex` | 3 | 位置 | -100~100 |
| `arm_wrist_flex` | 4 | 位置 | -100~100 |
| `arm_wrist_roll` | 5 | 位置 | -100~100 |
| `arm_gripper` | 6 | 位置 | 0~100 |

### 底盘电机（速度模式）

| 电机名称 | ID | 控制模式 | 标准范围 |
|----------|-----|----------|----------|
| `base_left_wheel` | 7 | 速度 | -100~100 |
| `base_back_wheel` | 8 | 速度 | -100~100 |
| `base_right_wheel` | 9 | 速度 | -100~100 |

## 键盘控制映射

**文件**: `lekiwi/key_board_teleop.py`

| 按键 | 动作 | 速度调节 |
|------|------|----------|
| W | 前进 | |
| S | 后退 | |
| A | 左移 | |
| D | 右移 | |
| Q | 左转 | |
| E | 右转 | |
| ] | 加速 | 切换到下一档 |
| [ | 减速 | 切换到上一档 |
| Esc | 退出 | |

## 底盘速度档位

**文件**: `lekiwi/direction_control.py`

| 档位 | xy速度 (m/s) | 角速度 (deg/s) | 说明 |
|------|-------------|----------------|------|
| 0 | 0.02 | 15 | 特慢 |
| 1 | 0.05 | 30 | 慢 |
| 2 | 0.25 | 50 | **中（默认）** |
| 3 | 0.40 | 80 | 快 |
