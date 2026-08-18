---
aliases: ["neural-network-optimizers-part-5-rprop"]
---

Understanding neural network optimizers in 3 minutes a day, part 5: Rprop

Resilient Backpropagation was proposed by Martin Riedmiller and Hermann Braun in 1993. Rprop computes updates using only the sign of the gradient, not its magnitude, and dynamically adjusts the step size independently for each weight.

## 1. The Appearance of Rprop

Rprop (Resilient Backpropagation) was proposed by Martin Riedmiller and Hermann Braun in 1993. It is described in detail in "A Direct Adaptive Method for Faster Backpropagation Learning: The RPROP Algorithm" [1](#refer-anchor-5), published at an IEEE international conference in 1993. Rprop computes updates using only the sign of the gradient, not its magnitude, and dynamically adjusts the step size independently for each weight. This approach overcomes some built-in weaknesses of traditional gradient descent, and through local adaptation to the behavior of the error function, it makes training more efficient and easier to understand.

## 2. How Rprop Works

1. **Initialization**: for each weight $w_i$, initialize an individual step size $\Delta_i$. Usually the initial value of $\Delta_i$ is set to a small positive number.

2. **Update rules**:
   - If $g_t$ (the current gradient) and $ g_{t-1} $ (the gradient from the previous step) have the same sign, increase the step size:
     $\Delta_i = \min(\Delta_{\text{max}}, \eta_i + \Delta_i)$
   - If $ g_t $ and $ g_{t-1} $ have different signs, or $ g_t $ equals zero, decrease the step size:
     $\Delta_i = \max(\Delta_{\text{min}}, \eta_i - \Delta_i)$
   - If both $ g_t $ and $ g_{t-1} $ are zero, reset the step size:
     $\Delta_i = \Delta_{\text{init}}$

3. **Weight update**:
   $w_i = w_i - \Delta_i \cdot \text{sign}(g_t)$
   where $g_t$ is the current gradient, and $\text{sign}(g_t)$ is the sign function of the gradient.

### Parameters:

- $\Delta_{\text{max}}$: maximum change size, preventing overly large steps;
- $\Delta_{\text{min}}$: minimum change size, preventing overly small steps;
- $\Delta_{\text{init}}$: initial change size.

With this mechanism, Rprop can adaptively tune the step size for each weight, making training more flexible and efficient. It is especially suitable for tasks where the update size needs fine control so the algorithm does not get stuck in a local minimum.

## 3. Main Features of Rprop

1. **Adaptive step size**: Rprop sets a separate step size for each weight instead of using one global learning rate. This means each weight's step can be adjusted based on its gradient history.

2. **Fast convergence**: because it adaptively adjusts the step size, Rprop usually converges faster.

3. **Robustness**: Rprop is not very sensitive to the initial step size, which gives it good robustness across different tasks.

![alt text](../../../01-第一章-预训练/assest/神经网络的优化器（五）Rprop/0.png)

## References

<div id="refer-anchor-5"></div>

[1] [A Direct Adaptive Method for Faster Backpropagation Learning: The RPROP Algorithm](https://citeseerx.ist.psu.edu/viewdoc/summary?doi=10.1.1.21.1417)

## Author's GitHub and WeChat

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

The repository has the original Markdown files, and it is fully open source. Stars and forks are very welcome.


---

## 📚 相关概念

[[concepts/Transformer 架构|Transformer 架构]] | [[concepts/分词器 LLM|分词器 LLM]] | [[concepts/LLM 训练 流水线|LLM 训练 流水线]] | [[concepts/RLHF DPO 对齐|RLHF DPO 对齐]] | [[concepts/LoRA PEFT 微调|LoRA PEFT 微调]] | [[concepts/多模态 LLM|多模态 LLM]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[entities/Hugging Face|Hugging Face]] | [[entities/DeepSeek|DeepSeek]] | [[entities/mindspore Transformer|mindspore Transformer]] | [[sources/Vaswani 2017 Attention|Vaswani 2017 Attention]] | [[sources/LLM 训练 流水线 指南|LLM 训练 流水线 指南]] | [[sources/DeepSeek 4 技术|DeepSeek 4 技术]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：预训练
