# Zotero AI Bar 1.6.10 custom build

这是基于上游 **Zotero AI Bar 1.6.10** 的个人定制发布包，方便备份、版本管理和分享。

> 上游项目：https://github.com/swcxito/zotero-ai-bar

## 当前改动

- 自定义中转站翻译走普通 JSON 文本流，避免部分中转站拒绝 `response_format` schema。
- AI Bar 输入框单行时保持紧凑，多行时随内容增长，最高 160px，超过后滚动。
- 保留紧凑的用户消息气泡样式。
- 对话上下文默认在估算达到 256,000 token 时压缩，摘要和近期历史目标约 32,000 token。
- 模型自身较小的 context/input 限制优先于本地预算。

## 安装

1. 关闭 Zotero。
2. 将 `zotero-ai-bar-1.6.10-custom.xpi` 拖入 Zotero，或在插件管理器中选择“从文件安装插件”。
3. 重新打开 Zotero。
4. 在插件设置中重新填写你自己的 API 地址、API Key 和模型配置。

不要分享 Zotero profile 下的 `prefs.js`，其中可能包含 API Key。这个发布包不包含该文件。

## 兼容性

- 插件清单要求 Zotero `6.999` 以上、`11.*` 以下，实际可理解为 Zotero 7 至 Zotero 11 系列。
- XPI 本身没有 macOS、Windows 或 Linux 原生二进制，正常安装路径依赖 Zotero 支持的平台。
- 本次实际验证平台是 macOS 上的 Zotero；Windows 和 Linux 预计可通过同一 XPI 安装，但没有在本次发布前实机验证。
- `patches/` 中的迁移脚本是 macOS 本地维护工具，普通用户安装 XPI 不需要运行它们。
- 使用自定义中转站时，中转站需要提供与插件配置相匹配的 OpenAI-compatible 聊天接口；API 地址、Key 和模型名称由使用者自行填写。

## 上下文压缩说明

压缩预算是估算值，不是精确 tokenizer 计数。系统消息和全文模式附带的论文原文会额外占用请求空间；最近的用户轮次会优先保留。

## 复现修改

`patches/` 中保存了本次修改使用的本地迁移脚本。它们默认针对 macOS 上的 Zotero profile 工作，运行前应备份 XPI，并且不要把 profile 配置提交到 GitHub。

## 来源与许可

本包是上游插件的本地修改版。上游代码、商标和许可条款仍归原项目所有；分享前请同时遵守上游仓库的许可证。这里没有重新声明上游许可证。

打包日期：2026-11-17
上游扩展版本：1.6.10
