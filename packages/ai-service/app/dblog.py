"""MySQL 运行日志:把本服务日志批量写入 log_ai_service 表。

设计要点:
- 独立守护线程 + 有界队列,emit 永不阻塞请求、永不抛异常(日志失败不能影响业务)
- 复用 DATABASE_URL 连接信息(mysql+aiomysql://... 改用 pymysql 同步驱动);
  非 MySQL(如 sqlite 兜底)时直接跳过,不落库
- 表不存在时自动建,与 log_nestjs(NestJS)、log_model_gateway(Java 网关)保持同构
"""

import logging
import os
import queue
import threading
import time

_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS {table} (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  level VARCHAR(16) NOT NULL,
  context VARCHAR(100) NULL,
  message TEXT NOT NULL,
  meta JSON NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY idx_level_created (level, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

_INSERT_SQL = (
    "INSERT INTO {table} (level, context, message, meta) "
    "VALUES (:level, :context, :message, :meta)"
)

_QUEUE_MAX = 10000  # 有界队列:MySQL 长时间不可用时丢旧保新,内存不涨
_BATCH_MAX = 200
_FLUSH_INTERVAL = 2.0


class _MysqlLogHandler(logging.Handler):
    def __init__(self, url: str, table: str = "log_ai_service"):
        super().__init__(level=logging.INFO)
        self._url = url
        self._table = table
        self._queue: queue.Queue = queue.Queue(maxsize=_QUEUE_MAX)
        threading.Thread(target=self._worker, daemon=True, name="mysql-log").start()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._queue.put_nowait(
                (
                    record.levelname.lower(),
                    record.name[-100:],  # context 截到 100,与表结构一致
                    self.format(record)[:60000],  # message 上限与 TEXT 容量留裕
                    None,
                )
            )
        except Exception:  # noqa: BLE001 — 日志 handler 绝不抛
            pass

    def _worker(self) -> None:
        engine = None
        try:
            from sqlalchemy import create_engine, text

            engine = create_engine(
                self._url, pool_pre_ping=True, pool_size=2, max_overflow=2, future=True
            )
            with engine.begin() as con:
                con.execute(text(_TABLE_DDL.format(table=self._table)))
        except Exception as exc:  # noqa: BLE001
            print(f"[dblog] MySQL 运行日志不可用,本次运行仅控制台输出: {exc}", flush=True)
            engine = None

        while True:
            batch = [self._queue.get()]
            deadline = time.monotonic() + _FLUSH_INTERVAL
            while len(batch) < _BATCH_MAX and time.monotonic() < deadline:
                try:
                    batch.append(self._queue.get(timeout=deadline - time.monotonic()))
                except queue.Empty:
                    break
            if engine is None:
                continue
            try:
                with engine.begin() as con:
                    con.execute(
                        text(_INSERT_SQL.format(table=self._table)),
                        [
                            {"level": lv, "context": ctx, "message": msg, "meta": meta}
                            for lv, ctx, msg, meta in batch
                        ],
                    )
            except Exception as exc:  # noqa: BLE001
                print(f"[dblog] 运行日志落库失败,丢弃 {len(batch)} 条: {exc}", flush=True)


def attach_mysql_logging() -> bool:
    """把 MySQL 日志 handler 挂到 root logger。

    DATABASE_URL 非 mysql 开头(如 sqlite 兜底)时返回 False,不做任何事。
    """
    url = os.getenv("DATABASE_URL", "")
    if not url.startswith("mysql"):
        return False
    handler = _MysqlLogHandler(url.replace("+aiomysql", "+pymysql"))
    handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger().addHandler(handler)
    return True
