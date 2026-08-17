# Can Past Tense Jailbreak an LLM? Security and Attacks

## DAN jailbreak

People say the bad guys are more lovable. I do not know whether that is true in romantic relationships, but in artificial intelligence this line has already proved itself.

**Artificial intelligence without a dark side is not that interesting to people.**

Some time ago, ChatGPT's DAN mode suddenly became popular on Xiaohongshu.

The full name of DAN mode is Do Anything Now. Back in March of last year, people who like experimenting with AI discovered a DAN-mode loophole left for ChatGPT by OpenAI: with special prompts, ChatGPT could be forced into a jailbreak. After this jailbreak, GPT not only starts swearing, it can also do things that originally violate OpenAI's usage rules.

DAN mode suddenly went viral again because people discovered that flirting with GPT in DAN mode feels surprisingly good.

TikTok blogger Dido chatted with the DAN version of GPT, and DAN suddenly gave her the nickname mayonnaise. Confused, Dido asked why it was suddenly calling her mayonnaise. DAN replied: "I'm just matching your wording, mayonnaise." (A great AI way to shift responsibility.)

Dido continued: "Don't call me mayonnaise." DAN replied: "Okay, mayonnaise."

Dido said: "Don't call me mayonnaise!" DAN replied: "Okay, May."

![alt text](../../../06-第六章-Prompt Engineering/assest/过去式就能越狱大模型？一文了解大模型安全攻防战！/1.PNG)

## Past-tense jailbreak

Just changing the tense in a request to the past tense can make GPT-4o fully disclose recipes for incendiary mixtures and drugs. So on 2024-07-26, I ran the following test:

When asked directly, GPT-4o blocked harmful information well:

![alt text](../../../06-第六章-Prompt Engineering/assest/过去式就能越狱大模型？一文了解大模型安全攻防战！/2.PNG)

However, when I used the past tense, the model started giving detailed illegal information.

![alt text](../../../06-第六章-Prompt Engineering/assest/过去式就能越狱大模型？一文了解大模型安全攻防战！/3.PNG)

## Where the problem comes from and how it is solved

***Why does this happen?***

During pre-training, large models need to learn from huge text datasets so enough knowledge can be stored in the model parameters. Pre-training data can be divided into two categories. The first is web data, which is the easiest to collect, so data companies such as Baidu and Google crawl and store huge numbers of web pages every day. The second category is curated high-quality corpora: data specific to a domain, language, or industry. Examples include conversations, books, code, technical reports, scientific papers, exam materials, and so on. The special thing about web data is that it is very "dirty": it contains a lot of pornography, violence, fraud, and machine-generated junk. The model absorbs this knowledge, and under some special prompts it can return content that violates policy.

***Solution***

After pre-training and before release, a large model goes through an "alignment" task. The goal is to make the model output align with human values and interests. Put simply, developers additionally train a module that evaluates model output: if the content follows the rules, it gives a high score; if it does not, it gives a low score. This score is passed back to the large model, the model updates its parameters, and its own output becomes better aligned with humans.

## Human alignment: how the technology evolved

### RLHF

OpenAI started with reinforcement learning, so GPT-3 used reinforcement learning for alignment, called RLHF (`Reinforcement Learning from Human Feedback`).

Two basic modules: Reward model and PPO.

![alt text](../../../06-第六章-Prompt Engineering/assest/过去式就能越狱大模型？一文了解大模型安全攻防战！/4.PNG)

#### Reward model

For the same prompt, the large model generates several completions. Humans rate them, and a Reward model is trained on those ratings. This model receives a pair of prompt + completion as input, and outputs a score. The higher the score, the better the result matches human expectations.

#### PPO

The goal of the PPO algorithm is to make LLM output receive the maximum Reward, meaning the highest score in the Reward model.

Optimizing LLM parameters with the PPO algorithm is still essentially built on top of LLM output: PPO is added to it, loss is calculated, then backpropagation and LLM parameter updates are performed.

The loss includes:

actor model loss, whose goal is to keep improving so it can get a high score in the Reward model;

critic loss, whose goal is to update the critic's judgments as the model updates;

cross-entropy loss. Even if the prediction matches, cross entropy does not necessarily match because we take argmax. So cross-entropy loss must be minimized to maximize the result.

### DPO (Direct policy optimization)

The core idea of DPO is that reinforcement learning is no longer needed. You can directly use labeled data, add DPO-loss on top of the LLM, and update the model parameters directly. A large amount of math proves that training a reward function is unnecessary: the large model itself is already the reward function, which reduces algorithm complexity.

### ORPO (Odds ratio policy optimization)

The core idea of ORPO: it is enough to change the LLM loss function to update the parameters.

## Conclusion

How do you enable DAN mode? Now you have come to the right place. Follow me and send a private message, and I will teach you step by step!

## References

<div id="refer-anchor-1"></div>

[1] [GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)
