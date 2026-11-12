# ImgZip

## 1. 项目简介

ImgZip 是一个基于 Python 3 和 PyQt5 的桌面工具，用于制作包含封面图片与字幕资料的「图种」文件。

### 主要功能

- **封面处理**：载入 JPG、JPEG、PNG、BMP、WEBP 图片；在界面中以 350×500 预览，支持移动取景和马赛克涂抹，并提供撤销。
- **固定导出尺寸**：最终封面统一导出为 560×800 JPEG，预览尺寸不会改变导出分辨率。
- **电影信息**：填写电影 ID、番号（banko）和 magnet 链接。
- **字幕管理**：一部电影可添加多个字幕文件；选择字幕后自动统计字幕条数，支持手动修改条数和填写匹配时长。
- **图种生成**：把封面 JPEG 与包含 `index.json` 和字幕文件的 ZIP 数据合并，最终只输出一个 JPG 文件。
- **便捷解包**：生成的 JPG 可以正常预览；将扩展名改为 `.zip` 后即可解出 `index.json` 和字幕文件。

### 运行与构建环境

| 项目 | 要求 |
|---|---|
| Python | 3.8.5 或以后 |
| PyQt5 | 5.15.11 |
| Pillow | 10.4.0（固定版本） |
| Windows | Windows 7 SP1 及以后；为兼容 Win7，请使用 Python 3.8.x 构建 |
| macOS | macOS 11 及以后；Intel 与 Apple Silicon 分别构建原生版本 |

Windows 7 使用 Python 3.8.x 的构建路径；本项目的 GitHub Actions 固定使用 Python 3.8.10 构建 Windows EXE。Python 3.9 及以后不支持 Windows 7，不应用于需要兼容 Win7 的 Windows 构建。

macOS 构建脚本会检测当前 Python 的 CPU 架构：Intel Python 构建 x86_64 App，Apple Silicon Python 构建 arm64 App。两个架构由 GitHub Actions 分别构建并发布。

### 项目结构

```text
ImgZip/
├── .github/
│   └── workflows/
│       └── release.yml       # GitHub Actions 自动构建与发布
├── assets/                   # 应用图标资源
├── imgzip/                   # 应用界面、数据模型与图种处理逻辑
│   ├── image_panel.py        # 封面预览、裁剪、马赛克与 JPEG 导出
│   ├── info_panel.py         # 电影信息与字幕表单
│   ├── main_window.py        # 主窗口与保存流程
│   ├── models.py             # 电影与字幕数据结构
│   ├── packer.py              # index.json、ZIP 与图种封装
│   └── subtitle_utils.py     # 字幕编码读取与字幕条数统计
├── tools/
│   ├── install_icon.py       # 图标资源转换工具
│   └── sync_version.py      # 同步应用与 Windows 文件版本
├── main.py                   # 程序入口
├── requirements.txt          # 运行依赖
├── version_info.txt          # Windows EXE 版本资源
├── build_win.bat             # Windows 本地打包脚本
└── build_mac.sh              # macOS 本地打包脚本
```

## 2. 本地运行

首次运行前，需要在项目根目录创建虚拟环境并安装依赖。构建脚本也会优先使用项目目录下的 `.venv`，其次使用 `venv`，两者都不存在时才使用系统 Python。

### Windows 运行

**Windows 7：** 建议安装 64 位 Python 3.8.x（GitHub Actions 使用 Python 3.8.10），然后在项目根目录打开 CMD：

```bat
py -3.8 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade "pip<25"
python -m pip install -r requirements.txt
python main.py
```

**Windows 8.1 及以后：** 可使用 Python 3.8.5 或以后版本。创建环境时，将 `py -3.8` 替换为本机对应的 Python 启动器版本，例如 `py -3.11`；其余命令相同。

### macOS 运行

在项目根目录打开终端。使用当前 Mac 原生架构的 Python 3.8.5 或以后版本：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

退出虚拟环境：

```bash
deactivate
```

运行期间，终端需要保持打开；关闭程序窗口即可结束应用。

## 3. 修改版本号与本地打包

### 修改版本号

项目版本的唯一维护入口是 `imgzip/__init__.py`：

```python
APP_NAME = "ImgZip"
APP_VERSION = "1.0.0"
```

发布新版本时，将 `APP_VERSION` 修改为目标版本，例如 `1.0.1`。然后在项目根目录执行版本同步脚本：

```bash
python tools/sync_version.py 1.0.1
```

Windows CMD 也可执行同一命令：

```bat
python tools\sync_version.py 1.0.1
```

