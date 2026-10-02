# Apex Flash 1 Abliterated on Baseten

Deploys the exact public BF16 checkpoint with SGLang 0.5.20 and an OpenAI-compatible API. The checkpoint revision and container digest are pinned. Baseten Delivery Network mirrors the weights before startup and caches them for subsequent replicas. No Hugging Face secret is needed for this public, ungated repository.

## Hardware and validation status

The checkpoint contains 321,322,735,872 BF16 parameters plus a small number of F32 parameters: approximately 642.65 GB / 598.5 GiB of raw weights. `B200:4` provides 720 GiB according to Baseten's resource table. The configuration caps total context at 131,072 tokens and concurrency at two requests to leave room for longer security-review reasoning.

B200 access is enabled, and the exact Cantina checkpoint passed startup and streaming inference validation at 32,768 context on October 2, 2026. That replica was deactivated after the audit. The new 131,072 context configuration is prepared for validation, with zero minimum and one maximum replica.

In the initial validation, weights loaded in approximately 253 seconds, using 146.8 GiB per GPU. Cache allocation and decode CUDA graph capture succeeded, leaving approximately 16.7 GiB free per GPU at the original 32,768-token context and eight-request limit. The BF16 configuration uses Triton MoE and TileLang DSA. SGLang reported fallback MoE kernel configurations for this B200 shape. The larger context, tool calling, multimodal inputs and concurrent long requests have not yet been validated.

The pinned checkpoint declares `text_config.max_position_embeddings: 1048576`, but that is not a validated serving limit on this hardware. SGLang's Responses implementation budgets generation from configured context minus prompt/reserved tokens; reasoning and the visible answer share that budget. A local capture of Codex CLI 0.160.0 confirmed it omits `max_output_tokens`, so SGLang chooses the remaining budget. The private Codex profile/catalog now advertise 131,072 context, with automatic compaction at 64,000 tokens to preserve generation headroom. Direct API callers can request `max_output_tokens: 65536` (Responses) or `max_tokens: 65536` (Chat Completions), provided prompt plus generation fits the server limit.

Start without speculative decoding. After correctness validation, benchmark the native MTP head with `--speculative-algorithm EAGLE --speculative-num-steps 5 --speculative-eagle-topk 1 --speculative-num-draft-tokens 6`. Draft acceptance and speed must be measured on this derivative.

## Deploy

Install the Baseten CLI following [Baseten's installation instructions](https://docs.baseten.co/reference/cli/baseten/overview#install), then:

```sh
baseten auth login --web
bash deploy.sh
```

A payment method and access to `B200:4` are required. Check available instance types before pushing:

```sh
baseten api management /v1/instance_types --jq '.instance_types | map(select(.gpu_type == "B200" and .gpu_count == 4))'
```

If this returns an empty list, request four-B200 access from Baseten support. Adding prepaid credits does not enable a missing GPU instance type; usage can be billed to the payment method after any existing credits are applied.

For a CLI installed somewhere else:

```sh
BASETEN_CLI=/path/to/baseten bash deploy.sh
```

For this existing model, the script sets production autoscaling before pushing a new production deployment, then applies the same settings to that deployment:

- Minimum replicas: zero (release idle GPU compute).
- Maximum replicas: one (one replica comprises all four GPUs).
- Scale-down delay: 60 seconds.
- Concurrency target: two requests.

Autoscaling changes apply asynchronously. Inspect the deployment with the command printed by the script and verify the settled values. Startup/validation can still allocate a billable replica; deactivate it after verification if continued serving is not needed. Deployment IDs, endpoint and logs URL are saved outside the repository, in `apex-baseten-deployment.json` in the system temporary directory. The smoke test uses the deployment-specific URL returned by push.

The deployment default is scale-to-zero. To hold a model warm for an active work session, explicitly raise the minimum to one, then lower it to zero or deactivate when finished.

## Call and measure

Create an inference API key in Baseten, set `BASETEN_API_KEY` in your shell, then:

```sh
python3 smoke_test.py
```

The client uses the streaming `/predict` mapping, prints output, and reports time to first chunk and total request time. This measures a request, not every startup phase. To measure wake-from-zero latency, confirm the replica count is zero, send the request, and inspect replica startup/model-load logs alongside client timing. Baseten request timeouts may require waking the model separately before inference.

For the OpenAI SDK, the corresponding deployment-specific base URL is:

```text
https://model-MODEL_ID.api.baseten.co/deployment/DEPLOYMENT_ID/sync/v1
```

For a stable production base URL:

```text
https://model-MODEL_ID.api.baseten.co/environments/production/sync/v1
```

Use model name `cantina-security/apex-flash-1-abliterated` and your individual inference-only key as `OPENAI_API_KEY`. Keep credentials, share links, and account-specific deployment metadata outside this repository.

The first external streaming smoke test returned `2 + 2 = 4`, with a first chunk at 3.32 seconds and total time of 4.58 seconds, including reasoning output. This is one short request, not a throughput benchmark.

## Cost and cold starts

Baseten lists `B200:4` at $0.66532/minute, or $39.9192/hour per running replica (checked October 2, 2026). Model loading and warm idle time are billable; scaled-to-zero replicas incur no GPU compute charge. Image builds are billed separately. A five-minute idle delay represents about $3.33 of running time after requests stop, plus any autoscaling/termination delay.

The initial deployment took approximately 26 minutes from creation to readiness, including image build, initial weight mirroring, scheduling, replica downloads, model loading, and compilation. The replica downloaded the 643 GB checkpoint in approximately 623 seconds; model loading took 253 seconds and decode CUDA graph capture took 139 seconds. Subsequent starts may benefit from caches, but wake-from-zero latency has not been measured. Keep it warm during an interactive work session if repeated restarts would be disruptive.

## Alternative host

A GPU VM or Runpod Pod can run the same SGLang container and server arguments, replacing `/models/apex` with `cantina-security/apex-flash-1-abliterated` or a local downloaded snapshot. Use a multi-GPU node with fast interconnects and enough disk for the approximately 643 GB checkpoint plus container/cache space. Account for authentication and TLS when exposing an API. The provider with immediately available compatible GPUs will be quickest in practice; there is no verified provider speed comparison for this checkpoint. Hugging Face currently lists no inference provider for this exact model.

## Sources

- [Cantina model card](https://huggingface.co/cantina-security/apex-flash-1-abliterated)
- [SGLang GLM-5.3-Flash cookbook](https://github.com/sgl-project/sglang/blob/main/docs/cookbook/autoregressive/GLM/GLM-5.3-Flash.mdx)
- [Baseten SGLang deployment example](https://docs.baseten.co/examples/sglang)
- [Baseten Delivery Network](https://docs.baseten.co/development/model/bdn)
- [Resources and prices](https://docs.baseten.co/deployment/resources)
- [Billing lifecycle](https://docs.baseten.co/organization/billing#replica-lifecycle)
- [Scale to zero](https://docs.baseten.co/deployment/manage/scaling#scale-to-zero)
