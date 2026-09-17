"""静态基础工具:任何 Agent 请求都可用(天气/计算器/时间/公交)。

学习要点:@tool 的 docstring 是写给模型看的"使用说明书",
描述越精确(什么时候调、参数什么格式、不要做什么),工具调用准确率越高。
"""
import os
from datetime import datetime

import httpx
from langchain_core.tools import tool


@tool
async def get_weather(city: str) -> str:
    """当用户询问某个城市的实时天气时调用。
    city: 中文城市名,如 "北京"、"上海"、"杭州"。不要传省份或国家。"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            resp = await c.get(
                f"https://wttr.in/{city}",
                params={"format": "j1", "lang": "zh"},
            )
        if resp.status_code != 200:
            return f"天气查询失败(HTTP {resp.status_code}),请告知用户稍后重试或换个城市名"
        cur = resp.json()["current_condition"][0]
        desc = next(
            (x["value"] for x in cur.get("lang_zh", []) if x.get("value")),
            cur["weatherDesc"][0]["value"],
        )
        return (
            f"{city}当前天气:{desc},气温 {cur['temp_C']}℃"
            f"(体感 {cur['FeelsLikeC']}℃),湿度 {cur['humidity']}%,"
            f"风速 {cur['windspeedKmph']}km/h"
        )
    except Exception as e:
        # 返回可读错误让模型自行向用户解释,而不是让工具调用崩溃
        return f"天气查询出错:{e},请向用户说明情况"


@tool
def calculator(expression: str) -> str:
    """当需要精确计算数学表达式时调用(加减乘除、乘方、括号),
    不要用心算代替。expression: 如 "(3+5)*2" 或 "2**10"。"""
    import ast
    import operator

    ops = {
        ast.Add: operator.add, ast.Sub: operator.sub,
        ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            return ops[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = _eval(node.operand)
            return v if isinstance(node.op, ast.UAdd) else -v
        raise ValueError("不支持的表达式")

    try:
        result = _eval(ast.parse(expression, mode="eval"))
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算失败:{e},请检查表达式格式"


@tool
def get_current_time() -> str:
    """当需要确认当前确切的日期、时间、星期几时调用(如"今天是周几""现在几点")。"""
    now = datetime.now()
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    return (
        f"当前时间:{now.year}年{now.month}月{now.day}日 "
        f"星期{weekdays[now.weekday()]} {now.hour:02d}:{now.minute:02d}"
    )


@tool
async def query_bus_route(line: str, city: str) -> str:
    """当用户询问某条公交车/地铁线路的信息(途经站点、首末班时间、票价)时调用。
    line: 线路名,如 "118路"、"地铁2号线"。city: 中文城市名,如 "长沙"。
    注意:本工具只查单条线路的站点信息;用户问"从A到B怎么坐车"时不要用。"""
    api_key = os.getenv("AMAP_API_KEY")
    if not api_key:
        return ("公交查询功能未配置高德 AMAP_API_KEY,"
                "请提示管理员到高德开放平台(lbs.amap.com)申请 Web 服务 key"
                "并写入 ai-service/.env 后重启服务")

    def fmt_time(t: str) -> str:
        # 高德返回 "0600"/"2230" 格式,转成 "06:00"
        return f"{t[:2]}:{t[2:]}" if t and len(t) == 4 else (t or "未知")

    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            resp = await c.get(
                "https://restapi.amap.com/v3/bus/linename",
                params={
                    "key": api_key, "city": city,
                    "keywords": line, "extensions": "all",
                },
            )
        data = resp.json()
        if data.get("status") != "1":
            return f"公交查询失败:{data.get('info', '未知错误')},请向用户说明"
        lines = data.get("buslines", [])
        if not lines:
            return f"未在{city}找到线路「{line}」,请确认线路名是否正确(如 118路)"
        parts = []
        for bl in lines[:2]:  # 同名线路可能有上/下行两条,都列出
            stops = " → ".join(s["name"] for s in bl.get("busstops", []))
            parts.append(
                f"线路:{bl.get('name', line)}\n"
                f"首末站:{bl.get('start_stop', '?')} ↔ {bl.get('end_stop', '?')}\n"
                f"首末班:{fmt_time(bl.get('start_time', ''))} ~ {fmt_time(bl.get('end_time', ''))}\n"
                f"票价:{bl.get('total_price') or '未知'}元\n"
                f"途经站点:{stops or '无站点数据'}"
            )
        return "\n\n".join(parts)
    except Exception as e:
        # 返回可读错误让模型自行向用户解释,而不是让工具调用崩溃
        return f"公交查询出错:{e},请向用户说明情况"

# 静态工具:任何 Agent 请求都可用
BASE_TOOLS = [get_weather, calculator, get_current_time, query_bus_route]
