# [Classic LLM Papers] 2024: Open Models Recalculate the Economics of Training and Inference

If the keyword of 2023 was "open-source models are catching up", then 2024 answered another question: once they have caught up, what should move models forward next?

The changes this year were not only about a model getting a higher score. More importantly, researchers started counting training cost, inference cost, context length, alignment data, and deployment efficiency very seriously. MoE became a main line again, long context moved from selling point to baseline ability, preference optimization became lighter, and open models stopped merely repeating the closed-source route. They started offering their own engineering answers.

Compressed into a few lines, 2024 looked like this: Mixtral and DeepSeek brought MoE efficiency to the foreground; Llama 3 and Gemma continued proving that high-quality dense models were still very viable; KTO, ORPO, and SimPO pushed alignment further toward lightweight methods. ChatGLM and DeepSeek also showed that Chinese-language and local scenarios were no longer simply following others, but making their own tradeoffs in long context, tool calling, and training efficiency.

## KTO

When KTO appeared in February 2024, DPO was already familiar to everyone. DPO's value was that it removed the heaviest reinforcement learning step from RLHF and made preference optimization more direct. But it still depends on paired preference data: for the same input, someone has to compare which answer is better.

KTO works exactly on this data threshold. It does not require pairwise comparison. It only needs a binary signal: this output is desirable or undesirable. In real products, this feedback is often easier to get. User likes and dislikes, moderation pass or rejection, and similar signals are much more common than carefully built preference pairs.

The paper's theoretical framing relies on Kahneman and Tversky's prospect theory. The authors propose Human-Aware Losses, or HALOs, to explain why methods such as DPO and PPO-Clip work: their loss functions implicitly contain reference dependence and loss aversion from human judgment. KTO goes further and writes this human-perceived utility directly into the alignment loss.

The meaning of KTO is not that it proves it is always better than DPO. The paper is careful to say that no universally superior alignment loss function exists. The truly important point is different: it weakens the assumption that preference data must be paired comparisons. For many real products, the simpler the feedback form, the easier alignment is to scale.

## Mixtral 8x7B

In early 2024, Mistral AI released Mixtral 8x7B. It made MoE feel concrete and convincing again.

Mixtral's key design is sparse mixture of experts. In each layer, the model has 8 experts, but each token chooses only 2 experts through a router. The total parameter count is about 47B, but one token effectively activates only about 13B parameters. The problem this solves is direct: can we give the model large capacity without making every inference request pay the full compute cost of a large dense model?

This idea was not born in 2024. GShard in 2020, then Switch Transformer and GLaM in 2021, had already discussed the MoE route in detail. Mixtral's value is that it put the idea into an open, usable, and very strong model. It supports 32K context, performs well on mathematics, code, and multilingual tasks, and the instruction version also went through SFT and DPO, making its dialogue ability competitive.

It also reminds us that MoE is not really about experts dividing tasks like people. Routing analysis in the paper shows that expert choice captures syntactic and structural features more than simply separating topics. The real value of MoE remains the new balance between parameter capacity and computation cost.

## ORPO

In March 2024, ORPO continued the line of making alignment lighter. Compared with DPO, ORPO is more radical because it builds preference optimization directly into SFT.

Traditional SFT has an easy-to-miss problem: it raises the probability of training answers, but does not explicitly penalize bad answers. Preference data already has chosen and rejected responses, but ordinary SFT often does not use the rejected information fully. ORPO adds an odds ratio loss to the SFT negative log-likelihood loss, directly increasing the gap between the preferred response and the rejected response.

The benefit is process simplicity. It does not require a separate reference model and does not require a multi-stage pipeline of SFT first, then DPO. Domain adaptation and preference discrimination happen in one training stage. For resource-constrained teams, this is a practical simplification.

ORPO does not solve all alignment problems at once. It still assumes good enough preference data, and hyperparameters need careful tuning. But in the context of 2024 methods, ORPO is very representative: the focus moved from a more complete RLHF pipeline to cheaper, stabler, and more reproducible alignment schemes.

## Gemma 1

In March 2024, Google released Gemma 1. Its positioning was clear: not to build the largest model, but to distill research and technology from the Gemini series into lightweight models that fit the open community better.

Gemma 1 offered 2B and 7B sizes, including pretrained and instruction-tuned versions. Architecturally, it did not chase strange tricks. It followed the Transformer decoder line with mature choices such as RoPE and GeGLU. The data and safety process deserve more attention. The 2B version was trained on about 2T tokens, the 7B version on about 6T tokens. The data mainly included English web documents, mathematics, and code, with strict filtering, decontamination, and safety evaluation.

Its significance is that it pushed the idea that small models also deserve serious treatment. In 2023, Mistral 7B had already shown that a 7B model could be strong. Gemma 1 showed that large labs were also valuing practical-size models again. Not every scenario needs 70B or 400B. Often, low-cost stable deployment, fine-tuning convenience, and a friendly license matter more.

