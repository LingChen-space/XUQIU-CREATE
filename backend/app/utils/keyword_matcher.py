"""关键词匹配工具 — 检测资格稀缺等信号。"""

import re


# 资格/稀缺信号关键词
SCARCITY_KEYWORDS = [
    "限量", "资格", "抢码", "体验服", "测试资格", "内测", "先到先得",
    "激活码", "邀请码", "预约", "名额有限", "先抢先得", "限量发放",
    "抢号", "封测", "删档测试", "不删档", "公测资格",
]

# 民间工具检测关键词
GRASSROOTS_TOOL_KEYWORDS = [
    "计算器", "excel", "表格", "在线文档", "腾讯文档", "飞书文档",
    "石墨文档", "自制", "自研", "做了个", "写了个", "搞了个",
    "网页版", "小程序", "H5", "工具", "模拟器",
]

GRASSROOTS_TOOL_URL_PATTERNS = [
    r"https?://docs\.qq\.com",
    r"https?://kdocs\.cn",
    r"https?://shimo\.im",
    r"https?://feishu\.cn",
    r"https?://github\.com",
    r"https?://gitee\.com",
]

TOOL_PRODUCT_KEYWORDS = [
    "工具", "计算器", "模拟器", "地图", "助手", "查询", "工具箱",
    "小程序", "网页版", "app", "h5",
]

TOOL_LAUNCH_KEYWORDS = [
    "上线", "已上线", "正式上线", "发布", "开放使用", "可使用",
    "入口", "官网", "下载", "链接", "地址", "获取教程",
]


def count_keyword_hits(text: str, keywords: list[str]) -> int:
    """统计文本中关键词命中次数。"""
    text_lower = text.lower()
    count = 0
    for kw in keywords:
        count += len(re.findall(re.escape(kw.lower()), text_lower))
    return count


def detect_scarcity_signal(texts: list[str]) -> tuple[float, list[str]]:
    """
    检测资格稀缺信号。
    返回 (信号强度 0-1, 命中的关键词列表)。
    """
    if not texts:
        return 0.0, []
    
    total_hits = 0
    hit_keywords = set()
    
    for text in texts:
        for kw in SCARCITY_KEYWORDS:
            cnt = len(re.findall(re.escape(kw), text))
            if cnt > 0:
                total_hits += cnt
                hit_keywords.add(kw)
    
    # 归一化：命中文章比例 * 命中关键词覆盖度
    hit_article_ratio = sum(1 for t in texts if count_keyword_hits(t, SCARCITY_KEYWORDS) > 0) / len(texts)
    keyword_coverage = len(hit_keywords) / len(SCARCITY_KEYWORDS)
    
    strength = (hit_article_ratio * 0.6 + keyword_coverage * 0.4)
    return min(strength, 1.0), list(hit_keywords)


def detect_grassroots_tools(texts: list[str], urls: list[str]) -> tuple[float, list[str]]:
    """
    检测民间工具萌芽信号。
    返回 (信号强度 0-1, 匹配到的证据)。
    """
    if not texts:
        return 0.0, []
    
    evidence = []
    
    # 关键词匹配
    for text in texts:
        for kw in GRASSROOTS_TOOL_KEYWORDS:
            if kw.lower() in text.lower():
                evidence.append(f"关键词「{kw}」命中")
                break
    
    # URL 模式匹配
    for url in urls:
        for pattern in GRASSROOTS_TOOL_URL_PATTERNS:
            if re.search(pattern, url):
                evidence.append(f"工具链接 {url[:60]}...")
                break
    
    # 强度 = 有证据的文本比例
    if len(texts) == 0:
        return 0.0, evidence
    
    evidence_count = len(set(evidence))
    strength = min(evidence_count / max(len(texts), 1) * 5, 1.0)
    return strength, evidence[:10]  # 最多返回10条证据


def detect_external_platform_tools(texts: list[str], urls: list[str]) -> tuple[float, list[str]]:
    """
    检测外部平台同类工具是否已经上线。
    返回 (信号强度 0-1, 匹配到的证据)。
    """
    evidence = []
    if not texts and not urls:
        return 0.0, evidence

    text_count = max(len(texts), 1)
    for text in texts:
        lowered = text.lower()
        has_tool = any(kw.lower() in lowered for kw in TOOL_PRODUCT_KEYWORDS)
        has_launch = any(kw.lower() in lowered for kw in TOOL_LAUNCH_KEYWORDS)
        if has_tool and has_launch:
            hit = next((kw for kw in TOOL_LAUNCH_KEYWORDS if kw.lower() in lowered), "上线")
            evidence.append(f"上线语义「{hit}」命中")

    for url in urls:
        if re.match(r"https?://", url or ""):
            evidence.append(f"外部工具链接 {url[:60]}...")

    text_strength = min(1.0, len([e for e in evidence if "上线语义" in e]) / text_count * 2)
    url_strength = 0.3 if any("外部工具链接" in e for e in evidence) else 0.0
    strength = min(1.0, text_strength * 0.7 + url_strength)
    return strength, evidence[:10]
