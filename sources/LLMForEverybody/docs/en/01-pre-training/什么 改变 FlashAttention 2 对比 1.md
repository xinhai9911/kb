---
aliases: ["what-changed-in-flashattention-v2-vs-v1"]
---

FlashAttention V2 reduces computation and memory access while keeping the accuracy and efficiency of the algorithm, which makes Attention faster. With these optimizations, forward propagation on an A100 GPU is about 2 times faster in V2, reaching roughly 50% to 73% of the theoretical compute peak.

## 1. FlashAttention v1

> $Attention(Q, K, V) = softmax(\frac{QK^T}{\sqrt{d_k}})V$

FlashAttention does not materialize the X and A matrices in global memory. Instead, it fuses the whole computation from the formula above into one CUDA kernel. To make that work, the algorithm needs to manage on-chip memory carefully, for example through a streaming algorithm, because GPU shared memory (SRAM) is small.

Classic algorithms such as matrix multiplication use tiling so the amount of on-chip memory stays within hardware limits. This works because addition is associative, so full matrix multiplication can be decomposed into a sum of many tiled matrix multiplications.

![alt text](<../../../01-第一章-预训练/assest/FlashAttention v2相比于v1有哪些更新？/0.png>)

## 2. What Changed in FlashAttention v2

![alt text](<../../../01-第一章-预训练/assest/FlashAttention v2相比于v1有哪些更新？/1.png>)

- It reduces the number of non-matmul FLOPs by removing the previous frequent rescale operations. Non-matmul FLOPs are only a small part of total FLOPs, but they take longer because GPUs have specialized hardware for matrix multiplication, with throughput up to 16 times higher than non-matrix operations. So it matters to reduce non-matmul FLOPs and do as many matmul FLOPs as possible.

- It introduces parallelism along the sequence-length dimension. This improves GPU utilization when the input sequence is very long, where batch size is usually small. Even for a single head, the computation can run in parallel across different thread blocks.

- Inside one attention computation block, work is split across different warps in the same thread block, reducing communication and shared-memory reads and writes.

## 3. The First Update in More Detail

The first change is reducing non-matmul FLOPs by removing frequent rescale operations. Again, non-matmul FLOPs are only a small portion of total FLOPs, but they are slower because GPUs have specialized units for matrix multiplication, and those units can have up to 16 times the throughput of non-matrix operations. So FlashAttention V2 tries to reduce non-matmul work and maximize matmul work.

### non-matmul vs. GEMM

***non matrix multiply***

Non-matrix multiplication means operations outside matrix multiplication, such as addition, multiplication, division, and so on. For example, `rescale` uses general GPU hardware: CUDA Cores.

***General Matrix Multiply***

General matrix multiplication is one way to implement matrix multiplication, and it uses specialized GPU hardware: Tensor Cores.

### CUDA Core vs. Tensor Core

Non-matrix operations are slower because the GPU has a specialized compute unit for matrix multiplication, the Tensor Core, whose throughput can be up to 16 times higher than regular non-matrix operations.
The figure below describes the A100. You can see that CUDA Core compute in single precision TF16 is 19.5 TFLOPS, while Tensor Core compute is 312 TFLOPS. That is a 16 times gap.

![alt text](<../../../01-第一章-预训练/assest/FlashAttention v2相比于v1有哪些更新？/3.png>)

### The Rescale Operation

![alt text](<../../../01-第一章-预训练/assest/FlashAttention v2相比于v1有哪些更新？/2.png>)

V2 changes the algorithm by reducing floating-point operations for non-matrix operations while keeping the output unchanged. In the original FlashAttention, meaning V1, every iteration of every block had to run a rescale operation, and that included division.

In V2, the rescale operation is delayed until the end of the loop and runs only once. Each computation can save one division. This adjustment is possible because, at each iteration, it is enough to make sure the numerator is scaled to the correct value and the denominator is computed correctly. This optimization reduces computation and improves efficiency.

## 4. The Second Update in More Detail

The second update introduces parallelism along the sequence-length dimension. This improves GPU utilization when the input sequence is very long, where batch size is usually small. Even for one head, computation can run in parallel across different thread blocks.

### GPU Hardware

- Streaming Processor (SP): the basic compute unit. Since the Fermi architecture, this is usually called a CUDA core.
- Streaming Multiprocessor (SM): one SM contains multiple CUDA cores (SPs). Different GPU architectures have different numbers of CUDA cores per SM. For example, in the Pascal architecture, one SM contains 128 CUDA cores.

### GPU Software

- thread: a parallel CUDA program runs with many threads. A thread is the basic unit of execution.
- warp: one warp usually contains 32 threads. Threads inside one warp can execute the same instruction at the same time, implementing SIMT (single instruction, multiple threads) parallelism. A warp is the smallest scheduling unit on an SM, and one SM can process multiple warps at the same time.
- thread block: one thread block can contain multiple warps. Threads inside one block can synchronize and communicate through shared memory. A thread block is the smallest execution unit on the GPU. Threads in one warp must belong to the same block. If the number of threads in a block is not a multiple of the warp size, the remaining slots in the extra warp become inactive threads. Hardware still pads the warp to full size, so those inactive threads still consume SM resources.

The second major V2 update is parallel computation along the sequence-length dimension. The goal is to improve GPU SM utilization, especially when processing long sequences. In V1, computation was first parallelized across batch and head count, then ran sequentially along the sequence length. So when the sequence length was large, not all available SMs were necessarily used well, because each block processed only one segment of the sequence.

In V2, sequence-length parallelism spreads compute tasks across more blocks and uses GPU resources more fully. More specifically, V2 introduces `num_m_block` and further splits the Q matrix into small blocks along the sequence-length dimension, with each block processed by a separate thread block. That lets each block independently compute its part of the output, reducing dependencies and communication overhead between blocks.

> This is a little like the idea of continuous batching.

## 5. The Third Update in More Detail

![alt text](<../../../01-第一章-预训练/assest/FlashAttention v2相比于v1有哪些更新？/4.png>)

In V2, the loop order changes: Q is moved to the outer loop, while K and V are in the inner loop. Each thread block is responsible for computing part of the output matrix O. This design lets each thread block compute independently, reducing dependencies and communication between thread blocks. In forward propagation, V2 also reduces floating-point operations for non-matrix operations, so it can make better use of specialized GPU compute units such as NVIDIA Tensor Cores and maximize GPU throughput.

In backward propagation, V2 is also optimized. It uses a similar blocking strategy to improve computation and memory access, which raises efficiency and performance. As a result, FlashAttention V2 provides higher parallelism, cuts redundant computation and memory access, and improves overall compute performance.

## References

<div id="refer-anchor-1"></div>

[1] [FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness](https://arxiv.org/abs/2205.14135)

[2] [FlashAttention-2: Faster Attention with Better Parallelism and Work Partitioning](https://arxiv.org/abs/2307.08691)

[3] [Detailed explanation of FlashAttention2, 200% better performance than FlashAttention](https://cloud.tencent.com/developer/article/2353093)

[4] [GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)
