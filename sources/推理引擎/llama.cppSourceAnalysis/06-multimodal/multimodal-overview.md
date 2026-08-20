# Multimodal Support in llama.cpp

## What Is Multimodal Support

Multimodal support enables llama.cpp to process and generate responses based on non-text inputs - images and audio - alongside standard text. It works by encoding images into embeddings using a separate model component (the multimodal projector), then feeding those embeddings into the language model for inference.

Running a multimodal model requires two GGUF files:
1. The standard language model file
2. A **multimodal projector (`mmproj`)** file that handles image/audio encoding and projection

## History

| PR | Milestone |
|----|-----------|
| #3436 | Initial LLaVA 1.5 support (`llava.cpp`, `clip.cpp`, `llava-cli`) |
| #4954 | MobileVLM added as second vision model |
| #12849 | `libmtmd` introduced as replacement for `llava.cpp` |
| #13012 | `mtmd-cli` added, consolidating all model-specific CLIs |

## Supported Models

**Current (via `convert_hf_to_gguf.py --mmproj`):**
- Gemma 3 (not 1B variant)
- SmolVLM / SmolVLM2
- Pixtral 12B
- Qwen 2 VL / Qwen 2.5 VL
- Mistral Small 3.1 24B
- InternVL 2.5 / InternVL 3
- MiniCPM-V 4.6

**Legacy (via `tools/mtmd/legacy-models` scripts):**
- LLaVA, MobileVLM, GLM-Edge
- MiniCPM-V 2.5/2.6/4.0/4.5, MiniCPM-o 2.6/4.0
- IBM Granite Vision

Pre-quantized models are listed in `docs/multimodal.md`.

## What Is `libmtmd`

`libmtmd` is the modern library replacing the original `llava.cpp`. Built on `clip.cpp`, it provides:

- **Unified Interface** - single API for all multimodal models
- **Improved UX/DX** - inspired by HuggingFace `transformers` `Processor` class
- **Multi-input Support** - text, audio, and images
- **Template Flexibility** - respects diverse chat templates across models

## Pipeline

```
Bitmap (RGB image / PCM audio)
  -> mtmd_tokenize(text + bitmap)
    -> preprocessor produces chunks
    -> special tokens injected (llava-uhd-style models)
  -> mtmd_encode() or mtmd_batch_encode()
  -> output embeddings
  -> feed to language model
```

Key terms:
- **bitmap**: raw input data (RGB image, PCM audio)
- **tiles/slices**: smaller square images for llava-uhd-style models
- **chunk**: preprocessed input for `mtmd_encode()`

## Helper Functions

`mtmd_helper` provides:
- Image/audio/video file decoding (JPEG to RGB, etc.)
- `llama_batch` management and `llama_decode` calls

## Audio Generation

Added in PR #26254, supporting a 3-stage TTS pipeline:
1. **Backbone/Semantic Stage** - text prompt + reference voice -> hidden state
2. **Acoustic Detail Generator** - hidden state -> audio codes or mel-spectrogram
3. **Waveform Reconstruction** - codes -> final waveform

Example: Qwen3-TTS uses ECAPA-TDNN speaker encoder, a backbone model, a code predictor, and a code2wav converter.

## Usage

Start the server with `--jinja` flag:
```bash
llama-server --jinja -fa -hf <model-gguf>
```

Use `mtmd-cli` for unified CLI interaction with any supported multimodal model.
