"""测试 AI 接入是否正常"""
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# 加载 .env 配置
from dotenv import load_dotenv
load_dotenv(project_root / ".env", override=True)

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_ai_connection():
    """测试 AI API 连接"""
    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    base_url = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    model = os.getenv("DASHSCOPE_MODEL", "qwen/qwen3.5-flash")
    timeout = int(os.getenv("DASHSCOPE_TIMEOUT", "30"))

    print("\n=== AI 配置信息 ===")
    print(f"API Key: {api_key[:8]}...{api_key[-4:] if len(api_key) > 12 else '***'}")
    print(f"Base URL: {base_url}")
    print(f"Model: {model}")
    print(f"Timeout: {timeout}s")
    print()

    if not api_key:
        print("X 错误：未设置 DASHSCOPE_API_KEY")
        print("请在 .env 文件中设置：")
        print("DASHSCOPE_API_KEY=sk-your-key-here")
        return False

    print(">> 正在测试 AI 连接...")
    try:
        from src.ai_extract import _get_client
        client = _get_client()
        print("OK AI 客户端创建成功")

        print(">> 正在测试实际请求...")
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "请回复'连接成功'"}],
            max_tokens=50,
        )

        result = response.choices[0].message.content
        print(f"OK AI 返回：{result}")
        return True

    except Exception as exc:
        print(f"X AI 连接失败：{exc}")
        print("\n可能的问题：")
        print("1. 网络连接问题 - 请检查网络设置")
        print("2. API Key 无效或过期 - 请检查密钥")
        print("3. 代理设置问题 - 如需代理请设置 HTTP_PROXY/HTTPS_PROXY")
        print("4. API 额度用完 - 请检查阿里云 dashscope 控制台")
        return False

if __name__ == "__main__":
    success = test_ai_connection()
    sys.exit(0 if success else 1)
