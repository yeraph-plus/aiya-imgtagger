import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = lambda _: None

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

# 环境变量
API_KEY = os.getenv("API_KEY", "")
API_URL = os.getenv("API_URL", "https://api.openai.com/v1").rstrip("/")

# 预设标签模板存放目录
DATA_DIR = BASE_DIR / "data"

# 发送给 AI 前图片最大宽度（等比缩放）
MAX_IMAGE_WIDTH = 1000
# 发送给 AI 前图片 JPEG 压缩质量
JPEG_QUALITY = 85
# 单次 AI 请求最多发送的图片数
MAX_IMAGES_PER_REQUEST = 6

# 支持的图片扩展名
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}

# 预览时缩略图尺寸（px）
THUMB_SIZE = 180

# AI 预标签保存文件名
AI_TAGS_FILENAME = "ai_tags.json"
# 预加载的文件夹数量
PRELOAD_TASK_COUNT = 5
# 并发打标 AI Worker 数量
AGENT_WORKER_COUNT = 2

# 标签分类组定义
ALL_TAG_CATEGORIES = ["parody", "character", "artist", "female", "male", "general", "rating", "other"]

# 自由填写分类：无标签模板约束，AI Prompt 可自由输出
FREE_FORM_TAG_CATEGORIES = ["parody", "character", "artist"]

# 受限分类：AI Prompt只能在模板范围内选择（当前由预设标签模板返取约束）
CONSTRAINED_CATEGORIES = [c for c in ALL_TAG_CATEGORIES if c not in FREE_FORM_TAG_CATEGORIES]

# AI Prompt 标签规则列表
TAGGING_RULES = [
    "Only tag content clearly identifiable in the images. If uncertain, do not tag.",
    "Confidence calibration: 0.95 = definitively present, unambiguous; 0.85 = highly likely, minimal doubt; 0.7 = reasonably present, some ambiguity. Only output tags with confidence >= 0.7.",
    "Use lowercase with underscores for multi-word tags. When preset tags are provided, output the exact slugs from the list.",
    "General category should be comprehensive — tag as many visual features as possible (hair, eyes, body, accessories, clothing, composition, etc.).",
    "Rating category is mandatory — always output a rating tag.",
    "For freeform categories (parody, character, artist): identify freely if determinable. If not recognized, do not emit these categories.",
    "Tag overlap priority: female/male are exclusively for character archetypes (loli, shota, kemonomimi, etc.) and expressive/behavioral traits (smile, blush, looking_at_viewer, pose, expression). All visual traits (hair color, eye color, body type, accessories, clothing, composition) always belong in general.",
    "Capture the diversity of the image set. If a tag appears in only some images (e.g. both day and night settings exist), include both.",
]

# AI Prompt 分类的目标说明列表
CATEGORY_PURPOSES = [
    "parody: identify the source work or franchise",
    "character: identify character names",
    "artist: identify the artist, cosplayer, photographer, or content creator (real names / social media handles allowed)",
    "female: female character archetypes (loli, mature, etc.) and expressive/behavioral traits (smile, blush, pose, expression)",
    "male: male character archetypes (shota, bishounen, etc.) and expressive/behavioral traits (smile, blush, pose, expression)",
    "general: visual traits — hair, eyes, body features, accessories, clothing, composition",
    "rating: content safety level (safe, questionable, explicit)",
    "other: technical and meta qualities — resolution, framing, environment, medium",
]

# Gallery 最终产物元数据文件名
GALLERY_INFO_FILENAME = "info.json"

# Gallery 最终产物类型主分类
GALLERY_CATEGORIES = ["doujinshi", "manga", "imageset", "cosplay", "misc", "private"]
