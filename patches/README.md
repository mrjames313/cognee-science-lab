# Local dependency patches

## Cognee 1.6.2 — OpenAI-compatible Hugging Face tokenizer override

`cognee-1.6.2-openai-compatible-tokenizer.patch` fixes a Cognee 1.6.2 issue where `HUGGINGFACE_TOKENIZER` is read from configuration but is not propagated to `OpenAICompatibleEmbeddingEngine`.

This matters for NVIDIA-hosted embeddings because the API model name:

```text
nvidia/nemotron-3-embed-1b
```

is not the same as the Hugging Face repository containing the matching tokenizer:

```text
nvidia/Nemotron-3-Embed-1B-BF16
```

Without the patch, Cognee attempts to load the tokenizer from the API model name, producing a Hugging Face 404 and falling back to an approximate tokenizer.

The patch:
- forwards `huggingface_tokenizer` into `OpenAICompatibleEmbeddingEngine`
- stores it before tokenizer initialization
- passes it to `resolve_embedding_tokenizer()`

Current `.env` configuration should include:

```env
HUGGINGFACE_TOKENIZER=nvidia/Nemotron-3-Embed-1B-BF16
```

If the virtual environment is rebuilt, reapply the patch from the Cognee `site-packages` directory:

```bash
patch -p1 < /Users/michaeljames/projects/cognee-science-lab/patches/cognee-1.6.2-openai-compatible-tokenizer.patch
```

This patch is version-specific to Cognee 1.6.2 and should be removed once the upstream OpenAI-compatible embedding implementation propagates `HUGGINGFACE_TOKENIZER` correctly.