"""内容互动热度计算。"""

import math


def compute_content_hot_score(
    view_count: int = 0,
    like_count: int = 0,
    comment_count: int = 0,
    share_count: int = 0,
) -> float:
    """按单篇内容互动量计算 0-100 热度分。"""
    views = max(0, view_count or 0)
    likes = max(0, like_count or 0)
    comments = max(0, comment_count or 0)
    shares = max(0, share_count or 0)

    raw = (views * 0.001) + (likes * 0.4) + (comments * 1.2) + (shares * 1.5)
    if raw <= 0:
        return 0.0
    return round(min(100.0, math.log10(raw + 1) * 28), 1)
