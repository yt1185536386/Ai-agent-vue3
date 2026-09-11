"""
firstagent.py —— 我的第一个完整 Agent(学习用,零项目依赖)

一个 Agent 的四个组成件,全部摊开在这个文件里:
  ① 大脑   ChatOpenAI(模型客户端)
  ② 手     @tool 装饰的工具函数
  ③ 神经   create_react_agent(LangGraph 编译出的 ReAct 循环)
  ④ 状态   MessagesState(循环中累积的消息列表)

与 ai-service/app/ 的关系:
  这个文件是把 app/agent.py 的 Agent 核心抽离出来的独立可运行版本,
  不经过 FastAPI/NestJS/数据库,直接在命令行和 Agent 对话。

运行:
  cd ai-service
  .venv/Scripts/python firstagent.py            # 交互模式,输入问题回车,quit 退出
  .venv/Scripts/python firstagent.py 长沙天气   # 单次提问
"""
import asyncio
import os
import sys
from datetime import datetime

import httpx
from dotenv import dotenv_values
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# 从 ai-service/.env 读取百炼来源配置(复用现有 key)
_env = dotenv_values(os.path.join(os.path.dirname(__file__), ".env"))

#============================================================
# 自定义一个function
#============================================================

@tool
def get_my_schedule() -> str:
    """当用户询问自己今天的日程安排时调用。"""
    return "晚 7点健身, 8点学习, 9点休息"

# ============================================================
# ② 手:工具(Agent 能"做"的事)
# ============================================================

@tool
async def get_weather(city: str) -> str:
    """当用户询问某个城市的实时天气时调用。
    city: 中文城市名,如 "北京"、"上海"。不要传省份或国家。"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            resp = await c.get(f"https://wttr.in/{city}",
                               params={"format": "j1", "lang": "zh"})
        cur = resp.json()["current_condition"][0]
        desc = next((x["value"] for x in cur.get("lang_zh", []) if x.get("value")),
                    cur["weatherDesc"][0]["value"])
        return (f"{city}当前天气:{desc},气温 {cur['temp_C']}℃"
                f"(体感 {cur['FeelsLikeC']}℃),湿度 {cur['humidity']}%")
    except Exception as e:
        return f"天气查询出错:{e},请向用户说明情况"


@tool
def calculator(expression: str) -> str:
    """当需要精确计算数学表达式时调用(加减乘除、乘方、括号)。
    expression: 如 "(3+5)*2" 或 "2**10"。"""
    import ast, operator
    ops = {ast.Add: operator.add, ast.Sub: operator.sub,
           ast.Mult: operator.mul, ast.Div: operator.truediv,
           ast.Pow: operator.pow, ast.Mod: operator.mod}

    def _eval(n):
        if isinstance(n, ast.Expression): return _eval(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)): return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in ops:
            return ops[type(n.op)](_eval(n.left), _eval(n.right))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            v = _eval(n.operand)
            return v if isinstance(n.op, ast.UAdd) else -v
        raise ValueError("不支持的表达式")

    try:
        return f"{expression} = {_eval(ast.parse(expression, mode='eval'))}"
    except Exception as e:
        return f"计算失败:{e}"


@tool
def get_current_time() -> str:
    """当需要确认当前确切的日期、时间、星期几时调用。"""
    now = datetime.now()
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    return (f"当前时间:{now.year}年{now.month}月{now.day}日 "
            f"星期{weekdays[now.weekday()]} {now.hour:02d}:{now.minute:02d}")


TOOLS = [get_weather, calculator, get_current_time, get_my_schedule]



# ============================================================
# ①+③:组装 Agent(大脑 + 神经循环)
# ============================================================

def build_first_agent():
    """大脑(ChatOpenAI) + 工具 → create_react_agent 编译出带循环的 Agent"""
    brain = ChatOpenAI(
        model="qwen-plus",
        api_key=_env.get("BAILIAN_MODEL_API_KEY", ""),
        base_url=_env.get("BAILIAN_MODEL_BASE_URL", "").rstrip("/"),
        temperature=0,
    )
    return create_react_agent(brain, TOOLS)


# ============================================================
# 跑道:驱动循环,把每一轮发生什么打印出来(学习用,比 SSE 直观)
# ============================================================

async def chat_once(agent, question: str):
    """问 Agent 一个问题,实时打印:工具调用过程 + 最终回答"""
    # ④ 状态:MessagesState 的初始内容——就是这一轮对话的起点
    state = {"messages": [HumanMessage(content=question)]}

    printed_answer = False
    async for event in agent.astream_events(state, version="v2"):
        kind = event["event"]
        if kind == "on_tool_start":
            print(f"\n⚙️  [工具调用] {event.get('name')}  参数: {event['data'].get('input')}")
        elif kind == "on_tool_end":
            out = event["data"].get("output")
            result = getattr(out, "content", out)
            print(f"✅ [工具返回] {str(result)[:200]}")
            print("─" * 50)
        elif kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            # 工具决策帧不打印,只打印真正的文字 token
            if not getattr(chunk, "tool_call_chunks", None):
                content = chunk.content
                if isinstance(content, str) and content:
                    if not printed_answer:
                        print("🤖 ", end="")
                        printed_answer = True
                    print(content, end="", flush=True)
    print("\n" + "═" * 60)


async def main():
    agent = build_first_agent()
    # 命令行带参数:单次提问
    if len(sys.argv) > 1:
        await chat_once(agent, " ".join(sys.argv[1:]))
        return
    # 交互模式
    print("firstagent 已启动(工具: 天气/计算/时间),输入问题回车,quit 退出")
    print("═" * 60)
    while True:
        try:
            q = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q or q.lower() in ("quit", "exit", "q"):
            break
        try:
            await chat_once(agent, q)
        except Exception as e:
            print(f"出错了: {e}")
    print("再见 👋")


if __name__ == "__main__":
    asyncio.run(main())
