---
aliases: ["why-large-language-models-use-swiglu-as-activation"]
---

Why do large language models use SwiGLU as their activation function?

Activation functions are a key part of neural network design. They introduce nonlinearity and control gradient flow, which allows the network to learn and handle complex tasks. In large language models, using SwiGLU as the activation function has become a clear trend. So why do LLMs use SwiGLU?

**Reading tip**: you can look only at the formulas and code if you just want to understand the mathematical expression and implementation.

## 1. The Earliest Activation Function: Sigmoid

In biology, neuron activation is usually nonlinear and threshold-like: a neuron activates and produces an output only after receiving a strong enough input signal. In artificial neural networks, although sigmoid is much less common in deep learning today, it was once one of the most popular activation functions. The S-shaped curve of sigmoid is somewhat similar to biological neuron activation: it has an obvious threshold, and when the input passes that threshold, the output rises sharply.

![alt text](<../../../01-第一章-预训练/assest/为什么大型语言模型都在使用 SwiGLU 作为激活函数？/0.png>)

Sigmoid is a widely used activation function in statistics and machine learning, especially in early neural network models. It has an S shape and squeezes the input into the range from 0 to 1. So it is especially useful in cases where the output should be interpreted as a probability, or when it is used as the output-layer activation in binary classification.

The mathematical expression of Sigmoid:

$$ \sigma(x) = \frac{1}{1 + e^{-x}} $$

where $e$ is the base of the natural logarithm, about 2.71828, and $x$ is the input value.

![alt text](<../../../01-第一章-预训练/assest/为什么大型语言模型都在使用 SwiGLU 作为激活函数？/1.png>)

### Properties of Sigmoid include:

1. **Output range**: the output is always in (0, 1), which makes sigmoid very useful for probability output and binary classification.

2. **Smoothness and continuity**: sigmoid is smooth and continuous across its whole domain, which helps with gradient computation during optimization.

3. **Central symmetry**: sigmoid is symmetric around the line $y = x$, so it can handle positive and negative input values.

4. **Gradient problem**: when input $x$ is very large or very small, the sigmoid gradient is close to 0. This can cause vanishing gradients, making it hard for gradients to propagate through deep neural network layers.

5. **Not zero-centered**: sigmoid output is not centered around 0, so the network may need more time and resources to adjust weights during optimization.

### Applications of Sigmoid:

- **Binary classification**: in the output layer of a binary classification task, sigmoid can turn the model output into a probability of belonging to a class.
- **Logistic regression**: in logistic regression, sigmoid converts the output of linear regression into a probability prediction.
- **Hidden layers**: although modern deep learning models use it less often in hidden layers, sigmoid can still act as a hidden-layer activation in some cases.

### Limitations:

- **Vanishing gradients**: in deep networks, when input values have large magnitude, the sigmoid gradient is close to 0. This easily causes vanishing gradients and blocks training of deep networks.
- **Compute cost**: compared with some activation functions such as ReLU, sigmoid is more expensive because it includes an exponential.

Because of these limitations, sigmoid has gradually been replaced in modern deep learning by other activation functions, such as ReLU and its variants, especially in hidden layers. Still, in scenarios where the output needs to be a probability prediction, sigmoid remains important.

```python
import numpy as np

def sigmoid(x):
    """Sigmoid activation function.

    Args:
        x: Input value.

    Returns:
        Value after sigmoid activation.
    """
    return 1 / (1 + np.exp(-x))
```

## 2. The Hero of Deep Learning: ReLU

ReLU (Rectified Linear Unit) is a simple and effective activation function widely used in deep learning. ReLU is defined as:

$$ f(x) = max(0, x) $$

This means that when input $x$ is greater than 0, the output equals the input. When input $x$ is less than or equal to 0, the output is 0. The ReLU graph is a broken line: for positive $x$, the slope is 1; for negative $x$, the slope is 0.

![alt text](<../../../01-第一章-预训练/assest/为什么大型语言模型都在使用 SwiGLU 作为激活函数？/2.png>)

Properties of ReLU include:

