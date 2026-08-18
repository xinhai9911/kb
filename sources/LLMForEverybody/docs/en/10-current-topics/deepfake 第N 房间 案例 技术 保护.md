---
aliases: ["deepfake-nth-room-case-technology-and-protection"]
---

# The Korean "Nth Room" Case Reappears Through DeepFake: Technology and Protection

## 1. Context

According to `Global Times`, citing Korean media, deepfake crimes against women in South Korea are becoming more common. Such cases appear not only on university campuses: even elementary and secondary schools, the military, and other places have become high-risk areas. On social networks, especially Telegram groups, information about affected schools and victims keeps appearing.

Some men in South Korea often use DeepFake technology to replace the faces of women they know in existing sexualized videos, then distribute these materials on Telegram and harass the victims.

The Korean "Nth Room" case, which once shocked the world, now seems to be constantly "updated" into versions 2.0 and 3.0.

![alt text](<../../../10-第十章-热点/assest/韩国“N 号房”事件因Deep Fake再现，探究背后的技术和应对方法/01.png>)

## 2. What is DeepFake?

Deepfake is a deep-learning-based AI application that can create extremely realistic altered images or videos. Using algorithms such as generative adversarial networks (`GANs`) and Diffusion Models, this technology combines the facial features or other traits of one person with an image or video of another person, creating highly plausible fake content.

The term deepfake was first created by a Reddit user in 2017. Initially, it was used to create fake sexualized videos of celebrities, but as the technology developed, its application areas expanded into entertainment, politics, education, and other fields.

![alt text](<../../../10-第十章-热点/assest/韩国“N 号房”事件因Deep Fake再现，探究背后的技术和应对方法/00.png>)

The technology itself is neutral, but misuse leads to harmful consequences. To counter the harm caused by DeepFake, we first need to understand the technical principles behind it. DeepFake can be implemented in different ways, and Diffusion Model is one popular approach.

## 3. Diffusion Model

Diffusion Model is one of the popular AIGC models of recent times. It is a generative model that can be used to create high-quality images and videos. Its core idea is to add perturbation to image or video pixels, then gradually reduce the perturbation strength to generate a realistic image or video.

Imagine you have a clear family photo, and you want to use a series of strange steps to "hide" the information in that photo, then find it back. This process of "hiding" and "restoring" is the core of diffusion models.

`Forward Diffusion`:

First, you start randomly drawing over the photo. This is like adding noise to the original data. You repeat this again and again, adding more interference each time, until the photo becomes unrecognizable and turns into a chaotic patch of colors and lines.

This process is like gradually adding noise to data until it becomes fully random noise.

`Reverse Diffusion`:

Now you have a completely scribbled-over photo, and the task is to restore the original family photo. You gradually erase the interference, little by little each time, until it all disappears and the family photo becomes clear again. This is like gradually restoring original data from noise.

In diffusion models, this process is implemented through a mathematical and computational model.

The model first learns to generate "interference" (forward process), then learns to erase it (reverse process). The reverse process is performed by training a neural network that predicts how much noise needs to be removed at each step, so that new data similar to the original can eventually be generated.

## How is face swap performed?

How does a Diffusion Model generate a nonexistent photo?

In this model, a description can be added to an image. This description links image and text through embedding. So we can generate the image we want from the description. Because the model has strong generative ability, the result is almost indistinguishable from real.

![alt text](<../../../10-第十章-热点/assest/韩国“N 号房”事件因Deep Fake再现，探究背后的技术和应对方法/12.png>)

For example, we have a photo of an avocado and the text "one avocado" for training the model. Then the model can create a corresponding image from the instruction "generate a photo of an avocado":

![alt text](<../../../10-第十章-热点/assest/韩国“N 号房”事件因Deep Fake再现，探究背后的技术和应对方法/13.png>)

Likewise, we have a photo of an office chair and the text "one office chair" for training the model. Then from the instruction "generate a photo of an office chair", the model can create the corresponding image:

![alt text](<../../../10-第十章-热点/assest/韩国“N 号房”事件因Deep Fake再现，探究背后的技术和应对方法/14.png>)

At this point, the model has learned what an avocado is and what a chair is. If you give it the instruction "generate an avocado chair", it gains creative ability.

![alt text](<../../../10-第十章-热点/assest/韩国“N 号房”事件因Deep Fake再现，探究背后的技术和应对方法/15.png>)

If we draw an analogy with the Korean DeepFake incident, attackers may act like this:

1. Use a large number of sexualized images so the model learns the corresponding features; at this stage, the model learns what nudity is.
2. Obtain ordinary photos of the victim so the model learns her facial features; at this stage, the model learns the victim's appearance.
3. Use a description to make the model generate nonexistent sexualized images of the victim; at this stage, the model can create realistic but fake nude images of the victim.

## 4. How to counter Deepfake?

Pandora's box has already been opened, and no one can completely avoid having their facial features used by other people.

Recently I saw that someone on GitHub open sourced an AI model for later detection of whether an image is DeepFake.

I think you cannot spend a thousand days catching a thief, but you can avoid giving the thief a thousand days of opportunities. Although we cannot completely cut off the source of generation, we can block the paths of distribution.

## References

<div id="refer-anchor-1"></div>

[1] [韩国再现“N号房”事件，大量Deepfake性犯罪引恐慌，超500所学校受影响](https://www.163.com/dy/article/JB96QC3R051180F7.html)

[2] [她决定开源AI模型，正面宣战“N号房2.0”](https://finance.sina.com.cn/cj/2024-09-04/doc-incmxxut6381305.shtml)

[3] [Denoising Diffusion Probabilistic Models](https://arxiv.org/abs/2006.11239)

[4] [Denoising Diffusion Implicit Models](https://arxiv.org/abs/2010.02502)

[5] [deeplearning.ai](https://learn.deeplearning.ai/courses/diffusion-models/)

[6] [Diffusion Deepfake](https://arxiv.org/abs/2404.01579)

## Follow my GitHub and WeChat Official Account. No time to explain, come aboard!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)


---

## 📚 相关概念

[[concepts/AI 安全 对齐|AI 安全 对齐]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：热点
