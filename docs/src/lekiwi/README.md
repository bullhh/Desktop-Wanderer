# LeKiwi 设备文档

本目录包含 LeKiwi 设备的完整文档。

## 文档结构

- [概述与架构 (Overview)](overview.md) - 代码架构和模块关系
- [快速开始 (Quickstart)](quickstart.md) - 首次启动与校准流程
- [工作流程 (Workflow)](workflow.md) - 捡球/放球状态机详解
- [配置参数 (Configuration)](configuration.md) - 详细配置参数说明
- [调试方法 (Debugging)](debugging.md) - 日志、摄像头、串口调试指南
- [故障排除 (Troubleshooting)](troubleshooting.md) - 常见问题与解决方案

## 快速链接

| 操作 | 命令 |
|------|------|
| 启动 | `python -m src.main` |
| 查找端口 | `lerobot-find-port` |
| 强制重新校准 | `rm ~/.cache/huggingface/lerobot/calibration/robots/lekiwi/None.json` |
