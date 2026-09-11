package com.v3agent.gateway.log;

import ch.qos.logback.classic.LoggerContext;
import jakarta.annotation.PostConstruct;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * 把 {@link MysqlLogAppender} 挂到 root logger。
 * 不动 logback 配置文件,application.yml 里的控制台格式与 level 保持原样;
 * appender 内部自带失败静默,MySQL 不可用时与改造前行为完全一致。
 */
@Component
public class MysqlLogAppenderInitializer {

    @PostConstruct
    public void attach() {
        LoggerContext ctx = (LoggerContext) LoggerFactory.getILoggerFactory();
        MysqlLogAppender appender = new MysqlLogAppender();
        appender.setContext(ctx);
        appender.setName("MYSQL_DB");
        appender.start();
        ch.qos.logback.classic.Logger root =
                (ch.qos.logback.classic.Logger) LoggerFactory.getLogger(org.slf4j.Logger.ROOT_LOGGER_NAME);
        root.addAppender(appender);
    }
}
