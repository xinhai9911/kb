# llama.cpp - Other CLI Tools Overview

llama.cpp includes several utility tools beyond `llama-cli` and `llama-completion`.

---

## llama-quantize

Converts GGUF models from high-precision formats (F32, BF16) to quantized formats. Reduces model size and can speed up inference, with some accuracy loss measured by perplexity (ppl) and KL divergence (kld).

### Basic Usage

```bash
# Basic quantization
./llama-quantize input-f32.gguf output-Q4_K_M.gguf Q4_K_M

# Short form
./llama-quantize input-f32.gguf q4_k_m 8
```

### Two-Phase Workflow

1. **Convert** Hugging Face model to GGUF:
   ```bash
   python convert_hf_to_gguf.py --outfile model-bf16.gguf --outtype bf16 --remote user/model
   ```

2. **Quantize** the GGUF file:
   ```bash
   ./llama-quantize model-bf16.gguf model-Q4_K_M.gguf Q4_K_M
   ```

### Multimodal Components

```bash
# Convert and quantize mmproj separately
python convert_hf_to_gguf.py --mmproj --outfile mmproj-Q8_0.gguf --outtype q8_0 --remote user/model
```

### Key Options

| Option | Description |
|--------|-------------|
| `--imatrix FILE` | Use importance matrix for quantization optimization |
| `--allow-requantize` | Allow requantizing already-quantized tensors (warning: reduces quality) |
| `--leave-output-tensor` | Leave output.weight un(re)quantized |
| `--pure` | Disable k-quant mixtures; quantize all tensors to same type |
| `--output-tensor-type TYPE` | Specific quant type for output.weight |
| `--token-embedding-type TYPE` | Specific quant type for token embeddings |
| `--keep-split` | Generate quantized model in same shards as input |
| `--include-weights TENSOR` | Apply imatrix to specific tensors |
| `--exclude-weights TENSOR` | Exclude specific tensors from imatrix |
| `--tensor-type REGEX=TYPE` | Quantize specific tensors to specific types (supports regex) |
| `--prune-layers LIST` | Remove specified layers |
| `--override-kv KEY=TYPE:VALUE` | Override model metadata in quantized model |

### Quantization Methods

| Method | Bits/Weight | 8B Model Size | Quality |
|--------|-------------|---------------|---------|
| IQ1_S | 2.0 | ~1.9 GiB | Lowest |
| IQ2_XXS | 2.4 | ~2.2 GiB | Very Low |
| Q2_K_S | 3.0 | ~2.8 GiB | Low |
| Q3_K_S | 3.6 | ~3.4 GiB | Medium-Low |
| Q3_K_M | 4.0 | ~3.7 GiB | Medium |
| Q4_K_S | 4.7 | ~4.4 GiB | Medium-High |
| Q4_K_M | 4.9 | ~4.6 GiB | High (default) |
| Q5_K_S | 5.6 | ~5.2 GiB | High |
| Q5_K_M | 5.7 | ~5.3 GiB | Very High |
| Q6_K | 6.6 | ~6.1 GiB | Very High |
| Q8_0 | 8.5 | ~8.0 GiB | Near-lossless |
| F16 | 16.0 | ~15.0 GiB | Lossless |

### Memory/Disk Requirements

| Model | Original (F32) | Q4_K_M |
|-------|----------------|--------|
| 8B | 32.1 GB | 4.9 GB |
| 70B | 280.9 GB | 43.1 GB |
| 405B | 1,625.1 GB | 249.1 GB |

---

## llama-bench

Performance testing tool for measuring prompt processing and text generation speeds.

### Syntax

```
llama-bench [options]
```

### Test Types

- **Prompt processing (pp)**: Processing a prompt in batches (`-p`)
- **Text generation (tg)**: Generating a sequence of tokens (`-n`)
- **Combined (pg)**: Processing + generation (`-pg`)

### Key Options

| Option | Description | Default |
|--------|-------------|---------|
| `-m, --model FILE` | Model file | models/7B/ggml-model-q4_0.gguf |
| `-hf, --hf-repo USER/MODEL[:quant]` | Hugging Face repo | unused |
| `-p, --n-prompt N` | Prompt tokens for pp test | 512 |
| `-n, --n-gen N` | Tokens to generate for tg test | 128 |
| `-pg PP,TG` | Combined pp+tg test | - |
| `-d, --n-depth N` | Context depth (prefill KV cache) | 0 |
| `-b, --batch-size N` | Batch size | 2048 |
| `-ub, --ubatch-size N` | Micro-batch size | 512 |
| `-t, --threads N` | CPU threads | system dependent |
| `-ngl, --n-gpu-layers N` | GPU layers | -1 |
| `-fa, --flash-attn MODE` | Flash Attention | auto |
| `-r, --repetitions N` | Repetitions per test | 5 |
| `-o, --output FORMAT` | Output format (csv, json, jsonl, md, sql) | md |
| `--numa MODE` | NUMA mode | disabled |
| `--prio N` | Thread priority | 0 |
| `--delay N` | Delay between tests (seconds) | 0 |
| `--progress` | Print progress indicators | - |
| `--no-warmup` | Skip warmup runs | - |

### Multiple Values

Parameters accept multiple values via commas or repeated flags:

```bash
# Test different batch sizes
./llama-bench -m model.gguf -n 0 -p 1024 -b 128,256,512,1024

# Test different thread counts
./llama-bench -m model.gguf -t 1,2,4,8,16,32

# Test different GPU layer counts
./llama-bench -m model.gguf -ngl 10,20,30,32

# Ranges
./llama-bench -ngl 10-35+5
```

### Output Formats

