package com.v3agent.gateway.log;

import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.classic.spi.IThrowableProxy;
import ch.qos.logback.core.AppenderBase;
import org.slf4j.MDC;

import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * 运行日志落库:批量写入 MySQL 的 log_model_gateway 表
 * (与 NestJS 的 log_nestjs、ai-service 的 log_ai_service 保持同构)。
 *
 * 连接信息优先级:环境变量 LOG_DB_URL / LOG_DB_USERNAME / LOG_DB_PASSWORD
 *   → 回退解析同仓库 NestJS/.env 的 DB_*(开发环境零配置)。
 * 两者都不可用或连接失败时静默禁用,控制台日志完全不受影响。
 *
 * 关键约束:日志系统绝不能反噬业务——队列有界(满了丢弃)、落库失败只写一次 stderr。
 */
public class MysqlLogAppender extends AppenderBase<ILoggingEvent> {

    private static final String TABLE = "log_model_gateway";

    private static final String DDL = """
            CREATE TABLE IF NOT EXISTS log_model_gateway (
              id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
              level VARCHAR(16) NOT NULL,
              context VARCHAR(100) NULL,
              message TEXT NOT NULL,
              meta JSON NULL,
              created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
              PRIMARY KEY (id),
              KEY idx_level_created (level, created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """;

    private static final String INSERT =
            "INSERT INTO log_model_gateway (level, context, message, meta) VALUES (?,?,?,?)";

    private static final int BUFFER_MAX = 1000;
    private static final int FLUSH_INTERVAL_SECONDS = 2;

    private final String url;
    private final String username;
    private final String password;
    private final List<Object[]> buffer = new ArrayList<>();
    private final ScheduledExecutorService scheduler =
            Executors.newSingleThreadScheduledExecutor(r -> {
                Thread t = new Thread(r, "mysql-log");
                t.setDaemon(true);
                return t;
            });

    private volatile boolean dbReady = false;
    private boolean warnedOnce = false;

    public MysqlLogAppender() {
        String envUrl = System.getenv("LOG_DB_URL");
        String envUser = System.getenv("LOG_DB_USERNAME");
        String envPass = System.getenv("LOG_DB_PASSWORD");

        Map<String, String> nestEnv = readNestjsEnv();
        this.url = envUrl != null && !envUrl.isBlank() ? envUrl : defaultUrl(nestEnv);
        this.username = envUser != null && !envUser.isBlank() ? envUser : nestEnv.get("DB_USERNAME");
        this.password = envPass != null ? envPass : nestEnv.getOrDefault("DB_PASSWORD", "");
    }

    private static String defaultUrl(Map<String, String> env) {
        String host = env.getOrDefault("DB_HOST", "localhost");
        String port = env.getOrDefault("DB_PORT", "3306");
        String db = env.getOrDefault("DB_DATABASE", "ai_agent");
        return "jdbc:mysql://%s:%s/%s?useSSL=false&serverTimezone=Asia/Shanghai&characterEncoding=UTF-8"
                .formatted(host, port, db);
    }

    /** 回退解析同仓库 ../NestJS/.env(相对 model-gateway 工作目录),失败返回空 Map。 */
    private static Map<String, String> readNestjsEnv() {
        for (Path candidate : List.of(
                Path.of("..", "NestJS", ".env"),
                Path.of("NestJS", ".env"))) {
            try {
                Map<String, String> out = new java.util.HashMap<>();
                for (String line : Files.readAllLines(candidate)) {
                    line = line.trim();
                    if (line.isEmpty() || line.startsWith("#") || !line.contains("=")) continue;
                    int i = line.indexOf('=');
                    out.putIfAbsent(line.substring(0, i).trim(), line.substring(i + 1).trim());
                }
                if (!out.isEmpty()) return out;
            } catch (Exception ignored) {
                // 换下一个候选路径
            }
        }
        return Map.of();
    }

    @Override
    public void start() {
        if (username == null || username.isBlank()) {
            addWarn("LOG_DB_USERNAME 未配置且 NestJS/.env 不可读,运行日志不落库(仅控制台)");
            super.start();
            return;
        }
        scheduler.scheduleWithFixedDelay(this::flush,
                FLUSH_INTERVAL_SECONDS, FLUSH_INTERVAL_SECONDS, TimeUnit.SECONDS);
        super.start();
    }

    @Override
    protected void append(ILoggingEvent event) {
        synchronized (buffer) {
            if (buffer.size() >= BUFFER_MAX) return; // 背压:满了丢弃
            IThrowableProxy t = event.getThrowableProxy();
            String msg = event.getFormattedMessage()
                    + (t == null ? "" : "\n" + throwableToString(t));
            buffer.add(new Object[]{
                    event.getLevel().toString().toLowerCase(),
                    truncate(event.getLoggerName(), 100),
                    truncate(msg, 60000),
                    MDC.get("requestId")
            });
        }
    }

    private void flush() {
        List<Object[]> batch;
        synchronized (buffer) {
            if (buffer.isEmpty()) return;
            batch = new ArrayList<>(buffer);
            buffer.clear();
        }
        if (!dbReady) {
            try (Connection con = DriverManager.getConnection(url, username, password);
                 var st = con.createStatement()) {
                st.execute(DDL);
                dbReady = true;
                if (warnedOnce) {
                    System.err.println("[MysqlLogAppender] MySQL 日志恢复可用");
                }
            } catch (Exception first) {
                if (!warnedOnce) {
                    warnedOnce = true;
                    System.err.println("[MysqlLogAppender] MySQL 日志不可用,丢弃 "
                            + batch.size() + " 条(此后不再提示,恢复后自动续写): "
                            + first.getMessage());
                }
                return;
            }
        }
        try (Connection con = DriverManager.getConnection(url, username, password);
             PreparedStatement ps = con.prepareStatement(INSERT)) {
            for (Object[] row : batch) {
                ps.setString(1, (String) row[0]);
                ps.setString(2, (String) row[1]);
                ps.setString(3, (String) row[2]);
                ps.setString(4, (String) row[3]);
                ps.addBatch();
            }
            ps.executeBatch();
        } catch (Exception e) {
            System.err.println("[MysqlLogAppender] 落库失败,丢弃 " + batch.size() + " 条: " + e.getMessage());
        }
    }

    @Override
    public void stop() {
        flush();
        scheduler.shutdownNow();
        super.stop();
    }

    private static String truncate(String s, int max) {
        return s == null || s.length() <= max ? s : s.substring(0, max);
    }

    private static String throwableToString(IThrowableProxy t) {
        StringBuilder sb = new StringBuilder()
                .append(t.getClassName()).append(": ").append(t.getMessage());
        var stes = t.getStackTraceElementProxyArray();
        for (int i = 0; i < stes.length && i < 20; i++) {
            sb.append("\n\tat ").append(stes[i].getStackTraceElement());
        }
        return sb.toString();
    }
}
