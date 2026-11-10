# ikuuu每日签到

通用的（机场只要 Powered by SSPANEL 就可以）机场签到。

## 推送

脚本采用 pushplus 推送（POST JSON）。

## 登录方式（重要）

面板自 2026 年起在登录页加了**极验 Geetest V4** 人机验证，`/auth/login` 必须携带
`phase=password` 与 `captcha_result`，纯脚本无法自动通过（返回 `captcha_failed`）。
因此推荐使用 **COOKIE 模式**：用浏览器登录一次，把登录态交给脚本，直接调 `/user/checkin`。

账号密码模式仍保留（`URL` + `INFO`），仅在面板关闭人机验证时可用。

## 域名说明

`ikuuu.de` / `ikuuu.eu` / `ikuuu.me` 已变成「最新域名发布页」，不再是面板，
脚本会直接报错提醒。当前面板域名：`https://ikuuu.top`（备用 `https://ikuuu.pw`）。

# 部署过程

1. 右上角 Fork 此仓库
2. 到 `Settings` → `Secrets and variables` → `Actions` 新建以下参数：

| 参数 | 是否必须 | 内容 |
|---|---|---|
| `URL` | 是 | 面板地址，必须是真面板，例如 `https://ikuuu.top` |
| `COOKIE` | 推荐 | 浏览器登录后的整条 Cookie；多账号用 `\|\|` 分隔 |
| `INFO` | 可选 | `邮箱<split>密码<split>pushplus_token`，多账号用 `,` 分隔；仅用于取推送 token，或面板未开验证码时的登录 |

3. 到 `Actions` 选择 `Airport Checkin` → `Run workflow`，以后每天 UTC+8 06:00 自动跑。
4. 在 `Run sign` 日志里确认结果，同时会推送到 pushplus。

## 如何取 COOKIE

1. 浏览器登录 `https://ikuuu.top`
2. F12 → Network → 任意一条请求 → 复制 `Cookie` 请求头整条内容（形如 `uid=xxx; email=xxx; key=xxx; ip=xxx; expire_in=xxx`）
3. 粘到 `COOKIE` secret

Cookie 一般 30 天级。过期后日志会报 `签到接口 302 到登录页：Cookie 已失效`，重新复制一次即可。

## 日志含义

| 输出 | 含义 |
|---|---|
| `签到结果：签到成功，获得 xxx G` | 正常 |
| `301/302 到登录页` | Cookie 失效，重新获取 |
| `已经是「域名发布页」` | URL 过期，换新域名 |
| `captcha_failed` | 面板开了极验，请用 COOKIE 模式 |
