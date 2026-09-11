"""展示轨道持久化:messages 表是前端气泡的唯一权威。

- display.py  用户/助手消息落库(fail-soft) + regenerate 截断(显式报错) + 老会话回填投影

从哪里入手学习:先看模块 docstring 的「双轨制」设计,再对照 agent/loop.py 的 checkpoint 理解两轨分工。
"""
