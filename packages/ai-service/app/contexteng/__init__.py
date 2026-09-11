"""Context 工程模块(现场记录者)。

负责 Context 的观测与记录:检索事件、context 快照、召回/利用率指标、
评测用例回收。第一阶段只观测不干预(不改变 context 内容)。

表前缀 cx_*,与 pe_* / documents / chunks 零跨域外键(拆服务前提)。
"""
