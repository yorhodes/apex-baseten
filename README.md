# Apex Flash 1 Abliterated on Baseten

Deploys the exact public BF16 checkpoint with SGLang 0.5.20 and an OpenAI-compatible API. The checkpoint revision and container digest are pinned. Baseten Delivery Network mirrors the weights before startup and caches them for subsequent replicas. No Hugging Face secret is needed for this public, ungated repository.

## Hardware and validation status

The checkpoint contains 321,322,735,872 BF16 parameters plus a small number of F32 parameters: approximately 642.65 GB / 598.5 GiB of raw weights. `B200:4` provides 720 GiB according to Baseten's resource table. The configuration caps context at 32,768 tokens and concurrency at eight requests to leave runtime headroom.

The configuration passes Truss schema validation and Baseten's authenticated push dry run. The real push was rejected because the workspace needs a payment method; no GPU deployment was created. This is a first-deployment configuration, not a GPU-tested performance claim. SGLang 0.5.20 includes `Glm5NextForConditionalGeneration`; the exact Cantina checkpoint still needs a real startup and inference test. If memory is insufficient, use `B200:8` and change `--tp-size 4` to `--tp-size 8`, or reduce context/concurrency. Eight GPUs cost twice as much. The BF16 configuration deliberately uses Triton MoE and TileLang DSA rather than copying kernels from an FP8 recipe.

Start without speculative decoding. After correctness validation, benchmark the native MTP head with `--speculative-algorithm EAGLE --speculative-num-steps 5 --speculative-eagle-topk 1 --speculative-num-draft-tokens 6`. Draft acceptance and speed must be measured on this derivative.

## Deploy

Install the Baseten CLI following [Baseten's installation instructions](https://docs.baseten.co/reference/cli/baseten/overview#install), then:

```sh
baseten auth login --web
bash deploy.sh
```

For a CLI installed somewhere else:

```sh
BASETEN_CLI=/path/to/baseten bash deploy.sh
```

The script pushes a published deployment and immediately requests:

- Minimum replicas: one (keep warm, as requested).
- Maximum replicas: one (one replica comprises all four GPUs).
- Scale-down delay: 300 seconds (the one-replica minimum prevents scale-to-zero).

Autoscaling changes apply asynchronously. Inspect the deployment with the command printed by the script and verify the settled values. If the autoscaling update fails, resolve it promptly or deactivate the deployment; the push may already have created a billable replica. `deployment.json` records the deployment IDs, endpoint, and logs URL and is excluded from version control. An unpublished model is not automatically assigned to production; the smoke test uses the deployment-specific URL returned by push.

To enable scale-to-zero later, update the deployed model with `baseten model deployment update-autoscaling --model-id MODEL_ID --deployment-id DEPLOYMENT_ID --min-replica 0` and change the script's floor accordingly. The current default keeps all four GPUs allocated between requests.

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

## Cost and cold starts

Baseten lists `B200:4` at $0.66532/minute, or $39.9192/hour per running replica (checked October 2, 2026). Model loading and warm idle time are billable; scaled-to-zero replicas incur no GPU compute charge. Image builds are billed separately. A five-minute idle delay represents about $3.33 of running time after requests stop, plus any autoscaling/termination delay.

There is no measured cold-start result for this deployment yet. Budgeting 5–15 minutes is only a rough planning estimate; initial weight mirroring, uncached image pulls, kernel compilation, and GPU scheduling may make the first deployment substantially longer. Keep it warm during an interactive work session if repeated restarts would be disruptive.

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
