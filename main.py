#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ikuuu (SSPANEL) 每日签到。

两种模式，优先级 COOKIE > URL+INFO：

COOKIE 模式（推荐）
    环境变量 COOKIE：浏览器登录后复制整条 Cookie 请求头。
    复用登录态直接 POST /user/checkin，跳过登录表单，也就绕开了极验验证码。
    多个账号的 Cookie 用 || 分隔。

账号模式（legacy）
    环境变量 URL、INFO（`邮箱<split>密码<split>pushplus_token`，多账号用 , 分隔）。
    面板升级后 /auth/login 要求 phase=password 并且必须携带极验 Geetest V4 的
    captcha_result，纯 requests 会被判 captcha_failed，因此该模式仅在面板关闭
    人机验证时可用。

推送：pushplus，走 POST JSON，不再把 token 和签到内容拼进 query string。
失败即非零退出，让 Actions 直接变红，而不是"绿色但没签到"。
"""

import json
import os
import sys
import time
import traceback

import requests

TIMEOUT = 20
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
PUSHPLUS_API = "https://www.pushplus.plus/send"
DEFAULT_BASE = "https://ikuuu.top"


def log(msg):
    print(msg, flush=True)


def build_session(base, cookie=None):
    session = requests.Session()
    session.headers.update(
        {
            "user-agent": UA,
            "accept": "application/json, text/plain, */*",
            "x-requested-with": "XMLHttpRequest",
            "origin": base,
            "referer": base + "/user",
        }
    )
    if cookie:
        session.headers["cookie"] = cookie.strip()
    return session


def read_json(resp, what):
    try:
        return resp.json()
    except ValueError:
        raise RuntimeError(
            "%s 返回的不是 JSON（HTTP %s）：%r"
            % (what, resp.status_code, resp.text[:200].replace("\n", " "))
        ) from None


def probe_base(base):
    """确认基地地址还是面板，而不是域名发布页。"""
    try:
        resp = requests.get(base + "/auth/login", timeout=TIMEOUT, headers={"user-agent": UA})
    except requests.RequestException as exc:
        raise RuntimeError("无法访问 %s：%s" % (base, exc)) from None
    if resp.status_code >= 400:
        raise RuntimeError("%s/auth/login 返回 HTTP %s" % (base, resp.status_code))
    text = resp.text
    if "originBody" in text or "SSPANEL" in text.upper() or "登录" in text:
        return
    if "最新域名" in text or "域名" in text:
        raise RuntimeError(
            "%s 已经是「域名发布页」，不再是面板。请打开该页面确认最新域名后更新 URL"
            "（当前可用：%s）" % (base, DEFAULT_BASE)
        )


def push(token, content):
    if not token:
        return
    try:
        resp = requests.post(
            PUSHPLUS_API,
            json={"token": token, "title": "ikuuu签到", "content": content},
            timeout=TIMEOUT,
        )
        log("推送结果：HTTP %s %s" % (resp.status_code, resp.text[:120]))
    except requests.RequestException as exc:
        log("推送失败（不影响签到判定）：%r" % exc)


def checkin_with_cookie(base, cookie, token):
    session = build_session(base, cookie)
    resp = session.post(base + "/user/checkin", timeout=TIMEOUT, allow_redirects=False)
    if resp.status_code in (301, 302, 303, 307):
        raise RuntimeError("签到接口 302 到登录页：Cookie 已失效，请重新登录后复制")
    data = read_json(resp, "签到接口")
    msg = data.get("msg") or json.dumps(data, ensure_ascii=False)[:200]
    log("签到结果：%s" % msg)
    push(token, msg)
    if data.get("ret") != 1:
        raise RuntimeError("签到未成功：%s" % msg)


def login_and_checkin(base, email, password, token):
    session = build_session(base)
    payload = {
        "host": base.split("://")[-1],
        "phase": "password",
        "email": email,
        "passwd": password,
        "remember_me": "on",
    }
    data = read_json(
        session.post(base + "/auth/login", data=payload, timeout=TIMEOUT), "登录接口"
    )
    if data.get("result") == "captcha_failed":
        raise RuntimeError(
            "登录被极验 Geetest V4 拦截（captcha_failed）：面板已要求人机验证，"
            "账号密码模式无法自动通过，请改用 COOKIE 模式"
        )
    if data.get("ret") != 1:
        raise RuntimeError("登录失败：%s" % (data.get("msg") or data))
    log("登录成功：%s" % data.get("msg", ""))

    data = read_json(
        session.post(base + "/user/checkin", timeout=TIMEOUT, allow_redirects=False),
        "签到接口",
    )
    msg = data.get("msg") or json.dumps(data, ensure_ascii=False)[:200]
    log("签到结果：%s" % msg)
    push(token, msg)
    if data.get("ret") != 1:
        raise RuntimeError("签到未成功：%s" % msg)


def parse_info(raw):
    accounts = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = [p.strip() for p in chunk.split("<split>")]
        while len(parts) < 3:
            parts.append("")
        accounts.append({"email": parts[0], "password": parts[1], "token": parts[2]})
    return accounts


def main():
    base = (os.environ.get("URL") or "").strip().rstrip("/") or DEFAULT_BASE
    cookie_raw = (os.environ.get("COOKIE") or "").strip()
    accounts = parse_info((os.environ.get("INFO") or "").strip())

    log("目标站点：%s" % base)
    probe_base(base)

    failures = []
    if cookie_raw:
        cookies = [c.strip() for c in cookie_raw.split("||") if c.strip()]
        log("模式：COOKIE，共 %d 个会话" % len(cookies))
        for idx, cookie in enumerate(cookies):
            token = accounts[idx]["token"] if idx < len(accounts) else ""
            try:
                checkin_with_cookie(base, cookie, token)
            except Exception as exc:
                log("会话#%d 失败：%s" % (idx + 1, exc))
                traceback.print_exc()
                push(token, "签到失败：%s" % exc)
                failures.append(str(exc))
            time.sleep(2)
    elif accounts:
        log("模式：账号密码（legacy），共 %d 个账号" % len(accounts))
        for idx, acc in enumerate(accounts):
            try:
                login_and_checkin(base, acc["email"], acc["password"], acc["token"])
            except Exception as exc:
                log("账号#%d 失败：%s" % (idx + 1, exc))
                traceback.print_exc()
                push(acc["token"], "签到失败：%s" % exc)
                failures.append(str(exc))
            time.sleep(2)
    else:
        log("错误：既没有配置 COOKIE，也没有配置 INFO")
        return 2

    if failures:
        log("共 %d 项失败" % len(failures))
        return 1
    log("全部签到完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
