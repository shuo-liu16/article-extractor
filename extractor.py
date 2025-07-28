import os
import json
import re
import hashlib
import datetime
import logging
from functools import lru_cache
from typing import List
from dotenv import load_dotenv
from openai import OpenAI
from logging.handlers import RotatingFileHandler

# ====================== 配置和常量 ======================
# 最先加载环境变量
load_dotenv()


# 配置类
class Config:
    MODEL = os.getenv("MODEL", "gpt-3.5-turbo")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", 2500))
    TEMPERATURE = float(os.getenv("TEMPERATURE", 0.7))
    API_KEY = os.getenv("OPENAI_API_KEY")
    BASE_URL = os.getenv("BASE_URL")
    LOG_DIR = os.getenv("LOG_DIR", "logs")
    CACHE_SIZE = int(os.getenv("CACHE_SIZE", 100))
    WORDS_PER_SEGMENT = int(os.getenv("WORDS_PER_SEGMENT", 200))
    MIN_SEGMENT_WORDS = int(os.getenv("MIN_SEGMENT_WORDS", 50))


# 词性映射表
POS_MAPPING = {
    # 名词
    "n": ".n",
    "noun": ".n",
    "substantive": ".n",
    ".n": ".n",
    # 动词
    "v": ".v",
    "verb": ".v",
    "vb": ".v",
    ".v": ".v",
    # 形容词
    "adj": ".adj",
    "adjective": ".adj",
    "a": ".adj",
    ".adj": ".adj",
    # 副词
    "adv": ".adv",
    "adverb": ".adv",
    "ad": ".adv",
    ".adv": ".adv",
    # 介词
    "prep": ".prep",
    "preposition": ".prep",
    "pr": ".prep",
    ".prep": ".prep",
    # 连词
    "conj": ".conj",
    "conjunction": ".conj",
    "cj": ".conj",
    ".conj": ".conj",
    # 代词
    "pron": ".pron",
    "pronoun": ".pron",
    "pn": ".pron",
    ".pron": ".pron",
    # 限定词
    "det": ".det",
    "determiner": ".det",
    "dt": ".det",
    ".det": ".det",
    # 数词
    "num": ".num",
    "numeral": ".num",
    "number": ".num",
    ".num": ".num",
    # 感叹词
    "intj": ".intj",
    "interjection": ".intj",
    "interj": ".intj",
    ".intj": ".intj",
    # 默认名词
    "": ".n",
    None: ".n",
}


# ====================== 日志系统 ======================
def setup_logging():
    """配置日志系统"""
    # 创建日志目录
    os.makedirs(Config.LOG_DIR, exist_ok=True)

    # 创建按日期命名的日志文件
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    log_file = f"{Config.LOG_DIR}/vocabulary_extractor_{current_date}.log"

    # 设置日志格式
    log_format = "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    formatter = logging.Formatter(log_format)

    # 配置文件处理器
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
    )
    file_handler.setFormatter(formatter)

    # 配置控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # 获取根日志器并配置
    logger = logging.getLogger()
    logger.setLevel(Config.LOG_LEVEL)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# 初始化日志
logger = setup_logging()
logger.info("Application started")
logger.info(f"Configuration: MODEL={Config.MODEL}, LOG_LEVEL={Config.LOG_LEVEL}")


# ====================== 文本处理工具 ======================
def clean_text(text: str) -> str:
    """清理文本中的特殊字符和多余空格"""
    # 移除HTML标签
    clean = re.sub(r"<[^>]+>", "", text)
    # 移除URLs
    clean = re.sub(r"http[s]?://\S+", "", clean)
    # 移除多余的空格和换行
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def split_by_word_count(
    text: str, words_per_segment: int, min_segment_words: int
) -> List[str]:
    """
    按单词数量分割文本，同时保证段落完整性

    参数:
        text (str): 输入文本
        words_per_segment (int): 目标每段单词数
        min_segment_words (int): 最小段落单词数（避免过短段落）

    返回:
        List[str]: 分割后的段落列表
    """
    # 基础清理
    text = clean_text(text)

    # 按句子初步分割（保留分割符）
    sentences = re.split(r"(?<=[.!?])\s+", text)
    segments = []
    current_segment = []
    current_word_count = 0

    for sentence in sentences:
        words = sentence.split()
        sentence_word_count = len(words)

        # 如果当前段落加上新句子不会超过限制，或段落为空
        if (
            current_word_count + sentence_word_count <= words_per_segment
        ) or not current_segment:
            current_segment.append(sentence)
            current_word_count += sentence_word_count
        else:
            # 完成当前段落
            segments.append(" ".join(current_segment))

            # 开始新段落
            current_segment = [sentence]
            current_word_count = sentence_word_count

    # 添加最后一段
    if current_segment:
        segments.append(" ".join(current_segment))

    # 合并过短段落
    merged_segments = []
    buffer = []
    buffer_word_count = 0

    for seg in segments:
        seg_words = seg.split()
        seg_word_count = len(seg_words)

        if buffer_word_count + seg_word_count < min_segment_words:
            buffer.append(seg)
            buffer_word_count += seg_word_count
        else:
            if buffer:
                merged_segments.append(" ".join(buffer))
                buffer = []
                buffer_word_count = 0
            merged_segments.append(seg)

    if buffer:
        merged_segments.append(" ".join(buffer))

    return merged_segments


