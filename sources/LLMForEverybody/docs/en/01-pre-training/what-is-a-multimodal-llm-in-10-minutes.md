What is a multimodal LLM (MM-LLM) in 10 minutes?

## 1. What Is Multimodality?

Multimodality means methods and technologies for integrating and processing two or more different types of information or data. In machine learning and artificial intelligence, these data types usually include, but are not limited to, text, images, video, audio, and sensor data. The goal of multimodal systems is to use information from several modalities to improve task performance, create a richer user experience, or produce more complete data analysis.

![alt text](<../../../01-第一章-预训练/assest/10分钟了解什么是多模态大模型（Multimodal LLMs）/00.png>)

## 2. Why Are Multimodal Large Language Models Still Language Models?

Multimodal Large Language Models, or MLLMs, are models that combine the natural language processing ability of Large Language Models (LLMs) with the ability to understand and generate data from other modalities, such as visual or audio data. These models combine text, images, sound, and other input and output types, creating a richer and more natural interaction experience.

The key advantage of MLLMs is that they can process and understand information from different modalities, then combine it to solve complex tasks. For example, an MLLM can analyze an image and generate descriptive text, or do the opposite and create a matching image from a text description. This cross-modal understanding and generation gives MLLMs broad application prospects in autonomous driving, intelligent assistants, content recommendation systems, education, and training.

![alt text](<../../../01-第一章-预训练/assest/10分钟了解什么是多模态大模型（Multimodal LLMs）/0.png>)

The diagram above shows the key components of MLLMs:

- **Modality Encoder**: encodes input data from different modalities into representations the model can understand.
- **Input Projector**: maps input data from different modalities into a shared semantic space.
- **LLMs**: large language models used to process text data.
- **Output Projector**: maps the model-generated output back into the space of the original modality.
- **Modality Generator**: generates matching output data based on the input.

As you can see, LLMs are still at the center. Multimodality extends their abilities. The extension works by finding a way to map data from different modalities into a semantic space that LLMs can accept as input. Next, let's look at these components one by one.

## 3. Modality Encoder

The Modality Encoder is a key component of a multimodal LLM. Its main job is to convert input data from different modalities into feature representations that the model can process. These inputs may include images, text, audio, video, and other forms. The role of the modality encoder is a bit like a translator: it translates information in different "languages" (modalities) into a shared "language" the model can understand and process.

Common modality encoders in multimodal LLMs include:

- Image encoder: handles visual information and converts images into feature vectors. Common image encoders include NFNet, ViT (Vision Transformer), CLIP ViT, and others.

![alt text](<../../../01-第一章-预训练/assest/10分钟了解什么是多模态大模型（Multimodal LLMs）/1.png>)

- Audio encoder: processes audio data and converts the audio signal into a frequency representation, for example using Fourier transforms or mel-frequency cepstral coefficients (MFCCs). Audio encoders help the model recognize speech, music, and other sound features. In multimodal models, common audio encoders include Whisper, CLAP, and others.

- Video encoder: more complex, because it must handle both images and time series. A video encoder not only extracts visual features from each frame, but also needs to understand temporal changes between frames, such as motion. It can use technologies similar to image encoders for each frame, plus additional methods for relationships between frames, such as ViViT, VideoPrism, and others.

The design of modality encoders is extremely important for multimodal LLM quality, because it directly affects the model's ability to accurately understand and generate cross-modal content. With effective modality encoders, multimodal LLMs can show stronger and more flexible abilities across many complex tasks.

## 4. Input Projector

The Input Projector (IP) is a key component of a multimodal LLM. Its main role is to project encoded features from different modalities into a shared feature space, so those features can be processed and understood consistently by other parts of the model, such as the LLM backbone.

In a multimodal LLM, different input types such as images, text, and audio are first processed by the corresponding Modality Encoder (ME) and converted into feature representations. But these features may live in spaces with different dimensions, and directly mixing them creates compatibility problems. The input projector solves this problem. Through transformations such as a linear layer, a multilayer perceptron (MLP), cross-attention, and other methods, it maps features from different modalities into one shared feature space.

The design of the input projector is critical for multimodal LLM quality, because it directly affects how the model processes and understands semantic information from different data types. Effective input projection helps the model do better cross-modal fusion and downstream tasks, such as image captioning and visual question answering.

![alt text](<../../../01-第一章-预训练/assest/10分钟了解什么是多模态大模型（Multimodal LLMs）/2.png>)

## 5. Output Projector

The Output Projector (OP) is a key component of a multimodal LLM. Its main job is to convert the output signal of the large language model into a feature representation suitable for generators of different modalities. These generators may create images, video, audio, or other modality data.

In a multimodal LLM, the LLM is responsible for processing and understanding input features from different modalities and generating the corresponding output. But LLM output is usually text-shaped, while generators for other modalities need input in a specific format. This is where the output projector acts as a bridge: it converts the text output of the LLM into a feature representation that other modality generators can understand and process.

The output projector can be implemented with several technologies, including but not limited to Tiny Transformer and multilayer perceptrons (MLPs). These technologies learn to map LLM output into the feature space of the target modality, enabling cross-modal feature conversion. With the output projector, a multimodal LLM can better support information exchange between modalities and generation tasks.

For example, in NExT-GPT, the output projector includes an image output projector, an audio output projector, and a video output projector. Together they form an "instruction-following alignment" mechanism. This mechanism ensures that the model can switch smoothly between several modalities based on LLM output and generate multimodal content effectively.

![alt text](<../../../01-第一章-预训练/assest/10分钟了解什么是多模态大模型（Multimodal LLMs）/3.png>)

## 6. Modality Generator

The Modality Generator (MG) is a key component of a multimodal learning system. Its main role is to generate outputs in different modalities, such as images, video, or audio.

The concrete implementation of a modality generator may include, but is not limited to, the following technologies and models:

- image generation: for example Stable Diffusion, an image generation technology based on diffusion models.
- video generation: for example Zeroscope, focused on video-content generation.
- audio generation: for example AudioLDM, used to generate audio signals.

In a multimodal LLM, the modality generator is a key technology for modality conversion and content generation. It lets the model flexibly process and generate different data types, giving the user a richer and more natural interaction experience.

![alt text](<../../../01-第一章-预训练/assest/10分钟了解什么是多模态大模型（Multimodal LLMs）/4.png>)

## References

<div id="refer-anchor-1"></div>

[1] [A Survey on Multimodal Large Language Models](https://arxiv.org/abs/2306.13549)

[2] [MM-LLMs: Recent Advances in MultiModal Large Language Models](https://arxiv.org/abs/2401.13601)

[3] [NExT-GPT: Any-to-Any Multimodal Large Language Model](https://next-gpt.github.io/)

## Follow my GitHub and WeChat account: no time to explain, everyone aboard!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

The repository has the original Markdown files, and the project is fully open source. Stars and forks are very welcome.
