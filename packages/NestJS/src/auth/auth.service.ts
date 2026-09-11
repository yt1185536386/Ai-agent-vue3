import { Injectable, UnauthorizedException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { JwtService } from '@nestjs/jwt';
import { randomUUID } from 'crypto';
import { SafeUser, UsersService } from '../users/users.service';
import { LoginDto, RegisterDto } from './auth.controller';

/** 登录失败锁定记录:key = username|ip */
interface LoginFailRecord {
  count: number;
  lockedUntil: number;
}

@Injectable()
export class AuthService {
  constructor(
    private readonly usersService: UsersService,
    private readonly jwtService: JwtService,
    private readonly config: ConfigService,
  ) {}

  // ---------- 登录防爆破(单实例内存版;多实例部署时换 Redis) ----------
  /** 同一 username|ip 连续失败达上限后锁定一段时间 */
  private readonly loginFails = new Map<string, LoginFailRecord>();
  private readonly LOGIN_MAX_FAILS = 5;
  private readonly LOGIN_LOCK_MS = 15 * 60_000;

  private loginKey(username: string, clientIp: string) {
    return `${username}|${clientIp || 'unknown'}`;
  }

  private assertNotLocked(key: string): void {
    const rec = this.loginFails.get(key);
    if (rec && rec.lockedUntil > Date.now()) {
      const minutes = Math.ceil((rec.lockedUntil - Date.now()) / 60_000);
      throw new UnauthorizedException(
        `失败次数过多,账号已临时锁定,请 ${minutes} 分钟后再试`,
      );
    }
  }

  private recordLoginFail(key: string): void {
    const rec = this.loginFails.get(key);
    const count = (rec?.count ?? 0) + 1;
    const lockedUntil =
      count >= this.LOGIN_MAX_FAILS ? Date.now() + this.LOGIN_LOCK_MS : 0;
    this.loginFails.set(key, { count, lockedUntil });
    // 顺带清理已过锁定期的记录,防止 Map 无限增长
    if (this.loginFails.size > 10_000) {
      const now = Date.now();
      for (const [k, v] of this.loginFails) {
        if (v.lockedUntil !== 0 && v.lockedUntil < now) {
          this.loginFails.delete(k);
        }
      }
    }
  }

  async register(dto: RegisterDto) {
    const user = await this.usersService.create(dto.username, dto.password, {
      email: dto.email,
      displayName: dto.displayName ?? dto.username,
    });
    const access_token = this.signToken(user);
    return { access_token, user };
  }

  async login(dto: LoginDto, clientIp = '') {
    const key = this.loginKey(dto.username, clientIp);
    this.assertNotLocked(key);
    const user = await this.usersService.findByUsername(dto.username);
    if (!user) {
      this.recordLoginFail(key);
      throw new UnauthorizedException('用户名或密码错误');
    }
    if (user.status === 0) {
      throw new UnauthorizedException('账号已被禁用');
    }
    const valid = await this.usersService.validatePassword(user, dto.password);
    if (!valid) {
      this.recordLoginFail(key);
      throw new UnauthorizedException('用户名或密码错误');
    }
    this.loginFails.delete(key);
    await this.usersService.updateLastLogin(user.id);
    const safe = this.usersService.toSafe(user);
    const access_token = this.signToken(safe);
    return { access_token, user: safe };
  }

  async me(userId: string) {
    const user = await this.usersService.findById(userId);
    if (!user) {
      throw new UnauthorizedException('用户不存在');
    }
    return this.usersService.toSafe(user);
  }

  private signToken(user: SafeUser): string {
    return this.jwtService.sign(
      {
        sub: user.id,
        username: user.username,
        // jti:token 唯一标识,为后续吊销(黑名单/登出)预留
        jti: randomUUID(),
      },
      {
        secret: this.config.get('JWT_SECRET'),
        expiresIn: this.config.get('JWT_EXPIRES_IN') || '7d',
      },
    );
  }
}