Gemma 1's limits were clear too. It mostly relied on English data and was not designed specifically for multilingual capability. Its size also means it cannot directly compete with the strongest closed models on complex reasoning. But it laid the foundation for Gemma 2: open models are not only about publishing weights, but about serious training, evaluation, and safe release.

## DeepSeek-V2

In May 2024, DeepSeek-V2 became one of the year's works that deserves separate attention. It did not tell its story only through parameter scale. It gave clear answers at the architecture and cost levels.

DeepSeek-V2 is an MoE model with 236B total parameters, while each token activates only 21B parameters. It supports 128K context. The two key designs are MLA and DeepSeekMoE. MLA, multi-head latent attention, uses low-rank joint compression for keys and values to reduce KV Cache. During inference, the model no longer caches full key and value tensors. It stores compressed latent vectors instead, which greatly reduces KV Cache.

This matters a lot. When long context is actually deployed, the bottleneck is often not whether the model understands long text, but whether KV Cache eats all GPU memory. MLA directly addresses that, making 128K context closer to a service capability rather than just a marketing number.

DeepSeekMoE solves another cost problem. Through fine-grained expert segmentation and shared expert isolation, the model keeps capability while lowering training cost. The paper's conclusion is direct: compared with DeepSeek 67B, DeepSeek-V2 significantly improves maximum generation throughput and lowers training cost.

DeepSeek-V2's influence is not only that one model became stronger. It clearly states the focus of open model competition in 2024: capability still matters, of course, but inference efficiency, training economics, and long-context cost matter just as much.

## SimPO

In May 2024, SimPO simplified preference optimization another step. Its starting point is a subtle but practical DPO problem: reward design during training does not fully match the metric the model actually uses to choose output at inference time.

DPO's implicit reward is built from the likelihood ratio between the current policy model and a reference model. SimPO directly uses length-normalized average log probability as the reward, making the optimization objective closer to how the model ranks candidate sequences during generation. The change looks small, but it addresses a common problem: to increase reward, the model can drift toward longer answers that are not necessarily better.

Another important simplification: SimPO does not need a reference model. That means one fewer model has to be loaded during training, reducing memory and compute cost. It also introduces a target reward margin, so the winning and losing responses are separated by at least some distance rather than only weakly distinguished.

If we look at KTO, ORPO, and SimPO together, 2024 alignment methods have a clear direction: the full RLHF pipeline is no longer treated as the only correct route, and DPO is not treated as the final stop. Researchers started breaking alignment into concrete engineering problems: data shape, training stage, reference model, and inference consistency.

## ChatGLM

In June 2024, the paper on the ChatGLM series systematically reviewed the path from GLM-130B to GLM-4 All Tools. This work is different from a paper about one new model. It is more of a summary of how the Chinese large model line was built.

One feature of early ChatGLM was Prefix Decoder-only architecture. The input prefix uses bidirectional attention to better understand the user question, while the generation part uses unidirectional attention to preserve autoregressive generation. This is a compromise between GPT-style generation and BERT-style understanding.

Later versions returned to standard Decoder-only architecture. That is interesting because it shows that architectural choice does not always benefit from more complexity. As data and scale grew, unified Causal Attention was enough for instruction understanding and generation, while training efficiency, engineering implementation, and ecosystem compatibility improved.

The GLM-4 series is not only about Chinese capability. The paper mentions GLM-4 All Tools, which can call a browser, Python interpreter, and other tools. This shows the movement from answering questions toward completing tasks. It is the same line as the industry's broader 2024 interest in agents and tool use. For Chinese scenarios, ChatGLM's value is that it connects local language, long context, tool calling, and engineering iteration.

## Llama 3

In July 2024, Meta released Llama 3.1, and the technical report described the Llama 3 Herd of Models. Unlike the MoE route, Llama 3 continues to rely on dense Transformer and seriously increases scale, data, and post-training.

The flagship Llama 3 version reaches 405B parameters, supports 128K context, and is trained on about 15T multilingual tokens. This data volume is more than 8 times Llama 2. Meta also emphasizes not only data size, but data quality: cleaning, deduplication, quality classification, code and reasoning data pipelines, multilingual identification, and upsampling high-quality code and mathematics data during the annealing stage.

Post-training is also telling. Through multiple rounds of SFT, rejection sampling, and DPO, Llama 3 gradually introduces instruction following, tool use, and safety alignment. This is not a story of winning only through pretraining scale. It is the result of increasing data, compute, training stability, post-training, and evaluation together.

Llama 3's meaning is that it proved the dense model route was still very strong in 2024. MoE is attractive, but dense models also have value in stability, ecosystem compatibility, and controllable inference behavior. For the open-source ecosystem, Llama 3 became a new baseline. If someone says their model is strong, they often have to compare with it.

## Gemma 2

In July 2024, Google released Gemma 2. Compared with Gemma 1, the focus became clearer: keep squeezing performance out of practical sizes.

Gemma 2 offers 2B, 9B, and 27B sizes. The architectural changes are not complex, but closely tied to efficiency. For example, it alternates local sliding window attention and global attention: some layers model local information, while others preserve long-range interaction. The 9B and 27B models also use GQA to speed up inference and reduce KV Cache pressure.

