# 概述

## 项目介绍和功能特性
项目介绍和功能特性
Desktop-Wanderer 是一个基于视觉引导的小型机器人系统，实现了自主目标检测、导航和抓取功能。系统采用模块化设计，支持多种硬件加速方案，具备以下核心功能特性：

- 视觉感知：基于YOLO的目标检测系统，支持ONNX CPU推理和Atlas 310B、RK3588 NPU硬件加速 [process.py](https://github.com/my-robot-army/Desktop-Wanderer/blob/4d26d3f7de81720ed1aae138e22fe11437374bbd/src/yolov/process.py)
- 智能导航：视觉引导的移动控制，能够自动导航至目标位置 [move_controller.py](https://github.com/my-robot-army/Desktop-Wanderer/blob/4d26d3f7/src/move_controller.py)
- 精确操作：支持两种机械臂控制模式 - ACT学习策略和逆运动学控制 [setup.py](https://github.com/my-robot-army/Desktop-Wanderer/blob/main/src/setup.py)
- 状态管理：基于状态机的行为控制，实现搜索-抓取的自动化流程 [setup.py](https://github.com/my-robot-army/Desktop-Wanderer/blob/main/src/setup.py)

## 系统架构概览

Desktop-Wanderer 采用四层分层架构设计，从应用层到硬件层逐级抽象：

![img.png](./images/img_1.png)

系统核心是位于 src/main.py 的主控制循环 [main.py](https://github.com/my-robot-army/Desktop-Wanderer/blob/main/src/main.py#L10-L20) ，负责协调各个子系统：
- 初始化阶段：加载配置、初始化机器人连接、读取初始关节角度 
- 感知阶段：获取机器人观测数据，执行YOLO目标检测 
- 决策阶段：根据当前状态选择相应控制器（移动控制或机械臂控制） 
- 执行阶段：发送控制指令到机器人，维持指定FPS控制频率 

## 快速开始指南

### 环境准备
1. 硬件要求：  
- LeKiwi机器人平台
- USB串口连接舵机控制板
- 12V8A电源连接舵机控制板

2. 软件依赖
> pip install -r requirements.txt

3. lerobot 平台安装

python 3.10环境准备
```commandline
wget "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
bash Miniforge3-$(uname)-$(uname -m).sh
conda create -y -n lerobot python=3.10
```
lerobot 安装
```commandline
conda activate lerobot
conda install ffmpeg -c conda-forge
git clone https://github.com/huggingface/lerobot.git
cd lerobot
pip install -e .
# 舵机驱动安装
pip install -e ".[feetech]"
```

详细说明可看安装与配置部分

### 配置设置

修改 config.yaml 配置文件：
```
port: /dev/tty.usbmodem5AE60581751 # 串口号
fps: 20 # 帧率
log_level: INFO # 日志级别
hardware_mode: normal # normal, 310b, rk3588
control_mode: inverse # inverse, act
```


