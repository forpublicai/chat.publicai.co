# Hugging Face Partner Model Integration

These docs describe how to use the utility scripts in the ``developer/hugging_face`` directory to publish or edit models on hugging face that Public AI provide inference for.

## Table of Contents
- [Hugging Face access tokens](#hugging-face-access-tokens)
- [Querying Models](#querying-models)
- [Registering a new Model](#registering-a-new-model)
- [Updating Model Status](#updating-model-status-live-or-staging)

---

## Hugging face access tokens

- A HF token is required to make changes. Set the `HF_TOKEN` environment variable in the `.env` file in ``developer/hugging_face``. This token needs to be from a user with access to the Public AI HF account.

- To run the tests you will need another HF token that has inference credits on, this token can be from any user with credits. This is called ``HF_TEST_TOKEN`` and is read from the ``.env`` file in ``developer/hugging_face``.
---

## Querying Models

Fetches the list of model mappings currently registered under the `publicai` provider.

```bash
cd developer/hugging_face
./get_models.sh
```
```json
{
  "conversational": {
    "swiss-ai/Apertus-8B-Instruct-2509": {
      "_id": "68c412e0983f7675e8393c85",
      "status": "live",
      "providerId": "swiss-ai/apertus-8b-instruct"
    },
    "swiss-ai/Apertus-70B-Instruct-2509": {
      "_id": "68c78030ef5631e538f8f004",
      "status": "live",
      "providerId": "swiss-ai/apertus-70b-instruct"
    },
    ...
  }
  ```

## Registering a new model

Registers a new model mapping item under the `publicai` provider.

#### Register as staging
```bash
cd developer/hugging_face
./register_model.sh \
  --task text-generation \
  --hf-model swiss-ai/Apertus-8B-Instruct-2509 \ # hugging face id
  --provider-model swiss-ai/apertus-8b-instruct \ # litellm id
  --prod # only add this if you want it to go live to the public, otherwise it will be in staging
```

### Supported Tasks
The `--task` argument must be exactly one of the following:
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

## Testing

To test make sure you have defined ``HF_TEST_TOKEN`` in ``/developer/hugging_face/.env`` the token/account needs to have credits to call inference providers. 

```bash
cd developer/hugging_face
python test.py
```

```
========================================================================================================================
Model Name                                         | Status       | TTFT (s)  
------------------------------------------------------------------------------------------------------------------------
aisingapore/Gemma-SEA-LION-v4-27B-IT               | SUCCESS      | 1.117s    
aisingapore/Qwen-SEA-LION-v4-32B-IT                | SUCCESS      | 1.357s    
allenai/Olmo-3-7B-Instruct                         | SUCCESS      | 1.216s    
speakleash/Bielik-11B-v3.0-Instruct                | SUCCESS      | 1.048s    
swiss-ai/Apertus-70B-Instruct-2509                 | SUCCESS      | 1.048s    
swiss-ai/Apertus-8B-Instruct-2509                  | SUCCESS      | 0.862s    
swiss-ai/Apertus-v1.5-70B                          | SUCCESS      | 0.499s    
swiss-ai/Apertus-v1.5-8B                           | SUCCESS      | 0.754s    
utter-project/EuroLLM-22B-Instruct-2512            | SUCCESS      | 0.906s    
========================================================================================================================
```

## Updating Model Status: Live or Staging

Updates the status of an existing model mapping item.

### Promote a model to live/production
```bash
cd developer/hugging_face
./update_status.sh 6a454f4ffdad7c320e5699ff --prod
```

### Revert a model to staging
```bash
cd developer/hugging_face
./update_status.sh 6a454f4ffdad7c320e5699ff --staging
```