- **Markdown** (`-o md`): Default, human-readable table
- **CSV** (`-o csv`): Comma-separated values
- **JSON** (`-o json`): JSON array with full details
- **JSONL** (`-o jsonl`): One JSON object per line
- **SQL** (`-o sql`): SQLite-compatible CREATE/INSERT statements

### Example: Benchmark a Model

```bash
# Basic benchmark
./llama-bench -m models/llama-7b-q4_k_m.gguf

# Compare GPU layers
./llama-bench -m models/llama-7b-q4_k_m.gguf -ngl 0,10,20,32

# Output to JSON for analysis
./llama-bench -m models/llama-7b-q4_k_m.gguf -o json > results.json
```

---

## llama-imatrix

Computes an importance matrix for a model using calibration data. The imatrix is used during quantization to optimize quality.

### Basic Usage

```bash
# Generate importance matrix
./llama-imatrix -m model-f16.gguf -f calibration-data.txt -ngl 99

# Use imatrix for quantization
./llama-quantize --imatrix imatrix.gguf model-f16.gguf model-Q4_K_M.gguf Q4_K_M
```

### Key Options

| Option | Description | Default |
|--------|-------------|---------|
| `-m, --model FILE` | Model file (required) | - |
| `-f, --file FILE` | Calibration data file (required) | - |
| `-o, --output-file FILE` | Output imatrix file | imatrix.gguf |
| `-ofreq, --output-frequency N` | Save to disk every N chunks | 10 |
| `--output-format FORMAT` | Output format (gguf, dat) | gguf |
| `--save-frequency N` | Save snapshot copies every N chunks | 0 |
| `--process-output` | Collect data for output.weight tensor | false |
| `--in-file FILE` | Load/merge existing imatrix files | - |
| `--parse-special` | Parse special tokens | - |
| `--chunk N` | Skip first N chunks | - |
| `--chunks N` | Max chunks to process (-1 = all) | -1 |
| `--no-ppl` | Disable perplexity calculation | - |
| `--show-statistics` | Display imatrix statistics | - |
| `-ngl, --n-gpu-layers N` | GPU layers (recommended for speed) | - |

### Statistics

`--show-statistics` displays per-tensor and per-layer metrics:
- **Sum(Act^2)**: Sum of squared activations (importance scores)
- **Min/Max**: Min and max squared activation values
- **Mean/StdDev**: Statistics of squared activations
- **% Active**: Proportion of active elements (threshold: 1e-5)
- **Entropy**: Shannon entropy of the distribution (bits)
- **Normalized Entropy**: Entropy normalized by log2(N)
- **ZD Score**: Layer importance score per Layer-Wise Quantization paper
- **CosSim**: Cosine similarity with previous layer

### Examples

```bash
# Generate and use imatrix
./llama-imatrix -m model-f16.gguf -f wiki.train.raw -ngl 99
./llama-quantize --imatrix imatrix.gguf model-f16.gguf model-Q4_K_M.gguf q4_k_m

# Convert legacy format to GGUF
./llama-imatrix --in-file imatrix-legacy.dat -o imatrix.gguf

# Combine multiple imatrices
./llama-imatrix --in-file imatrix-0.gguf --in-file imatrix-1.gguf -o combined.gguf

# Analyze imatrix
./llama-imatrix --in-file imatrix.gguf --show-statistics
```

---

## llama-gguf-split

Splits or merges GGUF model files. Useful for distributing large models across multiple files.

### Basic Usage

```bash
# Split a large GGUF file into smaller parts
./llama-gguf-split input.gguf output_prefix.gguf --chunk-size 10GiB

# Merge split files back together
./llama-gguf-split --merge output_prefix-00001-of-00003.gguf merged.gguf
```

### Key Options

| Option | Description |
|--------|-------------|
| `--chunk-size SIZE` | Maximum size per split file (supports K, M, G suffixes) |
| `--merge` | Merge split files into a single file |

---

## Other Tools

### llama-perplexity

Computes perplexity of a model against a text dataset. Used to evaluate model quality after quantization.

```bash
./llama-perplexity -m model.gguf -f test-data.txt
```

### llama-tokenize

Tokenizes text using a model's tokenizer. Useful for debugging tokenization issues.

```bash
./llama-tokenize -m model.gguf --text "Hello, world!"
```

### llama-embedding

Generates embeddings from text using a GGUF model.

```bash
./llama-embedding -m model.gguf --input "Text to embed"
```

### llama-cvector-generator

Generates control vectors from text datasets. Control vectors modify model behavior during inference.

### llama-export-lora

Exports LoRA adapter weights from a model.

### llama-cmd

Interactive command-line tool for various llama.cpp operations.

### llama-rpc

RPC server for distributed inference across multiple machines.

### llama-mtmd-cli

Multimodal CLI tool for models with vision/audio capabilities.

### llama-tts

Text-to-speech tool for supported models.

### llama-server

HTTP server for serving models via API (see server documentation).

### llama-batched-bench

Batched inference benchmarking tool.

### llama-fit-params

Tool for fitting model parameters to device memory.

### llama-results

Results processing and analysis tool.

### llama-ui

Web-based UI for interacting with models.

---

## Workflow Summary

Typical llama.cpp workflow:

```
1. Download/Convert model to GGUF
   convert_hf_to_gguf.py -> model-bf16.gguf

2. (Optional) Generate importance matrix
   llama-imatrix -m model-bf16.gguf -f calibration.txt -ngl 99

3. Quantize model
   llama-quantize --imatrix imatrix.gguf model-bf16.gguf model-Q4_K_M.gguf Q4_K_M

4. (Optional) Benchmark
   llama-bench -m model-Q4_K_M.gguf

5. Run inference
   llama-cli -m model-Q4_K_M.gguf --prompt "Hello"
```
