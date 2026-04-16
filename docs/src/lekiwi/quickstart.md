# LeKiwi 快速开始

## 环境要求

### 安装 Miniforge

```bash
wget "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
bash Miniforge3-$(uname)-$(uname -m).sh
```

### 创建 Python 3.10 环境

```bash
conda create -y -n lerobot python=3.10
conda activate lerobot
```

### 安装依赖

```bash
conda install ffmpeg -c conda-forge
git clone https://github.com/huggingface/lerobot.git
cd lerobot
pip install -e .
pip install -e ".[feetech]"
```

## 硬件连接

1. 使用 USB 线将控制板连接到 PC
2. 连接 12V 8A 电源适配器
3. 检查串口端口

```bash
lerobot-find-port
```

## 启动命令

```bash
conda activate lerobot
cd /path/to/Desktop-Wanderer
python -m src.main
```

## 初始化流程

### 代码层面初始化顺序

```python
# 1. 加载配置 (main.py:48)
init_app()  # 从 config.yaml 读取配置到全局变量

# 2. 初始化机器人对象 (robot_setup.py:29)
init_robot()
#   └─ cfg = LeKiwiConfig(port=get_port())
#   └─ _robot = LeKiwi(cfg)

# 3. 连接硬件 (main.py:52)
robot.connect()
#   ├─ bus.connect()                    # 连接串口总线
#   ├─ calibrate()                      # 如未校准则校准
#   ├─ cam.connect()                    # 连接摄像头
#   └─ configure()                      # 配置电机参数

# 4. 获取初始状态 (main.py:54)
start_obs = robot.get_observation()
```

## 首次校准

### 校准触发条件

满足以下任一条件时进入校准：

1. 首次使用设备（无校准文件）
2. 校准文件与电机实际值不匹配
3. 启动时输入 `c` 手动选择重新校准

### 校准步骤

#### 第一步：居中机械臂

**代码位置**: `lekiwi.py:152`

```
Move robot to the middle of its range of motion and press ENTER....
```

将所有机械臂关节手动转动到**行程中点位置**，按回车确认。

#### 第二步：记录关节行程

**代码位置**: `lekiwi.py:162-169`

```
Move all arm joints except '[full_turn_motor]' sequentially through their entire ranges of motion.
```

依次缓慢转动每个关节，确保经过**上下限位**，按回车停止。

> 注意：轮子电机和腕部滚动无需手动转动，系统自动跳过。

#### 第三步：保存校准

校准文件保存至：
```
~/.cache/huggingface/lerobot/calibration/robots/lekiwi/None.json
```

## 后续启动

已有校准文件时：

```
Press ENTER to use provided calibration file associated with the id None, or type 'c' and press ENTER to run calibration:
```

| 操作 | 效果 |
|------|------|
| 按 Enter | 使用现有校准文件继续 |
| 输入 `c` + Enter | 重新校准 |
| 等待 3 秒 | 自动使用现有校准文件 |

## 强制重新校准

```bash
rm ~/.cache/huggingface/lerobot/calibration/robots/lekiwi/None.json
python -m src.main
```

## 机械臂预设位置

**文件**: `robot_setup.py`

```python
_start_positions = {
    'arm_shoulder_pan': 0.0,
    'arm_shoulder_lift': -31.70,
    'arm_elbow_flex': 27.69,
    'arm_wrist_flex': 80.00,
    'arm_wrist_roll': 0.0,
    'arm_gripper': 10.0
}
```