脚本会把版本同步到 `version_info.txt` 中的 `filevers`、`prodvers`、`FileVersion` 和 `ProductVersion`。macOS 打包脚本会把同一版本写入 `.app` 的 `Info.plist`。两个本地打包脚本本身也会在构建前读取 `APP_VERSION` 并执行同步，因此日常本地打包只需维护 `imgzip/__init__.py` 的版本值。

版本号使用 `主版本.次版本.修订版本` 格式，例如 `1.0.0`、`1.0.1`、`1.0.2`。

### Windows 本地打包

为保证生成的 EXE 可以在 Windows 7 SP1 运行，请使用 Python 3.8.x（建议 3.8.10），并确保项目 `.venv` 中已安装依赖。运行：

```bat
build_win.bat
```

成功后生成：

```text
dist\ImgZip.exe
```

脚本会根据 Python 版本选择打包工具：Python 3.8 使用面向 Win7 的 PyInstaller 4.10；Python 3.9 及以后使用较新的 PyInstaller，但生成物不保证兼容 Windows 7。构建日志写入项目根目录的 `build_win.log`。

### macOS 本地打包

在要生成目标架构的 Mac 上，使用对应架构的 Python，执行：

```bash
bash build_mac.sh
```

成功后生成：

```text
dist/ImgZip.app
```

Intel Mac 会生成 x86_64 App；Apple Silicon Mac 会生成 arm64 App。脚本将最低系统版本设置为 macOS 11.0，并检查生成文件的架构。若需要同时发布两种架构，需要分别在 Intel 与 Apple Silicon 构建环境执行脚本。

本地构建结果位于 `dist/`；PyInstaller 中间文件位于 `build/`。这两个目录已加入 `.gitignore`，不需要提交到 Git。

## 4. GitHub Actions 自动打包

项目已配置 `.github/workflows/release.yml`。推送符合 `vX.Y.Z` 格式的 Git tag 后，GitHub Actions 会自动并行执行三个构建任务；三个任务全部成功后，自动创建 GitHub Release 并上传安装包。

### 首次配置与推送

先将项目提交并推送到 GitHub 仓库默认分支（以下以 `main` 为例）：

```bash
git add .
git commit -m "Prepare ImgZip 1.0.0"
git push origin main
```

确认 GitHub 仓库已包含 `.github/workflows/release.yml`，然后创建并推送版本 tag：

```bash
git tag -a v1.0.0 -m "ImgZip v1.0.0"
git push origin v1.0.0
```

以后发布新版本时，先修改 `imgzip/__init__.py` 的 `APP_VERSION`，运行版本同步脚本，提交修改，再推送相同版本号的 tag。例如发布 `1.0.1`：

```bash
python tools/sync_version.py 1.0.1
git add imgzip/__init__.py version_info.txt
git commit -m "Prepare ImgZip 1.0.1"
git push origin main
git tag -a v1.0.1 -m "ImgZip v1.0.1"
git push origin v1.0.1
```

### 自动构建平台

| 构建任务 | GitHub Runner | Python / 架构 | 目标平台 |
|---|---|---|---|
| Windows | `windows-2022` | Python 3.8.10 x64 | Windows 7 SP1 及以后（x64） |
| Mac Intel | `macos-15-intel` | x86_64 | macOS 11 及以后（Intel） |
| Mac Apple Silicon | `macos-15` | arm64 | macOS 11 及以后（Apple Silicon） |

工作流以 Git tag 为版本来源，在构建环境中自动同步应用版本、Windows 版本资源及 macOS `Info.plist`。Windows 使用单文件 EXE；两个 macOS 任务分别生成原生 `.app`，并压缩成 ZIP。

### Release 下载文件

以 `v1.0.0` 为例，自动发布的 GitHub Release 包含：

| 文件名 | 内容 | 适用平台 |
|---|---|---|
| `ImgZip_v1.0.0_Win.exe` | 单文件 EXE | Windows 7 SP1 及以后（x64） |
| `ImgZip_v1.0.0_MacIntel.zip` | `ImgZip.app` 压缩包 | macOS 11 及以后（Intel） |
| `ImgZip_v1.0.0_MacApple.zip` | `ImgZip.app` 压缩包 | macOS 11 及以后（Apple Silicon） |

在 GitHub 仓库的 **Actions** 页面查看构建过程和日志；全部成功后，在 **Releases** 页面下载三个安装包。发布需要工作流具备仓库内容写入权限；当前 workflow 已为发布 job 声明 `contents: write`。
