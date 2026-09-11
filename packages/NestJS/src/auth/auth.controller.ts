import {
  Controller,
  Post,
  Body,
  SetMetadata,
  Get,
  Req,
  Ip,
  UseGuards,
} from '@nestjs/common';
import {
  IsString,
  MinLength,
  IsEmail,
  IsOptional,
  MaxLength,
} from 'class-validator';
import { JwtAuthGuard } from './jwt-auth.guard';
import { AuthService } from './auth.service';

export class RegisterDto {
  @IsString()
  @MinLength(3)
  @MaxLength(32)
  username: string;

  @IsString()
  @MinLength(6)
  @MaxLength(64)
  password: string;

  @IsOptional()
  @IsEmail()
  @MaxLength(120)
  email?: string;

  @IsOptional()
  @IsString()
  @MaxLength(100)
  displayName?: string;
}

export class LoginDto {
  @IsString()
  @MinLength(1)
  username: string;

  @IsString()
  @MinLength(1)
  password: string;
}

@Controller('auth')
@SetMetadata('isPublic', true)
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  @Post('register')
  async register(@Body() dto: RegisterDto) {
    return this.authService.register(dto);
  }

  @Post('login')
  async login(@Body() dto: LoginDto, @Ip() ip: string) {
    return this.authService.login(dto, ip);
  }

  @Get('me')
  @UseGuards(JwtAuthGuard)
  async me(@Req() req: Express.Request) {
    return this.authService.me((req as any).user.userId);
  }
}
