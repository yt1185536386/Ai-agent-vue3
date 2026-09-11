import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { APP_GUARD } from '@nestjs/core';
import { ScheduleModule } from '@nestjs/schedule';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { AsrModule } from './asr/asr.module';
import { AuditModule } from './audit/audit.module';
import { AuthModule } from './auth/auth.module';
import { JwtAuthGuard } from './auth/jwt-auth.guard';
import { PermissionGuard } from './auth/permission.guard';
import { ChatModule } from './chat/chat.module';
import { FilesModule } from './files/files.module';
import { ModelsModule } from './models/models.module';
import { UsersModule } from './users/users.module';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    TypeOrmModule.forRootAsync({
      imports: [ConfigModule],
      inject: [ConfigService],
      useFactory: (config: ConfigService) => ({
        type: 'mysql',
        host: config.get('DB_HOST') || 'localhost',
        port: Number(config.get('DB_PORT') || 3306),
        username: config.get('DB_USERNAME'),
        password: config.get('DB_PASSWORD'),
        database: config.get('DB_DATABASE'),
        entities: [__dirname + '/**/*.entity{.ts,.js}'],
        // 自动建表:仅开发环境使用,生产必须 DB_SYNCHRONIZE=false(用 migration)
        synchronize: (config.get('DB_SYNCHRONIZE') ?? 'true') === 'true',
        logging: false,
      }),
    }),
    ScheduleModule.forRoot(),
    AuditModule,
    UsersModule,
    AuthModule,
    ChatModule,
    ModelsModule,
    FilesModule,
    AsrModule,
  ],
  controllers: [AppController],
  providers: [
    AppService,
    {
      provide: APP_GUARD,
      useClass: JwtAuthGuard,
    },
    // 必须在 JwtAuthGuard 之后:依赖 req.user 中的 userId
    {
      provide: APP_GUARD,
      useClass: PermissionGuard,
    },
  ],
})
export class AppModule {}
