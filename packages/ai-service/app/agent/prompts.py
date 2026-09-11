"""系统提示词层:时间注入 + 业务规则注册表。

规则可插拔:业务模块通过 register_rules()
登记自己的对话规则,agent_system_prompt() 组合「当前时间 + 全部规则块」。
新增业务领域时不需要改这里。
"""
from datetime import datetime

# 有序规则注册表:key 为领域名,value 为规则文本(注册顺序即拼接顺序)
_RULE_BLOCKS: dict[str, str] = {}

# ---- 可选注入点(裸钩子,默认 None = 维持现状;harness 不 import 业务模块)----
# 模板加载器: (key: str) -> str | None,返回 None 用代码默认拼装;
#             agent.py 启动时注入 prompteng.service.load_content
_TEMPLATE_LOADER = None
# 装配观测器: (event: dict) -> None,装配完成后回调;事件结构见 contexteng.events.PromptAssembly
_PROMPT_OBSERVER = None


def set_template_loader(fn) -> None:
    """注入模板加载器(同步、无 IO);None 恢复代码默认"""
    global _TEMPLATE_LOADER
    _TEMPLATE_LOADER = fn


def set_prompt_observer(fn) -> None:
    """注入装配观测器;None 关闭观测"""
    global _PROMPT_OBSERVER
    _PROMPT_OBSERVER = fn


def register_rules(key: str, text: str) -> None:
    """登记一个业务领域的对话规则块(重复登记同 key 会覆盖)"""
    _RULE_BLOCKS[key] = text


def registered_rules() -> dict[str, str]:
    """返回当前已登记的规则块(拷贝),供调试/eval 检视"""
    return dict(_RULE_BLOCKS)


def _now_text() -> str:
    now = datetime.now()
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    return (
        f"当前真实时间:{now.year}年{now.month}月{now.day}日 "
        f"星期{weekdays[now.weekday()]} {now.hour:02d}:{now.minute:02d}。"
    )


def agent_system_prompt() -> str:
    """Agent 每轮决策前置的系统提示:时间 + 各领域规则。

    只在 agent_node 调用模型时临时前置,不进图状态,
    避免每轮往 checkpoint 里追加一条、越积越多。

    DB 模板('agent.system',变量 {{time}} / {{rules}})激活时优先用模板渲染,
    否则回退代码默认拼装;装配完成后回调观测器(失败静默,绝不影响主链路)。"""
    rules_text = "\n\n".join(_RULE_BLOCKS.values())
    now = _now_text()
    source, content = "code", None
    if _TEMPLATE_LOADER:
        try:
            tpl = _TEMPLATE_LOADER("agent.system")
            if tpl:
                content = tpl.replace("{{time}}", now).replace("{{rules}}", rules_text)
                source = "db"
        except Exception:
            content = None  # 加载器异常一律回退代码默认
    if content is None:
        parts = [now]
        if rules_text:
            parts.append(rules_text)
        content = "\n\n".join(parts)
    if _PROMPT_OBSERVER:
        try:
            _PROMPT_OBSERVER({
                "template_key": "agent.system",
                "version": 0,  # 由观测器实现方(load_content 提供方)自行补全
                "source": source,
                "content_len": len(content),
            })
        except Exception:
            pass  # 观测失败绝不影响主链路
    return content


def time_system_message() -> dict:
    """注入当前服务器时间,纠正网关/模型自带的错误日期(直答路径用)"""
    return {
        "role": "system",
        "content": _now_text() + "回答与日期、时间、最新信息相关的问题时以此为准。",
    }
