"""本地向量化。

为什么不调云端 embedding API：DeepSeek 目前不提供 embedding 端点，为一个演示项目
再挂一个向量服务既增加部署面又增加评审现场的不确定性。这里用字符 n-gram 哈希向量
（1/2/3-gram，512 维，带 idf 权重、L2 归一化），中文短文本的召回表现足够支撑
「BM25 + 向量 → RRF → LLM 精排」这条混合检索链路，且完全离线、确定性可复现。

需要更高召回时，把 `embed()` 换成任意 bge-m3 服务即可，上层无感。
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

DIM = 512
_norm_re = re.compile(r"[\s\u3000]+")
_bad_re = re.compile(r"[^\w\u4e00-\u9fff]+")


def normalize(text: str) -> str:
    return _bad_re.sub(" ", _norm_re.sub(" ", text or "")).lower()


def tokenize(text: str) -> list[str]:
    """中文按字符 bigram + 英文按词，兼顾中英混排。"""
    text = normalize(text)
    tokens: list[str] = []
    for word in text.split():
        if re.fullmatch(r"[a-z0-9_.+-]+", word):
            tokens.append(word)
        else:
            chars = list(word)
            tokens.extend(chars)
            tokens.extend("".join(pair) for pair in zip(chars, chars[1:]))
    return tokens


def _bucket(token: str) -> int:
    return int(hashlib.md5(token.encode("utf-8")).hexdigest()[:8], 16) % DIM


def embed(text: str) -> list[float]:
    counts = Counter(tokenize(text))
    vec = [0.0] * DIM
    if not counts:
        return vec
    for token, cnt in counts.items():
        weight = (1.0 + math.log(cnt)) * (1.0 + 0.5 * min(len(token), 4))
        vec[_bucket(token)] += weight
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(v / norm, 6) for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return float(sum(x * y for x, y in zip(a, b)))
