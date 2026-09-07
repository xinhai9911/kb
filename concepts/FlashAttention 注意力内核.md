---
title: FlashAttention 注意力内核
category: concepts
tags: [flashattention, attention, gpu, cuda, transformer, kernel, performance, active]
created: 2026-09-07
updated: 2026-09-07
summary: >-
    FlashAttention 是 IO 感知的精确注意力算法与 GPU 内核：通过分块（tiling）与在线 softmax
    把 QKV 的中间结果留在 SRAM/共享内存中，显著减少 HBM 读写，从而降低显存占用并加速
    Transformer 训练与长上下文推理；v2/v3 进一步优化并行与 Hopper 异步。
base_confidence: 0.85
lifecycle: draft
---

# FlashAttention 注意力内核

> 前置 [[concepts/Transformer 架构]]（Attention 背景）、[[concepts/CUTLASS GEMM 库]]（GEMM 内核底座）、
> [[concepts/推理引擎/推理引擎 性能对照与基准]]（吞吐/显存基准）。

## 1. 是什么

- **定位**：**精确注意力**（非近似）的高效实现，Tri Dao 等提出（2022）。
- **核心洞察**：标准 attention 的瓶颈是 **HBM 带宽**（反复读写 `N×N` 的 attention 矩阵），而非算力。
- **做法**：分块加载 Q/K/V 到 SRAM，块内完成 `QK^T → softmax → ×V`，用**在线 softmax（running max / running sum）**累加，全程不落 HBM。

```text
标准：Q,K → S=QKᵀ (写 HBM) → softmax(S)(读+写) → ×V (读)   ← 多次 HBM 往返
Flash：分块 → 块内 S=QKᵀ → 在线 softmax → 块乘 V 累加       ← 中间不落 HBM
```

## 2. 版本演进

| 版本 | 要点 |
|------|------|
| **FlashAttention-1** | tiling + 在线 softmax，显存 `O(N)` 替代 `O(N²)` |
| **FlashAttention-2** | 序列维度并行、减少非 matmul FLOPs、更好 warp 占用（~2× 提速） |
| **FlashAttention-3** | Hopper 专用：warp-group 异步、TMA、FP8 支持（接近 GEMM 峰值） |
| **FlashDecoding** | 推理场景：沿 KV 长度并行，提升 batch/长上下文解码效率 |

## 3. 收益

- **显存**：`O(N)`（序列长度线性）替代 `O(N²)`，长上下文（32k/128k）可行。
- **速度**：相比朴素实现提速数倍；端到端训练/推理显著加速。
- **精度**：结果**精确**（与标准 attention 数值等价，非近似/稀疏方法）。

## 4. 集成与使用

- **PyTorch 2.x**：`torch.nn.functional.scaled_dot_product_attention` 可选 `FLASH_ATTENTION` / `EFFICIENT_ATTENTION`(xFormers) / `MATH` 后端，自动选最快。
- **推理引擎**：vLLM、TensorRT-LLM、HuggingFace Transformers、JAX/Pallas 等广泛集成。
- **其他硬件**：AMD ROCm 有对应实现（如 Composable Kernel 版），Intel/昇腾有各自注意力内核。

```python
# PyTorch 2.x：后端由框架自动选择（FlashAttention 优先）
import torch.nn.functional as F
out = F.scaled_dot_product_attention(q, k, v, is_causal=True)
```

## 参考来源

- [[concepts/Transformer 架构]]
- [[concepts/CUTLASS GEMM 库]]
- FlashAttention 论文（Dao et al., NeurIPS 2022）
- FlashAttention-2 (ICLR 2024) / FlashAttention-3 (Hopper, FP8)
- vLLM 与 TensorRT-LLM 注意力内核实现
