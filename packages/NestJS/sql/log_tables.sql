-- 运行日志表:每个后端服务一张,结构同构,仅在 DB_SYNCHRONIZE=false 的生产环境需要手工执行。
-- 开发环境:log_nestjs 由 TypeORM synchronize 自动建;log_ai_service 由服务启动时自动建;
--          log_model_gateway 由网关首次落库时自动建。

CREATE TABLE IF NOT EXISTS log_nestjs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  level VARCHAR(16) NOT NULL,
  context VARCHAR(100) NULL,
  message TEXT NOT NULL,
  meta JSON NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY idx_level_created (level, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='NestJS BFF 运行日志';

CREATE TABLE IF NOT EXISTS log_ai_service (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  level VARCHAR(16) NOT NULL,
  context VARCHAR(100) NULL,
  message TEXT NOT NULL,
  meta JSON NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY idx_level_created (level, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ai-service Agent 运行日志';

CREATE TABLE IF NOT EXISTS log_model_gateway (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  level VARCHAR(16) NOT NULL,
  context VARCHAR(100) NULL,
  message TEXT NOT NULL,
  meta JSON NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY idx_level_created (level, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='model-gateway Java 网关运行日志';
