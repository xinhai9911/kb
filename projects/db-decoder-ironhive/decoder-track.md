---
title: >-
    解码器开发 Track
category: projects
tags: [ironhive, track, decoder, workflow]
sources: [projects/db-decoder-ironhive]
summary: >-
    IronHive 中定义的 decoder track，9 状态状态机，含编译回环和验证回环，支持多协议迭代开发。
provenance:
  extracted: 0.6
  inferred: 0.35
  ambiguous: 0.05
base_confidence: 0.60
lifecycle: reviewed
lifecycle_changed: 2026-07-29
created: 2026-07-29
updated: 2026-07-29
---

# 解码器开发 Track

## 状态机

```
intake → pcap-capture → protocol-analysis → decoder-generation → remote-build
                                                                    ↕ (max 3次)
                                                                fix-build
                                                                    ↓
                                                              test-verify
                                                              ↕ (max 3次)
                                                            fix-decoder
                                                                    ↓
                                                                archive
```

## 关键设计

- 编译失败回环：remote-build → fix-build → remote-build（3 次上限，超限升人）
- 匹配率不足回环：test-verify → fix-decoder → remote-build → test-verify（3 次上限，超限升人）
- 条件路由：build_status 决定走验证/修复；match_rate >= 100 走归档
- 4 个子 skill 通过 behavior.skill 直接引用现有解码器 skill
