# 手动部署：GitHub 仓库 + Codespaces + HTTPS

本章适用于 2026-11-24 的简化 Demo。你在自己的浏览器和终端操作即可，不依赖 Codex 的 GitHub 插件。前提是 GitHub 账号可正常建仓库并使用 Codespaces；手动操作不能解除 suspended 限制，账号问题需要通过 GitHub 支持处理。

## 1. 最终会得到什么

| 部分 | 放在哪里 | 作用 |
| --- | --- | --- |
| iOS App 和凭证扩展 | 本地 `VDCDemo`，用 Xcode 安装到 iPhone | 持有凭证、系统注册、用户授权、出示 |
| 网页和后端 | 将 `VDCDemoServer` 单独上传 GitHub，运行在 Codespaces | 签发虚构校园凭证、生成请求、解密验证 |
| 知识文档 | 本地 `VDCDemoDoc`；仓库内另有本章副本 `DEPLOY.md` | 入门、配置、部署、排错 |

最终访问地址类似 `https://<codespace-name>-8000.app.github.dev`，不是 `github.com/用户名/仓库`，也不是 `用户名.github.io`。

GitHub Pages 是静态网站服务，不能运行本项目的 Python 签发和验证逻辑。因此只创建仓库、启用 Pages 或运行 Actions，都不会让后端持续运行。这里选择 Codespaces 开发容器：同一个 Python 进程提供 HTML、JS、CSS 和 API，网页使用同源相对路径，不用单独设置 API 地址或 CORS。依据：[GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)、[Codespaces 入门](https://docs.github.com/en/codespaces/quickstart)。

Codespaces 是临时开发环境，受额度、计费和休眠限制；不是免费永久在线的生产服务器。创建前查看自己账号的 Codespaces 额度与账单设置。

## 2. 推荐方式：上传已准备好的本地 Git 仓库

Mac 上本地仓库已建立，源码已提交；不必重新 `git init`，也不必复制 iOS 工程进去。

### 2.1 检查本地目录

在 Mac 的“终端”执行：

```sh
cd /Users/junlei/Documents/dev/VDCDemoServer
git status --short
git branch --show-current
git ls-files
```

`git status --short` 为空表示工作区干净。当前分支为 `codex/github-demo`；以实际命令输出为准。上传清单里应有 `.devcontainer/devcontainer.json`、`server.py`、`mdoc.py`、`static/` 和 `requirements.txt`。

`data/`、`.archive/`、`.venv/` 和私钥均已被忽略。不要使用强制添加忽略文件的命令；不要把整个工作目录拖到网页上传，以免把运行数据一起上传。

### 2.2 在 GitHub 创建空仓库

1. 在浏览器登录可用账号，打开 [创建仓库](https://github.com/new)。
2. Owner 选择自己的账号；Repository name 填 `VDCDemoServer`。
3. 选择 Private 即可。代码仓库是否公开与稍后演示端口是否公开，是两项独立设置。
4. 不勾选初始化 README，不添加 Gitignore 或 License：本地已有提交，远端先保持为空，避免首次推送冲突。
5. 点击 Create repository，保存页面显示的 HTTPS 仓库地址，例如 `https://github.com/你的用户名/VDCDemoServer.git`。

官方步骤：[创建新仓库](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository)。

### 2.3 用 GitHub CLI 登录

如果已安装 `gh`，跳过安装。如果你已有 Homebrew，可执行：

```sh
brew install gh
```

没有 Homebrew 时，可从 [GitHub CLI 官网](https://cli.github.com/) 选择适合 Mac 的安装方式；不需要为了这个项目安装前端 Node 工具链。

然后执行：

```sh
gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git --hostname github.com
gh auth status
```

按终端提示在浏览器完成授权，确认显示的是要部署的账号。登录、验证码和授权由你自己完成，不要把密码或 token 粘贴到聊天中。GitHub 的 HTTPS Git 推送不能用账号密码代替授权；这里让 `gh` 配置凭据，不把 token 写进 URL。官方说明：[登录](https://cli.github.com/manual/gh_auth_login)、[Git 凭据配置](https://cli.github.com/manual/gh_auth_setup-git)。

### 2.4 添加远端并推送

先检查是否已有远端：

```sh
cd /Users/junlei/Documents/dev/VDCDemoServer
git remote -v
```

如果没有输出，执行下面命令。**必须把 `YOUR_GITHUB_USERNAME` 替换成你的 GitHub 用户名**：

```sh
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/VDCDemoServer.git
git push -u origin HEAD
```

如果已有 origin，确认它是不是目标仓库。如果地址错误，先核对正确地址，再用以下命令替换，之后推送：

```sh
git remote set-url origin https://github.com/YOUR_GITHUB_USERNAME/VDCDemoServer.git
git push -u origin HEAD
```

刷新仓库页面，切换到已推送的 `codex/github-demo` 分支，确认文件出现在仓库根目录。根目录应直接包含 `server.py` 和 `.devcontainer/`，不要再嵌套一层 `VDCDemoServer/`。

如果误建了带 README 的仓库，且推送失败，不要强推覆盖不明提交。可以给本地项目另建一个空的目标仓库，再修改 origin 并推送。

### 2.5 备选：使用源码 ZIP，在网页上传

随本次交付提供 `VDCDemoServer-deploy.zip`，只包含待发布源码，不含数据库、密钥、虚拟环境、归档或 `.git`。

1. 解压到一个新的空目录。不要将 ZIP 本身作为唯一文件上传：GitHub 不会自动解压运行。
2. 打开新建的空仓库，使用上传现有文件入口（已有文件的仓库可选 Add file → Upload files）。
3. 上传解压目录内的文件和子目录，而不是外层文件夹。Mac Finder 可按 `Command + Shift + .` 显示隐藏项。
4. 确保 `.devcontainer/`、`.github/` 和 `.gitignore` 没有漏掉，提交上传。
5. 如果隐藏目录没有上传成功，可在网页 Add file → Create new file 中输入完整路径 `.devcontainer/devcontainer.json`，粘贴源码里的原内容并提交。其他遗漏文件同样补齐。

网页上传会丢失脚本可执行位，所以本项目统一支持 `sh ./run.sh`。不必执行 chmod。优先使用 Git 推送，它会可靠保留目录和权限。

## 3. 创建 Codespace

1. 打开上传完成的仓库，确认当前分支包含 `.devcontainer/devcontainer.json`。
2. 点击绿色 Code → Codespaces → Create codespace on 当前分支。界面文字可能随分支名变化。
3. 选择最小的可用配置即可。等待容器创建和初始化完成，浏览器会打开 VS Code 风格的编辑器。
4. 配置会自动创建 `.venv`，安装两个 Python 直接依赖，并通过 `nohup sh ./run.sh` 启动服务。
5. 在终端执行：

```sh
tail -n 40 /tmp/vdc-demo.log
curl -fsS http://127.0.0.1:8000/health
```

正常健康检查返回 `{"ok":true}`。日志应显示“本地监听”“公开地址”和两个根指纹。这里的 localhost 只代表 Codespace 容器，不是 iPhone。

如果找不到终端，可从编辑器菜单 Terminal → New Terminal 打开。若自动安装失败，先检查日志/创建日志和网络，再在仓库根目录执行 `sh ./run.sh`；如果已有进程成功监听，不要同时再启动第二份。

## 4. 把 8000 端口开放为公网 HTTPS

1. 打开编辑器底部 PORTS 面板。找不到时，从 View 菜单或命令面板搜索 Ports。
2. 应自动出现 8000；没有就点击 Add Port，输入 `8000`。
3. 右键 8000 → Port Visibility → Public。
4. 内部端口协议保持 HTTP。不要为了获取公网 HTTPS 把内部协议改成 HTTPS：本项目的 Python 监听的是 HTTP。
5. 复制该端口的转发地址，应为 `https://...-8000.app.github.dev`，在新标签页打开。
6. 用无痕窗口，或未登录 GitHub 的 iPhone Safari 再打开一次。必须能看到演示网页，而不是 GitHub 登录页。

外部 HTTPS 的证书和 TLS 由 GitHub 提供；Python 与转发代理之间使用 HTTP。公网 URL 是 HTTPS，并不要求 Python 自己也安装网站证书。因此不需要购买域名、不需要自签证书、不需要在手机上安装 CA。

Public 端口允许知道 URL 的人访问演示接口，但不会公开私有代码仓库。组织政策可能禁止 Public；这种情况下本方案的手机匿名 API 接入不能成立。官方说明：[端口、协议、可见性与公网地址](https://docs.github.com/en/codespaces/developing-in-a-codespace/forwarding-ports-in-your-codespace)。

## 5. 三步确认服务器部署成功

### 5.1 健康检查

用手机打开公网地址后追加 `/health`，应直接显示 `{"ok":true}`。不能是登录页、404 或 502。

### 5.2 来源检查

打开公网地址后追加 `/api/mdoc/config`，检查 `origin` 等于你正在使用的网址来源，例如：

```text
https://实际的-codespace-name-8000.app.github.dev
```

不带 `/api`、路径、查询串和末尾斜杠。服务自动从 Codespaces 环境变量生成这个来源；通常不必手工配置 PUBLIC_ORIGIN。若设置过旧 PUBLIC_ORIGIN，它会覆盖自动发现，应先清除旧配置后重启服务。

### 5.3 网页检查

打开网站首页，展开“连接诊断与信任指纹”。当前地址与服务端公开地址应一致、安全上下文应为 true。浏览器 API 支持状态取决于设备与浏览器，不支持并不代表 Python 服务没有部署成功。

不要把 GitHub 仓库 URL、Codespaces 编辑器 URL 或 `http://127.0.0.1:8000` 填到 iPhone App。

## 6. iPhone 演示顺序

1. 用 Xcode 安装正确签名的宿主 App 与扩展。开发团队、文档类型、共享 Keychain 和实际 provisioning 见第 09 章。这里只部署服务器，不改变 iOS 签名配置。
2. App 选择“系统凭证”，填写第 4 步得到的公网 HTTPS origin。
3. 连接服务，用可信的 Codespaces 终端输出核对 App 中的发行根和 Reader 根指纹，再建立信任。仅网页自己显示一个指纹不能独立证明它可信。
4. 领取固定虚构校园凭证，执行系统注册；先确认注册成功。
5. 在 iOS 26+ Safari 顶层页面打开同一网站。点击“准备验证”，服务器建立短有效期请求。
6. 再点击“使用 iPhone 凭证”。网页在这次用户点击中直接调用 Digital Credentials API，交给系统选择与授权。
7. 扩展验证 ReaderAuth 与来源，返回选定字段、设备持钥证明及加密响应。服务端解密验证后，网页才显示“验证通过”。

网站没有模拟成功或 URL Scheme 回退；旧 App“基础实验”页和旧 `/lab` API 不在这版后端中。

**已知边界：** 目前尚未完成真实 iPhone Safari 全链路验收。此前模拟签名注册返回 notAuthorized；自定义类型 `org.example.vdc.campus.1` 能否获得你团队的实际授权，必须用 provisioning 与真机系统注册确认。公网 HTTPS、网页有 API、协议测试通过都不能替代这一步。

本次网站部署不用增加 AASA 或 Universal Links。网页调用系统 Digital Credentials API，协议与扩展校验网站来源和 Reader 信任；App 本身的凭证能力与文档类型权限仍然需要。安全原理见第 10 章。

## 7. 以后如何更新、停止和重新启动

修改代码后，在 Mac 查看差异，只提交要发布的源码，再推送：

```sh
cd /Users/junlei/Documents/dev/VDCDemoServer
git diff
git status --short
```

例如只修改了网页脚本：

```sh
git add static/app.js
git commit -m "Update demo web flow"
git push
```

推送不会自动更新或重启已运行的 Codespace。在 Codespaces 终端先检查工作区干净，再拉取：

```sh
git status --short
git pull --ff-only
```

随后通过 Codespaces 管理页面停止并重新启动同一个环境，让启动钩子运行新代码。只刷新浏览器不会重启后端。若改了开发容器配置，需要运行 Codespaces: Rebuild Container；不要删除整个 Codespace来“更新”。

演示后打开 [Codespaces 管理页面](https://github.com/codespaces)，对当前环境选择 Stop codespace。下次打开同一个环境，检查服务、端口 Public 和公网 URL 后继续。

`data/` 保存数据库、发行根和 Reader 私钥。停止同一个环境通常保留数据；删除环境或清空数据会失去原密钥，重新生成后必须核对新指纹并重新领取。不要把私钥提交到 GitHub 来“持久化”。自动启动服务的数据目录位于仓库工作区，不使用 `/tmp` 保存这些密钥。

## 8. 常见问题

| 现象 | 原因与操作 |
| --- | --- |
| GitHub 显示 suspended / 403 | 先通过 GitHub 支持解决账号问题；手动部署也需要账号可用 |
| `gh: command not found` | 安装 GitHub CLI，或使用源码 ZIP 的网页上传方式 |
| `remote origin already exists` | 用 `git remote -v` 核对，必要时按 2.4 替换地址 |
| Repository not found / 权限不足 | 核对账号、仓库地址和仓库访问权限，检查 `gh auth status` |
| Codespace 内找不到 devcontainer 配置 | 上传漏了隐藏目录或多嵌套了一层；补齐后重建容器 |
| `run.sh: Permission denied` | 使用 `sh ./run.sh`；本项目自动启动也使用 sh，不依赖执行位 |
| `Address already in use` | 已有服务监听 8000，不要重复启动；先检查 `/health` 和日志 |
| 手机打开 GitHub 登录页 / App 收到 HTML | 把 8000 从 Private 改成 Public，并用无痕窗口复查 |
| 网页 502 | 检查 Python 日志、监听端口和内部 HTTP 协议 |
| 服务来源不一致 | 核对实际公网 URL 和配置中的 origin，清除旧 PUBLIC_ORIGIN 后重启 |
| 没有 Public 选项 | 组织策略可能限制端口公开，联系管理员确认 |
| HTTP 能在电脑打开、手机调用失败 | 使用 Codespaces 公网 HTTPS URL，不能使用手机自己的 localhost |
| iOS 注册 notAuthorized | 检查真实签名、entitlement 与 provisioning；网站 HTTPS 不能修复 App 权限 |
| 新环境中的凭证不可信 | 密钥换了，核对新指纹后更新信任并重新领取 |
| Codespace 停止后网站打不开 | 这是开发环境，演示时需保持运行；按账号额度使用 |

## 9. 本次验证与文件边界

后端保留 13 项可运行测试：mdoc 合法选择披露、官方 RFC 9180 HPKE 向量、篡改/重放/换钥/错来源/撤销/过期拒绝，以及代理来源、输入与私有文件访问检查。在 Codespaces 中可执行：

```sh
.venv/bin/python -m unittest -v
```

仓库的 Actions 也会运行这套测试；Actions 的绿色勾只表示测试成功，不表示服务在线或真机验收通过。网页已完成 JavaScript 语法检查和桌面/窄屏布局检查；真实系统选择器需要第 6 节条件。

当前只准备源码和手动操作步骤，尚未替你在 GitHub 创建仓库或启动公网服务。完成第 5 节后才能称为服务器部署成功；完成第 6 节才能称为 Apple 真机链路跑通。
