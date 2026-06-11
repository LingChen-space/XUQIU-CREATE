"""文本相似度工具 — 用于重复提问检测。"""

import re
from collections import Counter
from math import sqrt


def tokenize(text: str) -> list[str]:
    """中文简易分词：按字符级 + 常见词切分。"""
    text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", " ", text.lower())
    # 2-gram 字符级
    chars = [c for c in text if c != " "]
    bigrams = ["".join(chars[i:i+2]) for i in range(len(chars)-1)]
    # 同时保留单字
    return chars + bigrams


def cosine_similarity(tokens1: list[str], tokens2: list[str]) -> float:
    """余弦相似度。"""
    if not tokens1 or not tokens2:
        return 0.0
    c1, c2 = Counter(tokens1), Counter(tokens2)
    all_tokens = set(c1.keys()) | set(c2.keys())
    dot = sum(c1.get(t, 0) * c2.get(t, 0) for t in all_tokens)
    norm1 = sqrt(sum(v**2 for v in c1.values()))
    norm2 = sqrt(sum(v**2 for v in c2.values()))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def detect_repeat_questions(texts: list[str], threshold: float = 0.75) -> float:
    """
    检测一批文本中重复提问的比例。
    返回 0-1 之间，值越高说明重复提问越密集。
    """
    n = len(texts)
    if n < 2:
        return 0.0
    
    tokenized = [tokenize(t) for t in texts]
    pair_count = 0
    similar_pairs = 0
    
    for i in range(n):
        for j in range(i + 1, n):
            pair_count += 1
            sim = cosine_similarity(tokenized[i], tokenized[j])
            if sim >= threshold:
                similar_pairs += 1
    
    if pair_count == 0:
        return 0.0
    return similar_pairs / pair_count