- Sparse activation: because ReLU outputs 0 on the negative half-axis, roughly half the neurons, assuming zero-mean input, are inactive at any moment. This sparsity helps reduce computation and prevent overfitting.

- Nonlinearity: ReLU introduces nonlinearity, so neural networks can learn and model complex functions.

- High compute efficiency: because ReLU has a simple mathematical form, it is very fast to compute, which helps speed up neural network training and inference.

- Mitigating vanishing gradients: compared with sigmoid or tanh, ReLU has a constant gradient of 1 on the positive side. This helps ease the vanishing gradient problem and makes deep-network training more practical.

```python
import numpy as np

def relu(x):
    """ReLU activation function.

    Args:
        x: Input value.

    Returns:
        Value after ReLU activation.
    """
    return np.maximum(0, x)
```

## 3. The Rise of Variants: ReLU-Like Activation Functions

Beyond ReLU, there are many similar activation functions. They improve ReLU to solve some of its built-in problems. These ReLU-like activation functions include:

- **Leaky ReLU**: an improvement over ReLU. When the input is negative, Leaky ReLU introduces a small slope instead of immediately outputting 0. This helps solve ReLU's zero-output problem on the negative side.

- **Parametric ReLU (PReLU)**: an extension of Leaky ReLU that introduces a learnable parameter to control the slope on the negative side. This lets the neural network adaptively learn the activation behavior for negative inputs.

- **Exponential Linear Unit (ELU)**: a ReLU-like activation that introduces an exponential term on the negative side, making the output smoother there. In some cases, ELU can perform better.

- **Scaled Exponential Linear Unit (SELU)**: an ELU variant with scaling parameters. Under certain conditions, SELU can preserve the mean and variance of the input, which helps stabilize training.

- **GELU**: an activation function based on the Gaussian Error Linear Unit. In some cases, it can perform better. Its mathematical form is a smooth function involving the error function.

In practice, these ReLU-like activation functions are widely used. To some extent, they improve ReLU, and different variants behave differently in different scenarios. Choosing the right activation depends on the task and model architecture.

## 4. The Best Activation Function in Experiments: Swish

Swish is an activation function proposed by Google Brain. Its mathematical expression is:

$$ f(x) = x \cdot \sigma(x) $$

where $\sigma(x)$ is sigmoid.

![alt text](<../../../01-第一章-预训练/assest/为什么大型语言模型都在使用 SwiGLU 作为激活函数？/3.png>)

The name Swish may come from the fact that its shape looks like a fish tail and suggests a smooth, flowing motion, which matches the meaning of the word "swish."

Properties of Swish include:

- **Nonlinearity**: Swish introduces nonlinearity, so neural networks can learn and model complex functions.
- **Smoothness**: Swish is smooth and continuous across its whole domain, which helps with gradient computation during optimization.
- **Adaptiveness**: the output of Swish depends on the input value, so it can adaptively change the shape of the activation.

In some experiments, Swish performed better than ReLU, especially in certain deep neural networks. But Swish is more expensive to compute because it includes sigmoid. So in practice, the activation function should be chosen based on the task and architecture.

```python
import numpy as np

def swish(x, beta=1.0):
    """Swish activation function.

    Args:
        x: Input value.

    Returns:
        Value after Swish activation.
    """
    return x * sigmoid(beta * x)

def sigmoid(x):
    """Sigmoid function.

    Args:
        x: Input value.

    Returns:
        Output of sigmoid.
    """
    return 1 / (1 + np.exp(-x))
```

## 5. GLU

GLU (Gated Linear Unit) is not quite an activation function. It is a neural network layer. It is a structure where a linear transformation is followed by a gating mechanism. The sigmoid function controls how much information can pass through. GLU combines a Linear Unit with a gating mechanism, allowing the model to learn different input features effectively. The mathematical expression of GLU is:

$$f(X) = (X ∗ W + b) ⊗ σ(X ∗ V + c)$$

where ⊗ denotes element-wise multiplication, $X$ is the input, $W$ and $V$ are weight matrices, and $b$ and $c$ are biases.

