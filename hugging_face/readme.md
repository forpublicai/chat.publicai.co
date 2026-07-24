# Hugging Face Partner Model Integration

This directory contains utility scripts to interact with the Hugging Face Inference Providers API for the Public AI partner integration.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Querying Models (`get_models.sh`)](#querying-models-get_modelssh)
- [Registering Model Mappings (`register_model.sh`)](#registering-model-mappings-register_modelsh)
- [Updating Model Status (`update_status.sh`)](#updating-model-status-update_statussh)

---

## Prerequisites

- **`curl`** and **`jq`** must be installed on your system.
- An **API Token** is required to view or register `staging` models. You can either pass it via the `--token` flag or set the `HF_TOKEN` environment variable.

---

## Querying Models (`get_models.sh`)

Fetches the list of model mappings currently registered under the `publicai` provider.

### Options
* `-s, --status <status>`: Filter models by status. Default is `"staging|live"`. Note: Since the Hugging Face API does not support multi-status query parameters directly, the script queries them sequentially and merges the output.
* `-t, --token <token>`: Hugging Face API token (can also be read from `HF_TOKEN`).
* `-h, --help`: Show help instructions.

### Examples

#### Query both staging and live models (unauthenticated / default)
```bash
./get_models.sh
```

#### Query with a token to view staging models
```bash
./get_models.sh --token your_hf_token
```

#### Query only live models
```bash
./get_models.sh --status live
```

---

## Registering Model Mappings (`register_model.sh`)

Registers a new model mapping item under the `publicai` provider.

### Options
* `-t, --task <value>`: **Required**. The task/widget type of the model (e.g. `text-generation`). See [Supported Tasks](#supported-tasks).
* `-m, --hf-model <value>`: **Required**. The Hugging Face model path (`namespace/model-name`).
* `-p, --provider-model <value>`: **Required**. The partner model ID on the Public AI side.
* `--live` or `--prod`: Set status to `live`. If omitted, defaults to `staging`.
* `--token <value>`: Hugging Face API token (can also be read from `HF_TOKEN`).
* `-h, --help`: Show help instructions.

### Supported Tasks
The `-t` / `--task` argument must be exactly one of the following:
* `text-generation`
* `conversational`
* `image-text-to-text`
* `feature-extraction`
* `text-classification`
* `token-classification`
* `question-answering`
* `fill-mask`
* `summarization`
* `translation`
* `text2text-generation`
* `text-to-image`
* `image-classification`
* `object-detection`
* `image-segmentation`
* `image-to-image`
* `automatic-speech-recognition`
* `text-to-speech`
* `audio-classification`
* `audio-to-audio`
* `zero-shot-classification`
* `zero-shot-image-classification`
* `visual-question-answering`
* `document-question-answering`
* `depth-estimation`
* `video-classification`
* `text-to-video`

### Examples

#### Register as staging (default status)
```bash
./register_model.sh \
  --task text-generation \
  --hf-model swiss-ai/Apertus-8B-Instruct-2509 \
  --provider-model swiss-ai/apertus-8b-instruct \
  --token your_hf_token
```

#### Register as live/prod (live status)
```bash
./register_model.sh \
  --task text-generation \
  --hf-model swiss-ai/Apertus-8B-Instruct-2509 \
  --provider-model swiss-ai/apertus-8b-instruct \
  --prod \
  --token your_hf_token
```

#### Trigger validation error (invalid task value)
```bash
./register_model.sh \
  --task invalid-task \
  --hf-model swiss-ai/Apertus-8B-Instruct-2509 \
  --provider-model swiss-ai/apertus-8b-instruct
```

---

## Updating Model Status (`update_status.sh`)

Updates the status of an existing model mapping item.

### Options
* `-i, --id <value>`: The model mapping ID to update (can also be passed as the first positional argument).
* `-s, --status <value>`: The new status, either `"live"` or `"staging"` (default: `"live"`).
* `--live` or `--prod`: Set status to `"live"`.
* `--staging`: Set status to `"staging"`.
* `--token <value>`: Hugging Face API token (can also be read from `HF_TOKEN`).
* `-h, --help`: Show help instructions.

### Examples

#### Promote a model to live/production (using positional mapping ID)
```bash
./update_status.sh 6a454f492dad7c320e56992c --prod --token your_hf_token
```

#### Revert a model to staging
```bash
./update_status.sh 6a454f492dad7c320e56992c --staging --token your_hf_token
```


./register_model.sh --task conversational --hf-model swiss-ai/Apertus-v1.5-8B --provider-model swiss-ai/apertus-v1.5-8b --live
./register_model.sh --task conversational --hf-model swiss-ai/Apertus-v1.5-70B --provider-model swiss-ai/apertus-v1.5-70b --live