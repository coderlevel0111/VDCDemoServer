# Apple VDC Demo · GitHub Codespaces

当前固定使用 `org.iso.18013.5.1.mDL` / `org.iso.18013.5.1`，请求 `age_over_18` 和 `document_number`。旧校园凭证需要重新领取。

更新运行中的服务请读 [MDL-UPGRADE.md](MDL-UPGRADE.md)。本地修改不会自动更新 Codespaces。

一个 Python 服务，同时提供网页与 mdoc API。网站通过 Safari 的 Digital Credentials API 请求 iOS App 中的mDL 测试凭证，服务端执行真实解密和验证。只有固定虚构 mDL资料，不模拟成功结果。

## 运行在 GitHub

逐步手动部署请读 [DEPLOY.md](DEPLOY.md)，包含上传、登录、Codespaces、HTTPS 验收和排错。无需连接 Codex GitHub 插件。

1. 把本目录作为独立仓库上传 GitHub，创建该仓库的 Codespace。
2. 开发容器会安装两个 Python 依赖并启动服务。查看 `/tmp/vdc-demo.log`。
3. 在 Codespaces 的 **PORTS** 面板把 **8000 → Port Visibility → Public**。
4. 保留端口内部协议为 **HTTP**。外部地址由 GitHub 自动提供 HTTPS：
   `https://<codespace-name>-8000.app.github.dev`。
5. 在 iPhone Safari 打开该地址；把同一地址填入 iOS App“系统凭证”的服务地址。
6. App 连接、核对两个根指纹、领取并完成系统注册后，在网站准备验证，再点击“使用 iPhone 凭证”。

**无需 GitHub Pages、购买域名或安装自签网站证书。** GitHub Pages 不能运行 Python；这里用的是 Codespaces 的临时开发服务。代码仓库可以是私有的，转发端口仍可单独设为 Public；组织政策可能限制公共端口。

Codespace 停止或休眠后网址不能访问。演示前启动同一个 Codespace，演示后停止以节省额度。删除并重建环境会生成新网址和新的发行/Reader 密钥，App 需人工核对新指纹、更新信任并重新领取。

## 本地运行

```sh
sh ./run.sh
```

打开 `http://127.0.0.1:8000`。普通局域网 HTTP 不用于真实 iPhone 系统 API 演示。若已有外部 HTTPS 反向代理，可显式指定：

```sh
PUBLIC_ORIGIN=https://demo.example sh ./run.sh --port 8000
```

在 Codespaces 中无需填写 PUBLIC_ORIGIN；服务从 CODESPACE_NAME 和转发域自动确定。**来源固定为配置值，不信任客户端的 Host/X-Forwarded-* 头**，避免代理配置错误或任意来源请求。

## iOS 配置仍然独立

公网 HTTPS 解决了网站连接与证书问题，不会授予 App 系统文档权限。宿主与扩展仍需相同开发者 Team、共享 Keychain、对应文档类型 entitlement 和有效 provisioning。

当前固定类型为 `org.iso.18013.5.1.mDL`、namespace 为 `org.iso.18013.5.1`，仅签发虚构 mDL 测试子集，非真实驾照。实际 provisioning 和用户授权仍需核实。此前模拟签名注册返回 notAuthorized，尚未证明完整 Safari 系统选择链路在真机通过。

接口与现有 `SystemWalletView.swift`、`MDocEngine.swift` 保持兼容。网页只使用真实 `navigator.credentials.get({digital:...})`，没有 URL Scheme 回退、手动会话 ID 或假钱包。iOS App 直接进入 mDL 测试钱包；旧“基础实验”接口不再由这个简化服务提供。

## 文件

- `server.py`：标准库 HTTP、固定来源校验、有限静态文件白名单和四个 POST API。
- `mdoc.py`：原有 mdoc/COSE/ReaderAuth/设备签名/HPKE 引擎，保留所有验证。
- `static/index.html`、`app.js`、`style.css`：无构建步骤、无 CDN 的演示页面。
- `.devcontainer/devcontainer.json`：自动安装、启动、转发 8000。
- `test_server.py`、`test_mdoc.py`：运行中的 HTTP 代理场景和密码学反例。

依赖只有 cryptography 和 cbor2。没有 Node、前端框架、Dockerfile、云数据库或额外部署服务。

## API

| 路径 | 用途 |
| --- | --- |
| GET /health | 服务健康 |
| GET /api/mdoc/config | origin、类型、公开根证书及核对指纹；所有值保留为字符串以兼容 App |
| POST /api/mdoc/issue | 设备公钥 → 虚构虚构 mDL |
| POST /api/mdoc/request | origin → 签名的一次性系统请求 |
| POST /api/mdoc/verify | 加密响应 → 真实验证结果 |
| POST /api/mdoc/revoke | 每卡撤销令牌 → 撤销 |

数据和私钥只保存在 `data/`，被 gitignore 排除，任何静态路由都不能读取。服务器不记录请求正文。成功请求立即擦除其 HPKE 接收私钥；新请求清理过期交易。固定虚构卡的签发为开放接口，公共演示中不要使用真实个人资料。

## 测试

```sh
.venv/bin/python -m unittest -v
```

包含：官方 RFC 9180 P-256 HPKE 向量、合法选择披露、篡改/重放/换钥/错来源/撤销/过期拒绝、代理内层 HTTP 与外层 HTTPS、原生 App 无 Origin 头、非法输入及私有文件访问拒绝。

本实现是单进程、单发行者、单文档的教学配置，不是通用钱包或 ISO 符合性认证产品。旧 JWT 辅助实验仅在原机器 `.archive/` 本地归档，不上传新仓库。网站上线和协议测试通过不等于 Apple entitlement 已获得或真机系统流程已验收。