def normalize_pos(pos: str) -> str:
    """规范化词性标签"""
    if not pos:
        return ".n"

    # 清理和标准化输入
    pos = pos.lower().strip().replace(" ", "")

    # 检查是否已经是标准格式
    if pos in POS_MAPPING.values():
        return pos

    # 映射到标准格式
    return POS_MAPPING.get(pos, ".n")


# ====================== 核心词汇提取功能 ======================
def build_system_prompt(difficulty: str) -> str:
    """构造系统提示词"""
    difficulty_desc = {
        "basic": "基础词汇（CET4文章中值得注意的词汇）",
        "medium": "中级词汇（CET6文章中值得注意的词汇）",
        "advanced": "高级/学术词汇（IELTS/TOEFL/GRE文章中值得注意的词汇）",
    }.get(difficulty, "medium")

    example_output = {
        "vocabulary": [
            {
                "word": "extract",
                "pos": ".v",
                "definition": "to remove or take out something",
                "definition-ch": "提取；摘录",
                "common-usage": [
                    "extract data from reports",
                    "plant extracts used in medicine",
                ],
                "type": "word",
            },
            {
                "word": "paradigm shift",
                "pos": ".n",
                "definition": "a fundamental change in approach",
                "definition-ch": "范式转换；根本性转变",
                "common-usage": [
                    "the paradigm shift in technology",
                    "scientific paradigm shift",
                ],
                "type": "phrase",
            },
        ]
    }

    return f"""
    ## 角色
    你是专业的英语词汇分析助手，擅长从文本中智能识别和提取值得注意的单词和词组（每段都提取）。
    
    ## 任务
    1. 分析用户提供的英文文章
    2. 智能识别并提取符合要求的单词和词组（每段都提取）：{difficulty_desc}
    3. 为每个词汇项提供：
       - 词汇 (word): 单词或词组（2-4个单词的常用搭配）
       - 词性 (pos): 使用标准缩写 (.n/.v/.adj/.adv/.prep/.conj/.pron等)
       - 中文释义 (definition-ch): 简洁准确
       - 英文释义 (definition): 简洁准确，不超过15个单词
       - 常见用法 (common-usage): 1-2个例子
       - 类型 (type): "word"表示单词，"phrase"表示词组
    
    ## 智能识别策略
    ### 单词识别：
    - 优先选择：专业术语、学术词汇、生动表达、非常用词汇
    - 排除：超高频基础词汇 (the, a, is, etc.)
    - 排除：人名、地名等专有名词（除非有特殊含义）
    
    ### 词组识别：
    - 动词短语：take into account, come up with
    - 名词短语：paradigm shift, cutting edge technology
    - 形容词短语：well-known, state-of-the-art
    - 介词短语：in terms of, with regard to
    - 习语和表达：idioms, phrasal verbs
    - 学术表达：学术写作常用搭配
    
    ## 提取原则
    1. 自动识别：根据内容判断单词/词组
    2. 混合输出：单词:词组 ≈ 2:1
    3. 质量优先：优先提取有学习价值的词汇
    4. 上下文相关：确保词汇在文章中有实际意义
    
    ## 输出格式
    {json.dumps(example_output, indent=4, ensure_ascii=False)}
    * 只包含JSON内容，不包含任何额外文本！
    * 确保单词和词组是原文中出现的实际拼写
    """