Properties of GLU include:

- **Gating mechanism**: GLU introduces a gate and uses sigmoid to control the linear transformation of the input, helping the neural network learn different input features.
- **Nonlinearity**: GLU introduces nonlinearity, so the neural network can learn and model complex functions.
- **Adaptiveness**: GLU output depends on the input value, so it can adaptively change the activation behavior.

PyTorch implementation of GLU:

![alt text](<../../../01-第一章-预训练/assest/为什么大型语言模型都在使用 SwiGLU 作为激活函数？/4.png>)

```python
import numpy as np

def glu(x):
    """GLU activation function.

    Args:
        x: Input array. The last dimension must be even.

    Returns:
        Array after GLU activation.
    """
    assert x.shape[-1] % 2 == 0, "The last dimension of the input array must be even."
    half_dim = x.shape[-1] // 2
    return x[..., :half_dim] * sigmoid(x[..., half_dim:])

def sigmoid(x):
    """Sigmoid function.

    Args:
        x: Input value.

    Returns:
        Output of sigmoid.
    """
    return 1 / (1 + np.exp(-x))
```

## 6. Practice Reveals the Truth: SwiGLU

Now we finally reach today's main character: SwiGLU. SwiGLU is an activation function that combines Swish and GLU. It brings together the smoothness of Swish and the gating mechanism of GLU, letting the model learn different input features efficiently. The mathematical expression of SwiGLU is:

$$ f(X) = (X ∗ W + b) ⊗ Swish(X ∗ V + c) $$

```python
import numpy as np

def SwiGLU(x):
    """SwiGLU activation function.

    Args:
        x: Input array. The last dimension must be even.

    Returns:
        Array after SwiGLU activation.
    """
    assert x.shape[-1] % 2 == 0, "The last dimension of the input array must be even."
    half_dim = x.shape[-1] // 2
    return x[..., :half_dim] * swish(x[..., half_dim:])

def swish(x, beta=1.0):
    """Swish activation function.

    Args:
        x: Input value.

    Returns:
        Value after Swish activation.
    """
    return x * sigmoid(beta * x)

def sigmoid(x):
    """Sigmoid function.

    Args:
        x: Input value.

    Returns:
        Output of sigmoid.
    """
    return 1 / (1 + np.exp(-x))
```

## Why Use It?

SwiGLU is widely used in large language models because it has advantages in several areas. It combines the properties of Swish and GLU and provides an effective activation mechanism. More specifically:

1. **Nonlinear capacity**: SwiGLU introduces nonlinearity through Swish, allowing the model to learn and represent more complex data patterns.

2. **Gating properties**: the GLU gating mechanism lets the model dynamically adjust information flow, which helps it capture long-range dependencies when processing long sequences.

3. **Gradient stability**: SwiGLU gives a nonzero gradient in the negative-input region, helping reduce vanishing gradients and improving training stability.

4. **Learnable parameters**: SwiGLU parameters can be trained, so the model can dynamically adapt to different tasks and datasets, improving flexibility.

5. **Compute efficiency**: compared with some complex activation functions, SwiGLU keeps strong performance while remaining compute-efficient, which matters a lot for training and inference of large language models.


---

## 📚 相关概念

[[concepts/Transformer 架构|Transformer 架构]] | [[concepts/分词器 LLM|分词器 LLM]] | [[concepts/LLM 训练 流水线|LLM 训练 流水线]] | [[concepts/RLHF DPO 对齐|RLHF DPO 对齐]] | [[concepts/LoRA PEFT 微调|LoRA PEFT 微调]] | [[concepts/多模态 LLM|多模态 LLM]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[entities/Hugging Face|Hugging Face]] | [[entities/DeepSeek|DeepSeek]] | [[entities/mindspore Transformer|mindspore Transformer]] | [[sources/Vaswani 2017 Attention|Vaswani 2017 Attention]] | [[sources/LLM 训练 流水线 指南|LLM 训练 流水线 指南]] | [[sources/DeepSeek 4 技术|DeepSeek 4 技术]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：预训练
