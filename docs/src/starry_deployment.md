# Starry 部署 (Starry Deployment)

本文档说明当前仓库如何为 Starry / RK3588 准备运行时环境，重点覆盖：

- libuvc 相机运行时库的预编译与打包
- 目标机运行时依赖检查
- USB 权限与驱动切换
- Starry 上的启动方式

## 目标

当前方案的目标是：

- 开发机负责构建 native 库和整理运行时依赖
- Starry 目标机尽量只负责运行，不依赖现场 `cmake` 编译
- 相机采集使用 libuvc，不再依赖 lerobot/OpenCV 相机链路

## 当前目录约定

Starry 运行时预编译目录固定为：

```text
thirdparty/prebuilt/starry/aarch64/lib/
```

当前约定至少包含：

- `libdw_uvc_camera.so`
- `libuvc.so*`
- `libusb-1.0.so*`

其中：

- `libdw_uvc_camera.so` 是本项目自己的 native 封装库
- `libuvc.so*` 和 `libusb-1.0.so*` 是 libuvc 运行时依赖

## detector.py 的加载顺序

[`src/vision/detector.py`](../../src/vision/detector.py) 当前按以下顺序加载相机 native 库：

1. `DW_UVC_CAMERA_LIB_PATH`
2. `DW_UVC_PREBUILT_DIR`
3. `thirdparty/prebuilt/starry/<arch>/lib`
4. `thirdparty/prebuilt/starry/aarch64/lib`
5. 本地构建输出 `src/native/uvc_camera/build/libdw_uvc_camera.so`

说明：

- 在 `aarch64/arm64` 上默认不依赖运行时编译
- 在开发机上，如果没找到预编译库，允许回退到本地 `cmake` 构建
- 可以用环境变量强制控制：

```bash
export DW_UVC_PREBUILT_DIR=/path/to/prebuilt/lib
export DW_UVC_CAMERA_LIB_PATH=/path/to/libdw_uvc_camera.so
export DW_UVC_DISABLE_BUILD=1
export DW_UVC_ALLOW_BUILD=1
```

## 开发机准备

### 1. 构建 native 相机库

在开发机根目录执行：

```bash
cmake -S src/native/uvc_camera -B src/native/uvc_camera/build
cmake --build src/native/uvc_camera/build
```

输出文件：

```text
src/native/uvc_camera/build/libdw_uvc_camera.so
```

### 2. 打包 Starry 运行时依赖

执行：

```bash
bash scripts/package_starry_runtime.sh
```

脚本会做以下事情：

- 把 `libdw_uvc_camera.so` 复制到 `thirdparty/prebuilt/starry/aarch64/lib/`
- 尝试从当前宿主机查找并复制：
  - `libuvc.so*`
  - `libusb-1.0.so*`

执行后目录中通常会看到：

```text
thirdparty/prebuilt/starry/aarch64/lib/
├── libdw_uvc_camera.so
├── libuvc.so.0
└── libusb-1.0.so.0
```

### 3. 检查运行时资源是否齐全

执行：

```bash
bash scripts/check_runtime_env.sh
```

它会检查：

- `libdw_uvc_camera.so`
- `libuvc.so*`
- `libusb-1.0.so*`
- `src/yolov/models/tennis.rknn`
- `numpy`

如果检查失败，先不要部署到目标机。

## 目标机部署

### 1. 拷贝运行时文件

至少需要把以下内容复制到 Starry 目标机：

- 项目代码
- `thirdparty/prebuilt/starry/aarch64/lib/`
- `src/yolov/models/tennis.rknn`
- `config.yaml`

如果目标机上没有完整 Python 环境，还需要同时准备：

- Python 解释器
- `numpy`
- RKNN Python 运行时

### 2. 设置运行时库搜索路径

启动前建议设置：

```bash
export DW_UVC_PREBUILT_DIR=/path/to/project/thirdparty/prebuilt/starry/aarch64/lib
export LD_LIBRARY_PATH="${DW_UVC_PREBUILT_DIR}:${LD_LIBRARY_PATH:-}"
```

