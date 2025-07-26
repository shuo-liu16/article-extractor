import os
import json
import re
from openai import OpenAI
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
import datetime


# 配置日志系统
def setup_logging():
    # 创建日志目录（如果不存在）
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    # 创建按日期命名的日志文件
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    log_file = f"{log_dir}/vocabulary_extractor_{current_date}.log"

    # 设置日志格式
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)

    # 配置日志处理器
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,  # 5MB per file, keep 3 backups
    )
    file_handler.setFormatter(formatter)

    # 也可以添加控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # 获取根日志器并配置
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# 初始化日志
logger = setup_logging()
log_level = os.getenv("LOG_LEVEL", "INFO")
logger.setLevel(getattr(logging, log_level))
# 加载环境变量
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("BASE_URL"))


def extract_vocabulary(article, difficulty="medium"):
    """
    从英文文章中提取词汇（单词、词性、释义）
    """
    # 清理文章文本
    clean_article = clean_text(article)

    logger.info(f"开始提取词汇 - 难度级别: {difficulty}")
    logger.debug(f"清理后文章内容:\n{clean_article[:500]}...")

    # 构造系统提示词
    system_prompt = build_system_prompt(difficulty)

    try:
        logger.info("调用OpenAI API...")
        response = client.chat.completions.create(
            model=os.getenv("MODEL", "gpt-3.5-turbo"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"## 需要分析的英文文章:\n{clean_article}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=1500,
        )

        # 详细的响应验证
        if response is None:
            logger.error("API返回了None响应")
            return []

        if not hasattr(response, "choices") or not response.choices:
            logger.error("API响应中没有choices字段或choices为空")
            return []

        first_choice = response.choices[0]
        if not hasattr(first_choice, "message") or first_choice.message is None:
            logger.error("第一个choice中没有message字段或message为None")
            return []

        if (
            not hasattr(first_choice.message, "content")
            or not first_choice.message.content
        ):
            logger.error("message中没有content字段或content为空")
            return []

        result = first_choice.message.content
        vocab_data = parse_vocabulary_response(result)

        if not vocab_data:
            logger.warning("解析后的词汇列表为空")

        return vocab_data

    except Exception as e:
        logger.error(f"API调用过程中发生异常: {str(e)}", exc_info=True)
        return []


def clean_text(text):
    """清理文本中的特殊字符"""
    # 移除HTML标签
    clean = re.sub(r"<[^>]+>", "", text)
    # 移除多余的空格和换行
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def build_system_prompt(difficulty):
    """构造系统提示词"""
    difficulty_desc = {
        "basic": "基础词汇（cet4文章中值得注意的词汇）",
        "medium": "中级词汇（cet6文章中值得注意的词汇）",
        "advanced": "高级/学术词汇（IELTS/TOEFL/GRE文章中值得注意的词汇）",
    }.get(difficulty, "medium")

    example_output = {
        "vocabulary": [
            {
                "word": "extract",
                "pos": ".v",
                "definition": "to remove or take out something",
                "definition-ch": "提取；摘录（文中指从样本中分离物质）",
                "common-usage": [
                    "extract data from reports",
                    "plant extracts used in medicine",
                ],
                "type": "word"
            },
            {
                "word": "paradigm shift",
                "pos": ".n",
                "definition": "a fundamental change in approach or underlying assumptions",
                "definition-ch": "范式转换；根本性转变",
                "common-usage": [
                    "the paradigm shift in technology",
                    "scientific paradigm shift",
                ],
                "type": "phrase"
            },
            {
                "word": "breakthrough",
                "pos": ".n",
                "definition": "an important discovery or development",
                "definition-ch": "突破；重大发现",
                "common-usage": [
                    "scientific breakthrough",
                    "technological breakthrough",
                ],
                "type": "word"
            },
            {
                "word": "take into account",
                "pos": ".v",
                "definition": "to consider something when making a decision",
                "definition-ch": "考虑；把...考虑在内",
                "common-usage": [
                    "take into account all factors",
                    "must take into account the cost",
                ],
                "type": "phrase"
            },
        ]
    }

    return f"""
    ## 角色
    你是专业的英语词汇分析助手，擅长从文本中智能识别和提取值得注意的单词和词组。
    
    ## 任务
    1. 分析用户提供的英文文章
    2. 智能识别并提取符合要求的单词和词组：{difficulty_desc}
    3. 为每个词汇项提供：
       - 词汇 (word): 单词或词组（2-4个单词的常用搭配）
       - 词性 (pos): 使用缩写 (.n/.v/.adj/.adv/.prep/.conj/.pron等)
       - 中文释义 (definition-ch): 简洁准确
       - 英文释义 (definition): 简洁准确，不超过15个单词
       - 常见用法 (common-usage): 为了加深印象(1-2个例子)
       - 类型 (type): "word"表示单词，"phrase"表示词组
    
    ## 智能识别策略
    ### 单词识别：
    - 优先选择：专业术语、学术词汇、生动表达、非常用词汇
    - 排除：超高频基础词汇 (the, a, is, etc.)
    - 排除：人名、地名等专有名词（除非有特殊含义）
    
    ### 词组识别：
    - 动词短语：take into account, come up with, look forward to, get along with
    - 名词短语：paradigm shift, breakthrough discovery, cutting edge technology
    - 形容词短语：well-known, state-of-the-art, up-to-date, user-friendly
    - 介词短语：in terms of, with regard to, as a result of, in light of
    - 习语和表达：idioms, phrasal verbs, collocations
    - 学术表达：学术写作中常用的词组搭配
    
    ## 提取原则
    1. 自动识别：根据文章内容自动判断是单词还是词组
    2. 混合输出：单词和词组混合输出，比例为单词:词组 = 2:1
    3. 质量优先：优先提取有学习价值的词汇，避免过于简单或过于复杂的词汇
    4. 上下文相关：确保提取的词汇在文章中有实际意义
    
    ## 输出格式
    {json.dumps(example_output, indent=4, ensure_ascii=False)}
    * 只包含JSON内容，不包含任何额外文本！
    * 确保单词和词组是原文中出现的实际拼写
    * 智能混合输出单词和词组，无需用户指定
    """


def parse_vocabulary_response(response):
    """解析API响应为词汇列表"""
    try:
        # 尝试解析JSON
        data = json.loads(response)

        # 验证数据结构
        if not isinstance(data, dict) or "vocabulary" not in data:
            logger.warning(f"响应缺少 'vocabulary' 字段: {response[:200]}...")
            return []

        vocab_list = data["vocabulary"]
        logger.debug(f"原始解析到 {len(vocab_list)} 个词汇项")

        # 验证每个词汇项
        valid_vocab = []
        for item in vocab_list:
            # 检查必需字段
            if not all(key in item for key in ["word", "pos", "definition"]):
                missing = [
                    key for key in ["word", "pos", "definition"] if key not in item
                ]
                logger.warning(f"词汇项缺少必需字段 {missing}: {item}")
                continue

            # 规范化词性标签
            item["pos"] = item["pos"].lower().strip()

            # 确保可选字段存在
            item.setdefault("definition-ch", "暂无中文释义")
            item.setdefault("common-usage", [])
            item.setdefault("type", "word")  # 默认为单词类型

            # 确保 common-usage 是列表
            if not isinstance(item["common-usage"], list):
                if isinstance(item["common-usage"], str):
                    item["common-usage"] = [item["common-usage"]]
                else:
                    item["common-usage"] = []

            # 验证类型字段
            if item["type"] not in ["word", "phrase"]:
                item["type"] = "word"  # 默认为单词

            valid_vocab.append(item)

        logger.info(f"成功解析 {len(valid_vocab)} 个有效词汇项")
        return valid_vocab

    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败: {e}")
        logger.debug(f"原始响应: {response[:500]}...")
        return []
    except Exception as e:
        logger.error(f"解析响应时发生未知错误: {e}")
        return []


if __name__ == "__main__":
    article = "B Macfarlane compares the puzzle to a combination lock, ‘There are about 20 different factors and all of them need to be present before the revolution can happen,’ he says. For industry to take off, there needs to be the technology and power to drive factories, large urban populations to provide cheap labour, easy transport to move goods around, an affluent middle-class willing to buy mass-produced objects, a market-driven economy and a political system that allows this to happen. While this was the case for England, other nations, such as Japan, the Netherlands and France also met some of these criteria but were not industrialising. ‘All these factors must have been necessary but not sufficient to cause the revolution,’ says Macfarlane. ‘After all, Holland had everything except coal, while China also had many of these factors. Most historians are convinced there are one or two missing factors that you need to open the lock."

    extract_vocabulary(article, "advanced")