Knowledge distillation is especially important. Gemma 2 2B and 9B are not trained only through traditional next-token prediction. They learn from stronger teacher models through output distributions. This fits the 2024 small-model trend: a small model is not just a smaller copy of a large model. Its abilities have to be compressed into a deployable size through distillation, data filtering, and architecture tradeoffs.

Gemma 2 27B also emphasizes efficient operation on one TPU host or modern NVIDIA GPU. The appearance of such wording shows that open models in 2024 were no longer talking only about benchmarks, but about deployment boundaries. If a model is strong enough but too hard to run, its value drops.

## DeepSeek-V3

At the end of 2024, DeepSeek-V3 brought together many lines of the year: MoE, long context, training efficiency, FP8, communication optimization, and the possibility that open models could approach the closed-source frontier.

DeepSeek-V3 has 671B total parameters, activates 37B parameters per token, and is pretrained on 14.8T high-quality tokens. Architecturally, it continues MLA and DeepSeekMoE, while also introducing auxiliary-loss-free load balancing and a multi-token prediction objective. The first mechanism uses dynamic bias to regulate expert load and avoid traditional auxiliary loss interfering with the main task. The second asks the model to predict multiple future tokens from one hidden state, increasing training signal and helping speculative decoding during inference.

The training system is especially notable. DeepSeek-V3 uses FP8 mixed precision training, DualPipe bidirectional pipeline parallelism, and overlap of computation and communication, completing training on 2048 H800 GPUs. The paper estimates training cost at about 2.788 million H800 GPU hours and total cost at about 5.576 million USD. These numbers matter not because they are cheap for everyone, but because they make the question of lowering frontier model training cost very concrete.

DeepSeek-V3 has limits too. A cost estimate in a technical report does not mean any team can reproduce the same efficiency. The engineering stack, cluster scheduling, communication kernels, and data quality are very hard to reproduce. But it clearly marks a point in 2024: open models are not only chasing scores. They are starting to show solid results in training systems and cost structure.

## What Changed This Year

Large model progress in 2024 can be described through four changes.

First, MoE moved from interesting research back to something worth deploying. Mixtral showed the open community the practical effect of sparse activation models, while DeepSeek-V2 and DeepSeek-V3 combined MoE, MLA, load balancing, and communication optimization into a fuller training and inference scheme.

Second, long context entered engineering details. 128K is not only about stretching positional encoding. It also means solving KV Cache, throughput, and memory cost. DeepSeek's MLA, Llama 3's continual pretraining, and ChatGLM's long-context practice show that this is no longer a single trick.

Third, alignment methods kept getting lighter. KTO weakened the requirement for paired preference data, ORPO built preference optimization into SFT, and SimPO removed the reference model while realigning the training metric with inference. Together, they point to a trend: alignment increasingly looks like an engineering optimization problem, not only an expensive full pipeline.

Fourth, the competition criteria for open models changed. In 2023, people still asked whether open models could catch up to the closed-source experience. In 2024, they started asking whether models could train cheaper, run inference faster, support long context, preserve ability in small models, do tool calling well, and release safely.

So the real legacy of 2024 is not only the names Llama 3, Gemma, and DeepSeek. It is a more practical judgment: large models must keep becoming stronger, of course, but the next phase will likely belong to whoever handles capability, cost, and deployability at the same time.

## References

1. Ethayarajh, K., et al. (2024-02-02). KTO: Model Alignment as Prospect Theoretic Optimization. https://arxiv.org/abs/2402.01306
2. Jiang, A. Q., et al. (2024-02-08). Mixtral of Experts. https://arxiv.org/abs/2401.04088
3. Hong, J., et al. (2024-03-12). ORPO: Monolithic Preference Optimization without Reference Model. https://arxiv.org/abs/2403.07691
4. Gemma Team. (2024-03-13). Gemma: Open Models Based on Gemini Research and Technology. https://arxiv.org/abs/2403.08295
5. DeepSeek-AI. (2024-05-07). DeepSeek-V2: A Strong, Economical, and Efficient Mixture-of-Experts Language Model. https://arxiv.org/abs/2405.04434
6. Meng, Y., et al. (2024-05-23). SimPO: Simple Preference Optimization with a Reference-Free Reward. https://arxiv.org/abs/2405.14734
7. GLM Team. (2024-06-18). ChatGLM: A Family of Large Language Models from GLM-130B to GLM-4 All Tools. https://arxiv.org/abs/2406.12793
8. Dubey, A., et al. (2024-07-23). The Llama 3 Herd of Models. https://arxiv.org/abs/2407.21783
9. Gemma Team. (2024-07-31). Gemma 2: Improving Open Language Models at a Practical Size. https://arxiv.org/abs/2408.00118
10. DeepSeek-AI. (2024-12-27). DeepSeek-V3 Technical Report. https://arxiv.org/abs/2412.19437