说明：

- `DW_UVC_PREBUILT_DIR` 告诉 `detector.py` 去哪里找预编译 `.so`
- `LD_LIBRARY_PATH` 让动态链接器能找到 `libuvc.so` 和 `libusb-1.0.so`

### 3. 启动程序

按当前仓库逻辑，入口仍然是：

```bash
python -m src.main
```

如果是在 RK3588 / Starry 上运行，建议在 `config.yaml` 中使用：

```yaml
hardware_mode: rk3588
control_mode: inverse
```

## USB 权限与驱动切换

如果目标机环境和 Ubuntu 类似，且存在 `udev` 与 `uvcvideo`，可以继续复用仓库里的脚本。

### 1. 安装 USB 权限规则

```bash
sudo bash scripts/install_uvc_udev_rule.sh 0ac8 0346 plugdev
```

作用：

- 给指定 USB 摄像头设备添加访问权限
- 避免 libuvc 访问时报 `Access denied`

### 2. 切换 `uvcvideo` 绑定状态

如果 libuvc 需要直接接管摄像头，可执行：

```bash
sudo bash scripts/manage_uvc_driver.sh unbind 0ac8 0346
```

如果之后要恢复给 V4L2 / OpenCV 使用：

```bash
sudo bash scripts/manage_uvc_driver.sh bind 0ac8 0346
```

说明：

- Starry 上是否存在同样的 `udev`/`uvcvideo` 机制，要以目标系统实际能力为准
- 如果 Starry 没有这些用户态工具，这部分需要迁移成系统镜像内置配置或启动阶段处理

## 推荐部署流程

推荐按下面顺序执行：

1. 在开发机构建 `libdw_uvc_camera.so`
2. 执行 `scripts/package_starry_runtime.sh`
3. 执行 `scripts/check_runtime_env.sh`
4. 把项目代码、模型和 `thirdparty/prebuilt/starry/aarch64/lib/` 复制到目标机
5. 在目标机设置 `DW_UVC_PREBUILT_DIR` 和 `LD_LIBRARY_PATH`
6. 如有需要，配置 USB 权限并解绑 `uvcvideo`
7. 执行 `python -m src.main`

## 常见问题

### 1. 运行时报找不到 `libdw_uvc_camera.so`

优先检查：

- `thirdparty/prebuilt/starry/aarch64/lib/libdw_uvc_camera.so` 是否存在
- `DW_UVC_PREBUILT_DIR` 是否指向正确目录
- `DW_UVC_CAMERA_LIB_PATH` 是否被错误设置

### 2. 运行时报找不到 `libuvc.so` 或 `libusb-1.0.so`

优先检查：

- `LD_LIBRARY_PATH` 是否包含预编译目录
- 预编译目录中是否确实有 `libuvc.so*`、`libusb-1.0.so*`
- 是否执行过 `scripts/package_starry_runtime.sh`

### 3. 运行时报 `Failed to start libuvc camera`

常见原因：

- USB 权限不足
- 摄像头被 `uvcvideo` 占用
- 目标机未枚举到对应 USB 设备

建议先检查：

- `scripts/install_uvc_udev_rule.sh`
- `scripts/manage_uvc_driver.sh`

### 4. Starry 上不能运行 `cmake`

当前设计就是为了解决这个问题：

- 目标机默认不依赖运行时编译
- 应优先使用预编译 `.so`

如果目标机仍然触发了本地构建，请检查：

```bash
echo $DW_UVC_PREBUILT_DIR
echo $DW_UVC_CAMERA_LIB_PATH
```

并确认预编译目录是否完整。

## 后续建议

如果后面继续收敛 Starry 部署链路，建议追加：

- `scripts/run_starry.sh`
  统一设置环境变量并启动主程序
- `docs/starry_deploy.md` 的板级版本说明
  区分 Ubuntu 开发机、Starry 目标机、RK3588 板端的差异
- 把 `.so` 打包流程接入 CI 或构建流水线

