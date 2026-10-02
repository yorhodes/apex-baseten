"""Make one streaming request and report time to first chunk and total time."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", help="Override the predict URL; useful for another host.")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--max-tokens", type=int, default=1024, help="Generation budget, including reasoning.")
    args = parser.parse_args()
    if args.max_tokens <= 0:
        parser.error("--max-tokens must be positive")
    if args.url:
        url = args.url
    else:
        deployment = json.loads((Path(tempfile.gettempdir()) / "apex-baseten-deployment.json").read_text())
        url = deployment["predict_url"]
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("BASETEN_API_KEY")
    if api_key:
        headers["Authorization"] = f"Api-Key {api_key}"
    elif not args.url:
        parser.error("Set BASETEN_API_KEY to call the Baseten endpoint.")
    body = {
        "model": "cantina-security/apex-flash-1-abliterated",
        "messages": [{"role": "user", "content": "What is 2 + 2?"}],
        "max_tokens": args.max_tokens,
        "temperature": 1.0,
        "top_p": 0.95,
        "stream": True,
    }
    request = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    started = time.monotonic()
    first_chunk = None
    received = False
    with urllib.request.urlopen(request, timeout=args.timeout) as response:
        for raw_line in response:
            line = raw_line.decode().strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            event = json.loads(data)
            if "error" in event:
                raise RuntimeError(event["error"])
            choices = event.get("choices", [])
            if not choices:
                continue
            received = True
            if first_chunk is None:
                first_chunk = time.monotonic() - started
            delta = choices[0].get("delta", {})
            output = delta.get("content") or delta.get("reasoning_content") or ""
            print(output, end="", flush=True)
    if not received:
        raise RuntimeError("No completion chunks received.")
    print(f"\nFirst chunk: {first_chunk:.2f}s; total: {time.monotonic() - started:.2f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
