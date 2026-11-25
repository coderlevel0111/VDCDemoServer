# mDL 三端统一、授权排错与升级

2026-11-25 起，本项目唯一支持的文档类型为 `org.iso.18013.5.1.mDL`，不再发行、请求或注册自定义校园 docType。当前使用下面的受限虚构 mDL 测试配置，不代表真实驾照、正式发行资质或完整 ISO mDL 符合性。

## 1. 三端必须一致的配置

| 项目 | 唯一取值 |
| --- | --- |
| docType | `org.iso.18013.5.1.mDL` |
| namespace | `org.iso.18013.5.1` |
| 浏览器协议 | `org-iso-mdoc`，它不是 docType |
| 本次出示字段 | `age_over_18`（布尔值）和 `document_number`（字符串） |
| 请求保留数据 | 两个字段的 intentToRetain 都为 false |
| 演示业务政策 | `age_over_18` 必须严格为 true，且文档编号未撤销 |

Apple 的 Mobile Document Provider entitlement 文档列出了支持的文档类型，其中包含 mDL；注册类型必须在实际 entitlement 中。本项目现在固定选择这个支持的类型，不再假设能 provision 任意自定义字符串。官方资料：[entitlement 支持值](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.identity-document-services.document-provider.mobile-document-types)、[实现提供方](https://developer.apple.com/documentation/identitydocumentservices/implenting-as-an-identity-document-provider)。

这次不是只把校园字符串重命名为驾照：同时更换 namespace、签发字段、请求字段和业务策略。签发的虚构材料还包含 `given_name` 和 `family_name`，值明确为 DEMO ONLY / NOT A REAL LICENCE，出示时不披露它们。为了最小演示，本项目没有提供完整 mDL 的全部必需属性和画像，不宣称标准符合性认证，也不应用来证明现实身份或驾驶资格。

## 2. Review 后修改的位置

| 层 | 文件和检查点 |
| --- | --- |
| iOS 宿主/共享引擎 | `SharedCore/MDocEngine.swift` 固定类型和 namespace；保存的旧凭证必须重新通过 MSO 与字段验证才能注册 |
| iOS entitlement | `Config/Host.entitlements` 与 `Config/Provider.entitlements` 仅列出 mDL，沿用你现有 Team 和 Bundle ID |
| 宿主配置连接 | 同时检查服务的 doc_type、namespace 和 origin，错误中显示两端实际值 |
| 系统注册 | 注册 mDL；成功替换单卡后清理旧注册；只有 authorized 才读取 registrations |
| 扩展 | 仅接收匹配 mDL 和 namespace 的请求，用户批准后验证 ReaderAuth 并加密响应；未授权时不进行注册同步 |
| 后端 `mdoc.py` | 配置、MSO、IssuerSigned、ReaderAuth 请求、响应类型、摘要、撤销和业务校验统一使用 mDL |
| 网页 `static/` | mDL/年龄证明文案，先检查类型和 namespace，一致后才允许准备；将 true 显示为“是” |
| 测试 | 固定配置断言、旧类型与 namespace 拒绝、Apple 解析器、Swift/Python 互通、授权启动回归 |

ExtensionKit target 的历史工程名称仍为 `CampusDocumentProvider`，这是 Xcode target 名称，不是线上 docType；不为外观命名而改变你的签名标识。

## 3. 两类报错的区别

### `RegistrationError.notAuthorized`

旧代码会在 App 启动和回前台时直接读取 `store.registrations`。此时用户可能尚未授权，读取就会报错，容易被误认为“连接 mdoc 配置”失败。

新代码先读取不抛异常的 `store.status`，只有 `.authorized` 才读注册列表。`.notDetermined` 不代表网络错误：第一次真正调用 `addRegistration` 才触发系统授权。若用户曾拒绝，Apple 说明可在 Settings 中本 App 的页面重新启用。没有单独的 `requestAuthorization()` 调用可以替代这一步。

“连接并读取 mdoc 配置”只负责 HTTP 配置、类型一致性和根指纹，不要求已经获得文档提供授权。更改 docType 也不会自动同意系统授权；必须检查实际 provisioning 并完成用户授权。

### `Connection reset by peer`

这是网络连接被对端或中间链路重置，与系统文档授权不是同一问题。系统网络日志里的这一行本身不能证明整次请求最终失败。先看 App 的操作结果，并用同一 iPhone 的 Safari 打开公网 `/health` 和 `/api/mdoc/config`。

新代码在 URLSession 抛出 URLError 时会显示网络错误码和检查入口，不再让你混淆授权与网络。没有为 POST 自动重试，以免重复签发或重复提交验证。

## 4. 更新 GitHub/Codespaces 服务

本地 `VDCDemoServer` 已修改，不代表你正在运行的 Codespace 已更新。先把新源码上传到 GitHub，再更新运行环境。

### Git 推送方式

在 Mac 终端进入后端目录，确认 origin 是你自己的目标仓库：

```sh
cd /Users/junlei/Documents/dev/VDCDemoServer
git status --short
git remote -v
git log -1 --oneline
```

本次交付已包含后端本地提交。如果你修改了自己的副本，应先按需提交改动再推送：

```sh
git push
```

没有配置 upstream 时，可执行 `git push -u origin HEAD`。没有 origin 时按第 11 章登录并设置远端。

在 Codespaces 中，先在运行 Python 的终端按 Ctrl+C 停止旧服务。然后在仓库根目录执行：

```sh
git status --short
git pull --ff-only
sh ./run.sh --port 8000
```

如果 Codespaces 中有未提交的修改，先检查并保存自己的改动，不要强制覆盖；若提示分支不一致，先核对仓库当前分支。保留服务终端运行，PORTS 面板确认 8000 为 Public，内部协议为 HTTP。

### 网页上传方式

解压这次生成的 `VDCDemoServer-deploy.zip`，将其中的源码覆盖上传到原仓库，保留 `.devcontainer/` 等隐藏目录结构。不要只上传 ZIP 本身。随后仍需在 Codespaces 停服务、`git pull --ff-only` 并重新运行。

若你直接把文件上传进 Codespaces 工作区，则不必 `git pull`，但应提交并推送这些代码，避免仓库与运行环境长期不同步。

### 验收实际运行的版本

另开 Codespaces 终端执行：

```sh
curl -fsS http://127.0.0.1:8000/api/mdoc/config | python3 -m json.tool
```

必须看到：

```json
{
  "doc_type": "org.iso.18013.5.1.mDL",
  "namespace": "org.iso.18013.5.1"
}
```

上面只是完整 JSON 中的两个关键字段，其余根证书等字段也会存在。再用 iPhone Safari 打开 `https://legendary-spork-544jp4rj96p24g7-8000.app.github.dev/api/mdoc/config` 核对。同样返回 mDL 才说明公网运行的是新版本。网页刷新后应显示 mDL 测试凭证和年龄证明，不再显示学生身份。

无需删除服务器 `data/`：本次升级可以保留发行根和 Reader 根。删除会换掉密钥并导致 App 根指纹不一致；仅为切换类型不应清空它们。

## 5. 更新 iPhone

1. Xcode 重新编译并安装宿主和扩展，保留你已设置的 Team、Bundle ID、共享 Keychain。检查实际签名的两个文档类型 entitlement 都只有 mDL。
2. 点击连接配置。若仍报类型不一致，先更新服务，不要放宽 App 校验。
3. 原发行/Reader 根未改变时沿用固定信任；变更时先人工核对指纹，再重置信任。
4. 重新领取 mDL 测试凭证。旧校园 MSO、旧 namespace、旧请求不能直接改名使用，不能复用。
5. 第一次注册同意系统提示。如果状态为 notAuthorized，在 iOS 设置中本 App 页面启用文档提供，并检查 provisioning，返回 App 重试注册。
6. 成功注册后，到同一 Safari 网站准备并出示。扩展按钮为“同意并出示 mDL 测试凭证”。

旧服务创建的网页交易最多两分钟过期；升级后重新准备请求。旧卡即使没过期也会因 MSO 类型或 namespace 不兼容而被拒绝。本机读取旧卡失败时会将其视为无有效卡，成功注册新卡后清理旧单卡注册。

## 6. 验证范围

本次验证结果：16 项后端测试通过，3 项 Swift 常规单元测试和 1 项 Apple 解析器/Swift-Python 协议集成测试通过，1 项 UI 回归测试通过；模拟器与真机 SDK 构建通过。真机 SDK 编译不使用签名、不等于实际设备授权。

后端新增固定 mDL 配置、旧类型拒绝和旧 namespace 拒绝测试；保留选择披露、篡改、设备换钥、错来源、重放、撤销、过期与 RFC 9180 HPKE 向量，共 16 项。

iOS 常规测试检查固定 profile、Base64URL、来源校验和未授权启动时不错误读取注册列表。独立协议测试检查 Apple 原始请求解析及 Swift/Python 的 mDL 加密响应互通；完整 Safari 系统 UI 仍需你使用真实权限验收，不能由编译或协议测试代替。


## 7. Codespaces 网页准备请求报来源不受信任

已实测公网配置 origin 正确，但携带同一个公网 Origin 的 POST 仍被旧后端拒绝。这符合开发隧道改写 Origin 为内部 localhost 的行为；本地 HTTP 集成测试已覆盖这种情况。微软隧道项目的说明：[Origin 重写问题](https://github.com/microsoft/dev-tunnels/issues/284)。由于旧错误信息没有返回接收到的值，不能仅凭该错误断言某次请求的具体内部 Origin；新版拒绝信息会显示收到值和期望值。

修复仍固定协议 origin 为公网 HTTPS，不使用客户端 Host 或 X-Forwarded 头改写它。只有 Origin 是当前监听端口的精确回环 HTTP 别名时，才额外检查：

- 浏览器的 Sec-Fetch-Site 必须是 same-origin。
- X-VDC-Browser-Token 必须匹配本次服务启动生成的随机令牌。
- 令牌由同源配置接口返回，网页读取后随 POST 发送；该配置响应不允许跨域读取，跨站自定义请求头的预检也不获授权。

这不是登录令牌，不是对开放演示 API 增加用户身份认证；非浏览器仍可按现有原生 API 调用。它用于防止为了兼容回环 Origin 而放宽浏览器跨站访问。非匹配来源、缺失/错误令牌、cross-site、same-site、错误端口和 null Origin 都会拒绝。协议请求正文的 origin、ReaderAuth 与加密会话仍绑定公网来源。

GET /api/mdoc/config 多一个字符串 browser_request_token，兼容 App 的字符串字典解析。iOS 无需修改。后端重启会更换网页令牌；更新后必须重新加载网页，不要继续使用重启前的页面。

更新至少需要 server.py 与 static/app.js 一起生效：推送或上传新版，停止旧 Python，拉取代码并重启，然后在 iPhone Safari 关闭旧页面重新打开。仅 git pull 而不重启后端，或只更新 JS，都不能完成修复。新版本后端共 17 项测试通过；已有协议测试结果保留。
