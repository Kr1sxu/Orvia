"""固定官方模型工件清单；仅显式准备阶段允许下载，推理阶段绝不补下载。"""

MODEL = "Qwen/Qwen3-Embedding-0.6B"
REVISION = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
SIGNATURE = f"{MODEL}@{REVISION}:1024:qwen-lasttoken-v1"
FILES = {
    "config.json": (727, "git-sha1", "cef2749ee93607b8f9a58ec72f4f6bfaf874e71d"),
    "merges.txt": (1671853, "git-sha1", "31349551d90c7606f325fe0f11bbb8bd5fa0d7c7"),
    "model.safetensors": (1191586416, "sha256", "0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd"),
    "tokenizer.json": (11423705, "sha256", "def76fb086971c7867b829c23a26261e38d9d74e02139253b38aeb9df8b4b50a"),
    "tokenizer_config.json": (9706, "git-sha1", "7345216a0785dc7086e8c245b2a9d3896ce2b756"),
    "vocab.json": (2776833, "git-sha1", "4783fe10ac3adce15ac8f358ef5462739852c569"),
}


def manifest():
    return {"model": MODEL, "revision": REVISION, "license": "Apache-2.0",
            "source": f"https://huggingface.co/{MODEL}/tree/{REVISION}",
            "bytes": sum(item[0] for item in FILES.values()),
            "files": [{"name": name, "bytes": size, "algorithm": algorithm, "digest": digest}
                      for name, (size, algorithm, digest) in FILES.items()]}
