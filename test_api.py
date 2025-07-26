import os
from dotenv import load_dotenv
from openai import OpenAI
from openai import APIConnectionError, APIError

# 加载环境变量
load_dotenv()

try:
    # 初始化OpenAI客户端（完全移除代理相关代码）
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("BASE_URL", "https://api.openai.com/v1")
    )
    
    # 检查必要的环境变量
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("请设置 OPENAI_API_KEY 环境变量")
    
    # 获取模型名称
    model = os.getenv("MODEL", "gpt-3.5-turbo")
    
    print(f"正在使用模型: {model}")
    
    # 发送请求
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是一个乐于助人的助手。"},
            {"role": "user", "content": "你好，世界！今天的日期是？"},
        ],
    )
    
    # 打印回复
    print("\nAI回复:")
    print(response.choices[0].message.content)

except ValueError as e:
    print(f"配置错误: {str(e)}")
except APIConnectionError as e:
    print(f"连接失败: {str(e)}")
except APIError as e:
    print(f"API错误: {str(e)}")
except Exception as e:
    print(f"未知错误: {str(e)}")