def parse_vocabulary_response(response: str) -> List[dict]:
    """解析API响应为词汇列表"""
    try:
        # 尝试解析JSON
        data = json.loads(response)

        # 验证数据结构
        if not isinstance(data, dict) or "vocabulary" not in data:
            logger.warning(f"响应缺少 'vocabulary' 字段")
            return []

        vocab_list = data["vocabulary"]
        logger.debug(f"原始解析到 {len(vocab_list)} 个词汇项")

        # 验证每个词汇项
        valid_vocab = []
        for item in vocab_list:
            # 检查必需字段
            required_keys = ["word", "pos", "definition"]
            if not all(key in item for key in required_keys):
                missing = [key for key in required_keys if key not in item]
                logger.warning(f"词汇项缺少字段 {missing}: {item.get('word', '未知')}")
                continue

            # 规范化词性标签
            item["pos"] = normalize_pos(item["pos"])

            # 确保可选字段存在
            item.setdefault("definition-ch", "")
            item.setdefault("common-usage", [])
            item.setdefault("type", "word")

            # 确保 common-usage 是列表
            if not isinstance(item["common-usage"], list):
                if isinstance(item["common-usage"], str):
                    item["common-usage"] = [item["common-usage"]]
                else:
                    item["common-usage"] = []

            # 截断过长的释义
            if len(item["definition"]) > 100:
                item["definition"] = item["definition"][:97] + "..."

            # 验证类型字段
            if item["type"] not in ["word", "phrase"]:
                item["type"] = "word"

            valid_vocab.append(item)

        logger.info(f"验证后保留 {len(valid_vocab)} 个有效词汇项")
        return valid_vocab

    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败: {e.msg}")
        logger.debug(f"错误位置: {e.lineno}:{e.colno}, 原始响应: {response[:200]}...")
        return []
    except Exception as e:
        logger.error(f"解析响应时出错: {str(e)}", exc_info=True)
        return []


# 初始化OpenAI客户端（放在依赖函数之后）
client = OpenAI(api_key=Config.API_KEY, base_url=Config.BASE_URL)


@lru_cache(maxsize=Config.CACHE_SIZE)
def extract_vocabulary(article: str, difficulty: str = "medium") -> List[dict]:
    """
    从英文文章中提取词汇（单词、词性、释义）
    使用缓存避免重复处理相同内容
    """
    # 清理文章文本
    clean_article = clean_text(article)

    # 创建内容哈希作为缓存键
    content_hash = hashlib.md5(f"{clean_article}-{difficulty}".encode()).hexdigest()
    logger.info(f"开始提取词汇 - 难度: {difficulty}, 内容哈希: {content_hash[:8]}")

    # 构造系统提示词
    system_prompt = build_system_prompt(difficulty)

    try:
        logger.info("调用OpenAI API...")
        response = client.chat.completions.create(
            model=Config.MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"## 需要分析的英文文章:\n{clean_article}"},
            ],
            response_format={"type": "json_object"},
            temperature=Config.TEMPERATURE,
            max_tokens=Config.MAX_TOKENS,
        )

        # 验证API响应
        if not response or not response.choices:
            logger.error("API返回无效响应")
            return []

        first_choice = response.choices[0]
        if not first_choice.message or not first_choice.message.content:
            logger.error("API响应缺少内容")
            return []

        result = first_choice.message.content
        vocab_data = parse_vocabulary_response(result)

        logger.info(f"成功提取 {len(vocab_data)} 个词汇项")
        return vocab_data

    except Exception as e:
        logger.error(f"API调用失败: {str(e)}", exc_info=True)
        return []


# ====================== 高级功能接口 ======================
def extract_by_paragraphs(text: str, difficulty: str = "medium") -> List[dict]:
    """
    分段处理文章并合并结果
    返回包含段落标记的词汇列表
    """
    paragraphs = split_by_word_count(text, Config.WORDS_PER_SEGMENT, Config.MIN_SEGMENT_WORDS)
    all_vocab = []
    logger.info(f"开始分段处理，共 {len(paragraphs)} 个段落")

    for idx, para in enumerate(paragraphs, 1):
        logger.info(f"处理第 {idx}/{len(paragraphs)} 段落 (长度: {len(para)} 字符)")
        vocab_list = extract_vocabulary(para, difficulty)

        # 添加段落标记
        for item in vocab_list:
            item["paragraph"] = idx

        all_vocab.extend(vocab_list)

    logger.info(f"处理完成，共提取 {len(all_vocab)} 个词汇项")
    return all_vocab


def save_vocabulary_to_file(
    vocab_list: List[dict], filename: str = "vocabulary.json"
) -> bool:
    """将词汇列表保存到JSON文件"""
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(vocab_list, f, ensure_ascii=False, indent=2)
        logger.info(f"词汇表已保存到 {filename}")
        return True
    except Exception as e:
        logger.error(f"保存文件失败: {str(e)}")
        return False


# ====================== 主入口 ======================
if __name__ == "__main__":
    logger.info("词汇提取器已启动")
    print("请直接调用 extract_by_paragraphs() 函数或创建测试脚本")
