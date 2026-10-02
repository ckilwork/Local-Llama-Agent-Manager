# Local Llama Agent Manager

一个用于 Windows 的本地 `llama.cpp` / `llama-server` 图形管理器。它负责保存启动配置、启动和停止服务器、查看日志与生成速度，并提供浏览器地址和 OpenAI 兼容 API Base URL 的一键复制。

## 功能

- 中文 / English 界面，保存多个服务器配置模板
- 设置模型、可选 `mmproj`、可选 MTP 草稿模型，以及上下文长度、GPU 层数等启动参数
- 根据 `/health` 区分准备中与运行中；从 `/slots` 估算实时生成速度
- 保存、选择、删除本地系统提示词方案
- 查看启动命令预览和运行日志

> 本项目不包含 `llama-server.exe` 或任何模型文件。MTP 等选项是否可用，取决于所使用的 `llama-server` 版本和模型。

## 下载 Windows x64 版

从 [Releases 下载最新 ZIP](https://github.com/ckilwork/Local-Llama-Agent-Manager/releases/latest)。完整解压后运行 `Local-Llama-Agent-Manager.exe`；不要只提取 EXE，程序需要同目录下的 `_internal` 文件夹。首次启动时选择本机的 `llama-server.exe` 和模型文件。

## 从源码运行

在 Windows 上安装 Python 3.13，然后在本目录执行：

```powershell
python -m pip install -r requirements.txt
python main.py
```

首次启动时选择本机的 `llama-server.exe` 和模型文件。个人配置保存在 `%LOCALAPPDATA%\LlamaCppLauncher\presets.json`，不在本仓库中。

## 测试与打包

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q tests
python -m PyInstaller --noconfirm --clean Local-Llama-Agent-Manager.spec
```

打包输出位于 `dist\Local-Llama-Agent-Manager`。构建配置会排除与 Qt 冲突的第三方 ICU DLL。打包后可运行 `Local-Llama-Agent-Manager.exe --self-test` 检查 Qt 启动依赖；成功时退出码为 0。

## 许可证

[MIT](LICENSE)
