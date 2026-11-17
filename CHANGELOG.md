# Changelog

## 1.6.10-custom

- 修复自定义中转站翻译请求因 response_format schema 被拒绝的问题。
- 调整 AI Bar 输入框的单行和多行高度行为。
- 增加显式上下文压缩预算：256k token 触发、32k token 历史目标。
- 让模型 metadata 中更小的 context/input 限制优先生效。
