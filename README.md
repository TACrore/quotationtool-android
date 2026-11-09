# 报价单工具 · Android（A 方案）

目标：Kivy 重写 UI，复用 `tools/quote_base.py`（飞书 Base/OpenAPI），reportlab 出 PDF，
python-for-android / buildozer 打成 APK。

## 当前环境结论（本机）

```
HypervisorPresent = False      → WSL2 不可用（需 BIOS 开启虚拟化）
当前用户非管理员               → 无法启用 WSL 功能/安装发行版
Java / Android SDK / Gradle    → 未安装
```

因此 **本机无法直接产出 APK**。两条可行路径：

### 路径 1：用户开虚拟化 + 管理员（本机装 WSL2）

1. BIOS 开启 VT-x / SVM
2. 管理员 PowerShell：`wsl --install -d Ubuntu`，重启
3. Ubuntu 内：
   ```bash
   sudo apt update && sudo apt install -y python3-pip git openjdk-17-jdk zip unzip \
        autoconf automake libtool pkg-config zlib1g-dev libncurses5-dev \
        libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
   pip3 install --user buildozer cython
   ```
4. 本目录：`buildozer -v android debug`

### 路径 2：GitHub Actions 云端构建（本机零改造）

把 `android/` 目录推到私有仓库，用 `p4a` 官方镜像构建，产物是 artifact。
工作流见 `android/.github/workflows/build-apk.yml`。

## 目录

```
android/
  main.py            Kivy 入口与界面
  appdata.py         数据层适配（复用 tools/quote_base.py）
  buildozer.spec     打包配置（包名、权限、字体、依赖）
  requirements.txt   本地开发依赖
  .github/workflows/build-apk.yml
```

## 功能范围（首发 = 最小可用）

- 登录（飞书扫码走 WebView/OAuth，或用 device flow）
- 客户列表（只显示本人负责的，Base 规则保证）
- 报价列表（按客户过滤，显示单价/币种/审批状态）
- 选图号 → 生成报价单 PDF（reportlab）→ 系统分享
- 通知查看（本人收件人）
- 不做：批量录入、权限管理、客户资料维护（保留在 Windows 端）

## 关键约束

- Android 上**没有 tkinter**，UI 全部用 Kivy 重写
- 飞书 OAuth 回调在手机上无 localhost，需改用 `feishu://callback` 或设备码方案
- 字体 18MB 需打进 APK（或按需下载），APK 预计 40–60MB
- Base 接口需要用户 token；token 存 Android Keystore/加密文件，不能明文
