import httpx
from openai import OpenAI

http_client = httpx.Client(timeout=30.0, verify=False)
client = OpenAI(
    api_key="sk-1e9543d6293149edb37b2d95b994b6c7",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    http_client=http_client,
)
for model in ["qwen-flash", "qwen3.5-flash", "qwen-3.5-flash"]:
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "1+1="}],
            max_tokens=10,
            temperature=0.1,
        )
        print(f"{model}: OK -> {resp.choices[0].message.content}")
    except Exception as e:
        err_msg = str(e)
        print(f"{model}: FAIL -> {err_msg[:200]}")
