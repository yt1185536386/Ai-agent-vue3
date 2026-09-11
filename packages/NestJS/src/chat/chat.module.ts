import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ModelsModule } from '../models/models.module';
import { ChatController } from './chat.controller';
import { ChatService } from './chat.service';
import { ConversationsController } from './conversations.controller';
import { UserChatSetting } from './user-chat-setting.entity';

@Module({
  imports: [TypeOrmModule.forFeature([UserChatSetting]), ModelsModule],
  controllers: [ChatController, ConversationsController],
  providers: [ChatService],
})
export class ChatModule {}
