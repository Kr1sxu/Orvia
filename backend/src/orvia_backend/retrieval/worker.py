"""固定Qwen官方last-token pooling；无生成、插件、远程代码或联网补下载。"""

import json
import sys

from .model import SIGNATURE
from .runtime import verify
from pathlib import Path


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def main():
    try:
        directory = Path(sys.argv[1])
        verify(directory)
        import torch
        from transformers import AutoModel, AutoTokenizer
        torch.set_num_threads(4)
        torch.set_num_interop_threads(1)
        tokenizer = AutoTokenizer.from_pretrained(str(directory), local_files_only=True, trust_remote_code=False, padding_side="left")
        model = AutoModel.from_pretrained(str(directory), local_files_only=True, trust_remote_code=False, use_safetensors=True,
                                          torch_dtype=torch.float32).eval().to("cpu")
        emit({"ready": True, "signature": SIGNATURE})
        for line in sys.stdin.buffer:
            if len(line) > 32 * 1024:
                emit({"error": "MODEL_INPUT_LIMIT"})
                return
            request = json.loads(line)
            texts = request["texts"]
            if request["query"]:
                texts = ["Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery:" + text for text in texts]
            vectors = []
            with torch.inference_mode():
                for offset in range(0, len(texts), 4):
                    inputs = tokenizer(texts[offset:offset + 4], padding=True, truncation=False, return_tensors="pt")
                    if inputs["input_ids"].shape[1] > 1024:
                        emit({"error": "MODEL_TOKEN_LIMIT"})
                        break
                    # 左侧padding令末token始终是有效token；不以padding位置计算嵌入。
                    pooled = model(**inputs).last_hidden_state[:, -1]
                    vectors.extend(torch.nn.functional.normalize(pooled, p=2, dim=1).tolist())
                else:
                    emit({"vectors": vectors})
    except (ImportError, OSError, ValueError, RuntimeError, KeyError):
        emit({"error": "MODEL_RUNTIME_UNAVAILABLE"})


if __name__ == "__main__":
    main()
