import {
  BadRequestException,
  ConflictException,
  ForbiddenException,
  Injectable,
  Logger,
  NotFoundException,
  OnModuleInit,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { In, IsNull, Not, Repository } from 'typeorm';
import * as bcrypt from 'bcryptjs';
import { DeptPosition, User, UserStatus } from './users.entity';
import { JobLevel } from './job-level.entity';
import { Department } from './department.entity';
import { Permission } from './permission.entity';
import { JobLevelPermission } from './job-level-permission.entity';
import { UserPermissionGrant } from './user-permission.entity';
import { ALL_PERM_CODES, PERMISSION_SEEDS } from './permission-codes';
import { AuditLog } from '../audit/audit-log.entity';
import { AuditService } from '../audit/audit.service';
import {
  CreateDepartmentDto,
  CreateJobLevelDto,
  CreateUserDto,
  SetJobLevelPermsDto,
  SetUserPermsDto,
  UpdateDepartmentDto,
  UpdateJobLevelDto,
  UpdateUserDto,
} from './users.dto';

export interface SafeUser {
  id: string;
  username: string;
  email?: string;
  displayName?: string;
  avatar?: string;
  isSuperAdmin: boolean;
  jobLevel?: { id: number; name: string; rank: number } | null;
  department?: { id: number; name: string } | null;
  deptPosition: DeptPosition;
  status: UserStatus;
  lastLoginAt?: Date;
  createdAt: Date;
}

export type AuditOutcome = 'auto' | 'approved' | 'rejected';

/** 无职级时视为最低层级,所有职级调整操作自然被拦截 */
const LOWEST_RANK = Number.MAX_SAFE_INTEGER;

/** 部门默认职级(每个部门一套):rank 越小级别越高 */
const DEPT_JOB_LEVEL_SEEDS = [
  { name: '高级', rank: 1 },
  { name: '中级', rank: 2 },
  { name: '初级', rank: 3 },
];

const ROOT_DEPARTMENT_NAME = '总公司';

/** eric 所在的总经办部门(总裁办总经理 = 超级管理员) */
const PRESIDENT_OFFICE_NAME = '总裁办';

/** 部门内职位名额: 经理限 1 / 副经理限 2 / 组长与组员不限 */
const DEPT_POSITION_QUOTA: Partial<Record<DeptPosition, number>> = {
  [DeptPosition.MANAGER]: 1,
  [DeptPosition.DEPUTY]: 2,
};

const DEPT_POSITION_LABELS: Record<DeptPosition, string> = {
  [DeptPosition.MANAGER]: '经理',
  [DeptPosition.DEPUTY]: '副经理',
  [DeptPosition.LEADER]: '组长',
  [DeptPosition.MEMBER]: '组员',
};

@Injectable()
export class UsersService implements OnModuleInit {
  private readonly logger = new Logger(UsersService.name);

  constructor(
    @InjectRepository(User)
    private readonly usersRepository: Repository<User>,
    @InjectRepository(JobLevel)
    private readonly jobLevelsRepository: Repository<JobLevel>,
    @InjectRepository(Department)
    private readonly departmentsRepository: Repository<Department>,
    @InjectRepository(Permission)
    private readonly permissionsRepository: Repository<Permission>,
    @InjectRepository(JobLevelPermission)
    private readonly jobLevelPermissionsRepository: Repository<JobLevelPermission>,
    @InjectRepository(UserPermissionGrant)
    private readonly userPermissionsRepository: Repository<UserPermissionGrant>,
    @InjectRepository(AuditLog)
    private readonly auditRepository: Repository<AuditLog>,
    private readonly auditService: AuditService,
  ) {}

  async onModuleInit(): Promise<void> {
    await this.seedDepartments();
    await this.ensurePresidentOffice();
    await this.migrateJobLevelsToDepartments();
    await this.seedDeptJobLevels();
    await this.seedPermissions();
    await this.backfillDepartment();
    await this.backfillJobLevels();
    await this.seedSuperAdmin();
  }

  // ---------- 种子与迁移(全部幂等) ----------

  /** 一次性迁移: 旧全局职级(departmentId 为空或 0)整体重置为按部门划分 */
  private async migrateJobLevelsToDepartments(): Promise<void> {
    const legacy = await this.jobLevelsRepository
      .createQueryBuilder()
      .where('departmentId IS NULL OR departmentId = 0')
      .getCount();
    if (!legacy) return;
    await this.jobLevelsRepository
      .createQueryBuilder()
      .delete()
      .where('departmentId IS NULL OR departmentId = 0')
      .execute();
    this.logger.log(`已清理旧全局职级 ${legacy} 个,迁移为按部门划分`);
  }

  /** 每个部门一套默认职级: 职级数为 0 的部门播种 高级/中级/初级 */
  private async seedDeptJobLevels(departmentId?: number): Promise<void> {
    const departments = departmentId != null
      ? await this.departmentsRepository.find({ where: { id: departmentId } })
      : await this.departmentsRepository.find();
    for (const dept of departments) {
      const count = await this.jobLevelsRepository.count({
        where: { departmentId: dept.id },
      });
      if (count > 0) continue;
      for (const seed of DEPT_JOB_LEVEL_SEEDS) {
        await this.jobLevelsRepository.save(
          this.jobLevelsRepository.create({
            ...seed,
            departmentId: dept.id,
            builtin: true,
          }),
        );
      }
      this.logger.log(`已为部门 ${dept.name} 播种默认职级(高级/中级/初级)`);
    }
  }

  /** 确保总裁办存在(根层级;eric 的归属部门) */
  private async ensurePresidentOffice(): Promise<void> {
    const exists = await this.departmentsRepository.findOne({
      where: { name: PRESIDENT_OFFICE_NAME, parentId: IsNull() },
    });
    if (!exists) {
      await this.departmentsRepository.save(
        this.departmentsRepository.create({
          name: PRESIDENT_OFFICE_NAME,
          parentId: null,
        }),
      );
      this.logger.log(`已创建 ${PRESIDENT_OFFICE_NAME}`);
    }
  }

  private async seedDepartments(): Promise<void> {
    const count = await this.departmentsRepository.count();
    if (count === 0) {
      await this.departmentsRepository.save(
        this.departmentsRepository.create({
          name: ROOT_DEPARTMENT_NAME,
          parentId: null,
        }),
      );
      this.logger.log(`已创建根部门 ${ROOT_DEPARTMENT_NAME}`);
    }
  }

  /** 权限点字典: 补齐 5 个可配置权限点,并清理旧体系遗留的权限码 */
  private async seedPermissions(): Promise<void> {
    for (const [code, module, action, name] of PERMISSION_SEEDS) {
      const exists = await this.permissionsRepository.findOne({
        where: { code },
      });
      if (!exists) {
        await this.permissionsRepository.save(
          this.permissionsRepository.create({ code, module, action, name }),
        );
      }
    }
    // 先清理仍引用旧 permissions 表的外键行(旧表尚未删除时,否则 DELETE 会报外键错误)
    const legacyCodes = (
      await this.permissionsRepository.find({
        where: { code: Not(In(ALL_PERM_CODES)) },
        select: { id: true },
      })
    ).map((p) => p.id);
    if (legacyCodes.length) {
      for (const table of ['role_permissions', 'temp_permissions']) {
        try {
          await this.permissionsRepository.query(
            `DELETE FROM ${table} WHERE permissionId IN (?)`,
            [legacyCodes],
          );
        } catch {
          // 旧表可能已被手动清理,忽略
        }
      }
    }
    const removed = await this.permissionsRepository.delete({
      code: Not(In(ALL_PERM_CODES)),
    });
    if (removed.affected) {
      this.logger.log(`已清理旧权限码 ${removed.affected} 条`);
    }
  }

  /** eric: 超管 + 总裁办总经理 + 总裁办最高职级 */
  private async seedSuperAdmin(): Promise<void> {
    const office = await this.getPresidentOffice();
    const top = office ? await this.getTopJobLevelOf(office.id) : null;
    const exists = await this.findByUsername('eric');
    // 初始密码可用 SEED_ADMIN_PASSWORD 覆盖;默认值仅供本地开发,
    // 部署/公开环境必须显式配置(启动日志会提示)
    const seedPassword = process.env.SEED_ADMIN_PASSWORD || 'eric123';
    if (!exists) {
      if (office) await this.demoteOtherManagers(office.id);
      await this.create('eric', seedPassword, {
        displayName: 'Eric',
        isSuperAdmin: true,
        jobLevelId: top?.id,
        departmentId: office?.id,
        deptPosition: DeptPosition.MANAGER,
      });
      this.logger.log(
        `已创建超级管理员账号 eric / (密码见 SEED_ADMIN_PASSWORD,未配置时为开发默认值)` +
          `(${PRESIDENT_OFFICE_NAME}总经理 + 最高职级)`,
      );
      return;
    }
    const patch: Partial<User> = {};
    if (!exists.isSuperAdmin) {
      patch.isSuperAdmin = true;
    }
    if (office && exists.department?.id !== office.id) {
      patch.department = office;
    }
    if (office && exists.deptPosition !== DeptPosition.MANAGER) {
      await this.demoteOtherManagers(office.id);
      patch.deptPosition = DeptPosition.MANAGER;
    }
    if (top && exists.jobLevel?.id !== top.id) {
      patch.jobLevel = top;
    }
    if (Object.keys(patch).length) {
      await this.usersRepository.update(exists.id, patch);
      this.logger.log(`已校正 eric 为超级管理员 + ${PRESIDENT_OFFICE_NAME}总经理 + 最高职级`);
    }
  }

  private async getPresidentOffice(): Promise<Department | null> {
    return this.departmentsRepository.findOne({
      where: { name: PRESIDENT_OFFICE_NAME, parentId: IsNull() },
    });
  }

  /** 部门经理名额(限 1)固定让给 eric: 其余经理降为组员 */
  private async demoteOtherManagers(departmentId: number): Promise<void> {
    const holders = await this.usersRepository.find({
      where: { department: { id: departmentId }, deptPosition: DeptPosition.MANAGER },
    });
    for (const holder of holders) {
      if (holder.username === 'eric') continue;
      await this.usersRepository.update(holder.id, {
        deptPosition: DeptPosition.MEMBER,
      });
      this.logger.log(`已将 ${holder.username} 降为组员,为 eric 腾出部门经理名额`);
    }
  }

  /** 回填: 职级为空或职级不属于本部门的用户,重置为本部门最低职级 */
  private async backfillJobLevels(): Promise<void> {
    const departments = await this.departmentsRepository.find();
    for (const dept of departments) {
      const lowest = await this.getLowestJobLevelOf(dept.id);
      if (!lowest) continue;
      await this.usersRepository
        .createQueryBuilder()
        .update(User)
        .set({ jobLevel: lowest })
        .where('departmentId = :deptId', { deptId: dept.id })
        .andWhere(
          '(jobLevelId IS NULL OR jobLevelId NOT IN ' +
            '(SELECT id FROM job_levels WHERE departmentId = :deptId))',
          { deptId: dept.id },
        )
        .execute();
    }
  }

  /** 回填:没有部门的用户归入根部门 */
  private async backfillDepartment(): Promise<void> {
    const root = await this.getRootDepartment();
    if (!root) return;
    await this.usersRepository
      .createQueryBuilder()
      .update(User)
      .set({ department: root })
      .where('departmentId IS NULL')
      .execute();
  }

  // ---------- 基础查询 ----------

  toSafe(user: User): SafeUser {
    return {
      id: user.id,
      username: user.username,
      email: user.email ?? undefined,
      displayName: user.displayName ?? undefined,
      avatar: user.avatar ?? undefined,
      isSuperAdmin: user.isSuperAdmin,
      jobLevel: user.jobLevel
        ? { id: user.jobLevel.id, name: user.jobLevel.name, rank: user.jobLevel.rank }
        : null,
      department: user.department
        ? { id: user.department.id, name: user.department.name }
        : null,
      deptPosition: user.deptPosition,
      status: user.status,
      lastLoginAt: user.lastLoginAt ?? undefined,
      createdAt: user.createdAt,
    };
  }

  findByUsername(username: string): Promise<User | null> {
    return this.usersRepository.findOne({ where: { username } });
  }

  findById(id: string): Promise<User | null> {
    return this.usersRepository.findOne({ where: { id } });
  }

  findByEmail(email: string): Promise<User | null> {
    return this.usersRepository.findOne({ where: { email } });
  }

  /** 注册用创建:默认普通用户 + 最低职级 + 根部门 + 组员 */
  async create(
    username: string,
    password: string,
    options?: {
      email?: string;
      displayName?: string;
      avatar?: string;
      isSuperAdmin?: boolean;
      jobLevelId?: number;
      departmentId?: number;
      deptPosition?: DeptPosition;
    },
  ): Promise<SafeUser> {
    await this.assertUsernameEmailAvailable(username, options?.email);
    const department = options?.departmentId
      ? await this.departmentsRepository.findOne({
          where: { id: options.departmentId },
        })
      : await this.getRootDepartment();
    const jobLevel = options?.jobLevelId
      ? await this.jobLevelsRepository.findOne({
          where: { id: options.jobLevelId },
        })
      : department
        ? await this.getLowestJobLevelOf(department.id)
        : null;
    if (jobLevel && department && jobLevel.departmentId !== department.id) {
      throw new BadRequestException('职级不属于所选部门');
    }
    const deptPosition = options?.deptPosition ?? DeptPosition.MEMBER;
    if (department) {
      await this.assertDeptPositionQuota(department.id, deptPosition);
    }
    const passwordHash = await bcrypt.hash(password, 10);
    const user = this.usersRepository.create({
      username,
      passwordHash,
      email: options?.email,
      displayName: options?.displayName,
      avatar: options?.avatar,
      isSuperAdmin: options?.isSuperAdmin ?? false,
      status: UserStatus.ACTIVE,
      jobLevel: jobLevel ?? null,
      department: department ?? null,
      deptPosition,
    });
    const saved = await this.usersRepository.save(user);
    return this.toSafe(saved);
  }

  async updateLastLogin(userId: string): Promise<void> {
    await this.usersRepository.update(userId, { lastLoginAt: new Date() });
  }

  async validatePassword(user: User, password: string): Promise<boolean> {
    return bcrypt.compare(password, user.passwordHash);
  }

  // ---------- 有效权限(职级批量绑定 + 个人逐项覆盖) ----------

  // ---------- 鉴权上下文快照缓存(PermissionGuard 每请求查库的优化) ----------
  // 原先每个请求要做 ~4 次查库(findById + 权限点全表 + 个人绑定 + 职级绑定)。
  // 缓存 30s 兜底;所有权限/用户写操作后调用 invalidateAuthCache() 立即失效,
  // 保证"禁用/改权限即时生效"语义不变。
  private authCache = new Map<
    string,
    { at: number; user: User; codes: Set<string> }
  >();
  private readonly AUTH_CACHE_TTL = 30_000;

  /** 读取用户与有效权限码(带快照缓存);用户不存在返回 null */
  async loadAuthContext(
    userId: string,
  ): Promise<{ user: User; codes: Set<string> } | null> {
    const hit = this.authCache.get(userId);
    if (hit && Date.now() - hit.at < this.AUTH_CACHE_TTL) {
      return { user: hit.user, codes: hit.codes };
    }
    const user = await this.findById(userId);
    if (!user) return null;
    const codes = await this.resolvePermissionCodes(user);
    this.authCache.set(userId, { at: Date.now(), user, codes });
    return { user, codes };
  }

  /** 权限/用户变更后调用:未指定 userId 时全量失效鉴权快照缓存 */
  invalidateAuthCache(userId?: string): void {
    if (userId) {
      this.authCache.delete(userId);
    } else {
      this.authCache.clear();
    }
  }

  /**
   * 解析用户的有效权限码集合:
   * 超管 → 全部权限点;其余逐权限点 —— 个人绑定有记录则以 allowed 为准,
   * 无记录则继承职级绑定,职级也未绑定则拒绝。
   */
  async resolvePermissionCodes(user: User): Promise<Set<string>> {
    const points = await this.permissionsRepository.find();
    if (user.isSuperAdmin) {
      return new Set(points.map((p) => p.code));
    }
    const overrides = await this.userPermissionsRepository.find({
      where: { userId: user.id },
    });
    const overrideMap = new Map(overrides.map((o) => [o.permissionId, o.allowed]));
    const jobLevelRows = user.jobLevel
      ? await this.jobLevelPermissionsRepository.find({
          where: { jobLevelId: user.jobLevel.id },
        })
      : [];
    const jobLevelSet = new Set(jobLevelRows.map((r) => r.permissionId));
    const codes = new Set<string>();
    for (const point of points) {
      const override = overrideMap.get(point.id);
      if (override !== undefined) {
        if (override) codes.add(point.code);
      } else if (jobLevelSet.has(point.id)) {
        codes.add(point.code);
      }
    }
    return codes;
  }

  /** 当前用户有效权限(/v1/users/me/permissions) */
  async effectivePermissions(userId: string): Promise<{
    isSuperAdmin: boolean;
    permissions: string[];
  }> {
    const user = await this.findById(userId);
    if (!user || user.status !== UserStatus.ACTIVE) {
      return { isSuperAdmin: false, permissions: [] };
    }
    const codes = await this.resolvePermissionCodes(user);
    return { isSuperAdmin: user.isSuperAdmin, permissions: [...codes] };
  }

  // ---------- 权限维护(仅超级管理员,守卫已拦截) ----------

  listPermPoints(): Promise<Permission[]> {
    return this.permissionsRepository.find({ order: { id: 'ASC' } });
  }

  /**
   * 职级 × 权限点矩阵(按部门分组):
   * 超管返回全部部门;部门经理返回本部门子树;其余禁止。
   */
  async jobLevelPermMatrix(operator: User): Promise<
    Array<{
      department: { id: number; name: string };
      levels: Array<{ jobLevel: { id: number; name: string; rank: number }; codes: string[] }>;
    }>
  > {
    let scopeIds: Set<number> | null = null;
    if (!operator.isSuperAdmin) {
      scopeIds = await this.managerScopeIds(operator);
      if (!scopeIds.size) {
        throw new ForbiddenException('只有部门经理或超级管理员可以维护职级权限');
      }
    }
    const departments = (await this.listDepartments())
      .filter((d) => scopeIds == null || scopeIds.has(d.id))
      .sort((a, b) => a.id - b.id);
    const levels = await this.listJobLevels();
    const rows = await this.jobLevelPermissionsRepository.find();
    return departments.map((dept) => ({
      department: { id: dept.id, name: dept.name },
      levels: levels
        .filter((l) => l.departmentId === dept.id)
        .map((level) => ({
          jobLevel: { id: level.id, name: level.name, rank: level.rank },
          codes: rows
            .filter((r) => r.jobLevelId === level.id)
            .map((r) => r.permission.code),
        })),
    }));
  }

  /** 职级批量绑定: 全量覆盖该职级的权限点集合(超管任意;经理限本部门子树) */
  async setJobLevelPerms(
    operator: User,
    jobLevelId: number,
    dto: SetJobLevelPermsDto,
  ): Promise<{ jobLevelId: number; codes: string[] }> {
    const level = await this.getJobLevelOrFail(jobLevelId);
    await this.assertCanConfigDepartment(operator, level.departmentId);
    const points = await this.assertPermCodesExist(dto.codes);
    await this.jobLevelPermissionsRepository.delete({ jobLevelId: level.id });
    for (const point of points) {
      await this.jobLevelPermissionsRepository.save(
        this.jobLevelPermissionsRepository.create({
          jobLevelId: level.id,
          permissionId: point.id,
        }),
      );
    }
    await this.audit(operator, 'perm.bind_job_level', 'joblevel', String(level.id), level.name, {
      codes: dto.codes,
    }, 'auto');
    this.invalidateAuthCache();
    return { jobLevelId: level.id, codes: dto.codes };
  }

  /** 个人权限配置: 个人覆盖项 + 职级继承项 + 有效结果 */
  async userPermConfig(
    operator: User,
    userId: string,
  ): Promise<{
    user: SafeUser;
    overrides: Array<{ code: string; allowed: boolean }>;
    inherited: string[];
    effective: string[];
  }> {
    const user = await this.findById(userId);
    if (!user) throw new NotFoundException('用户不存在');
    await this.assertCanBindUserPerms(operator, user);
    const overrides = await this.userPermissionsRepository.find({
      where: { userId },
    });
    const jobLevelRows = user.jobLevel
      ? await this.jobLevelPermissionsRepository.find({
          where: { jobLevelId: user.jobLevel.id },
        })
      : [];
    const overrideIds = new Set(overrides.map((o) => o.permissionId));
    const inherited = jobLevelRows
      .filter((r) => !overrideIds.has(r.permissionId))
      .map((r) => r.permission.code);
    const effective = await this.resolvePermissionCodes(user);
    return {
      user: this.toSafe(user),
      overrides: overrides.map((o) => ({
        code: o.permission.code,
        allowed: o.allowed,
      })),
      inherited,
      effective: [...effective],
    };
  }

  /** 个人单独绑定: 全量覆盖;allowed 为 null 的项删除(回到继承职级) */
  async setUserPerms(
    operator: User,
    userId: string,
    dto: SetUserPermsDto,
  ): Promise<{ userId: string; overrides: Array<{ code: string; allowed: boolean }> }> {
    const target = await this.findById(userId);
    if (!target) throw new NotFoundException('用户不存在');
    await this.assertCanBindUserPerms(operator, target);
    const codes = dto.overrides.map((o) => o.code);
    const points = await this.assertPermCodesExist(codes);
    const pointByCode = new Map(points.map((p) => [p.code, p]));
    await this.userPermissionsRepository.delete({ userId });
    const saved: Array<{ code: string; allowed: boolean }> = [];
    for (const override of dto.overrides) {
      if (override.allowed === null || override.allowed === undefined) continue;
      const point = pointByCode.get(override.code)!;
      await this.userPermissionsRepository.save(
        this.userPermissionsRepository.create({
          userId,
          permissionId: point.id,
          allowed: override.allowed,
        }),
      );
      saved.push({ code: override.code, allowed: override.allowed });
    }
    await this.audit(operator, 'perm.bind_user', 'user', target.id, target.username, {
      overrides: saved,
    }, 'auto');
    this.invalidateAuthCache(target.id);
    return { userId, overrides: saved };
  }

  private async assertPermCodesExist(codes: string[]): Promise<Permission[]> {
    if (!codes.length) return [];
    const points = await this.permissionsRepository.find({
      where: { code: In(codes) },
    });
    const found = new Set(points.map((p) => p.code));
    const missing = codes.filter((c) => !found.has(c));
    if (missing.length) {
      throw new NotFoundException(`权限码不存在: ${missing.join(', ')}`);
    }
    return points;
  }

  /**
   * 个人权限绑定规则:
   * 超管(eric)的权限不可被任何人修改;
   * 部门经理可调整本部门子树内任意用户(全权,无需权限点);
   * 其余操作者须持有「部门成员管理」权限点且职级严格高于目标。
   */
  private async assertCanBindUserPerms(operator: User, target: User): Promise<void> {
    if (target.isSuperAdmin) {
      throw new ForbiddenException('超级管理员的权限不可修改');
    }
    if (operator.isSuperAdmin) return;
    const managerScope = await this.managerScopeIds(operator);
    if (target.department?.id != null && managerScope.has(target.department.id)) {
      return;
    }
    const codes = await this.resolvePermissionCodes(operator);
    if (!codes.has('dept:member')) {
      throw new ForbiddenException('没有操作权限');
    }
    const opRank = operator.jobLevel?.rank ?? LOWEST_RANK;
    const targetRank = target.jobLevel?.rank ?? LOWEST_RANK;
    if (opRank >= targetRank) {
      throw new ForbiddenException('只能调整职级低于自己的用户');
    }
  }

  /**
   * 职级相关配置(职级 CRUD / 职级权限绑定)规则:
   * 超管任意部门;部门经理限本部门子树;其余禁止。
   */
  private async assertCanConfigDepartment(
    operator: User,
    departmentId: number,
  ): Promise<void> {
    if (operator.isSuperAdmin) return;
    const managerScope = await this.managerScopeIds(operator);
    if (!managerScope.has(departmentId)) {
      throw new ForbiddenException('只能管理本部门及子部门的职级配置');
    }
  }

  // ---------- 授权规则 ----------

  /** 部门子树 id 集合(内存遍历,Set 天然防环) */
  async departmentSubtreeIds(rootId: number | null | undefined): Promise<Set<number>> {
    const out = new Set<number>();
    if (rootId == null) return out;
    const all = await this.departmentsRepository.find();
    const byParent = new Map<number, number[]>();
    for (const d of all) {
      if (d.parentId == null) continue;
      const list = byParent.get(d.parentId) ?? [];
      list.push(d.id);
      byParent.set(d.parentId, list);
    }
    const stack = [rootId];
    while (stack.length) {
      const id = stack.pop()!;
      if (out.has(id)) continue;
      out.add(id);
      for (const child of byParent.get(id) ?? []) stack.push(child);
    }
    return out;
  }

  /** 操作者作为部门经理可管理的部门 id 集合(本部门子树);非经理或无部门返回空集 */
  async managerScopeIds(operator: User): Promise<Set<number>> {
    if (operator.deptPosition !== DeptPosition.MANAGER || !operator.department) {
      return new Set();
    }
    return this.departmentSubtreeIds(operator.department.id);
  }

  /**
   * 用户管理(CRUD)规则:
   * 超管可管所有非超管用户;超管不可被任何人管理;不能通过管理接口操作自己;
   * 部门经理全权管理本部门子树内用户(无需权限点,不受职级限制);
   * 其余操作者须持有「部门成员管理」权限点,且只能管理本部门及子部门内
   * 职级严格低于自己的用户(上级管下级,无职级按最低处理)。
   */
  async canManage(operator: User, target: User): Promise<boolean> {
    if (target.isSuperAdmin) return false;
    if (operator.id === target.id) return false;
    if (operator.isSuperAdmin) return true;
    // 部门经理全权
    const managerScope = await this.managerScopeIds(operator);
    if (target.department?.id != null && managerScope.has(target.department.id)) {
      return true;
    }
    // 职级向下管理(保留)
    const codes = await this.resolvePermissionCodes(operator);
    if (!codes.has('dept:member')) return false;
    const opRank = operator.jobLevel?.rank ?? LOWEST_RANK;
    const targetRank = target.jobLevel?.rank ?? LOWEST_RANK;
    if (opRank >= targetRank) return false;
    const scope = await this.departmentSubtreeIds(operator.department?.id);
    return target.department?.id != null && scope.has(target.department.id);
  }

  /**
   * 职级调整规则:需先满足 canManage;
   * 部门经理在本部门子树内不受层级限制(全权);
   * 其余操作者职级必须高于目标当前职级,且新职级严格低于操作者自己;
   * 新职级必须属于目标所在部门(职级已按部门划分)。
   * 超管是体系根节点,不受层级限制。
   */
  async assertCanAdjustJobLevel(
    operator: User,
    target: User,
    newLevel: JobLevel,
  ): Promise<void> {
    if (!(await this.canManage(operator, target))) {
      throw new ForbiddenException('无权管理该用户');
    }
    if (newLevel.departmentId !== target.department?.id) {
      throw new BadRequestException('职级不属于目标用户所在部门');
    }
    if (operator.isSuperAdmin) return;
    const managerScope = await this.managerScopeIds(operator);
    if (target.department?.id != null && managerScope.has(target.department.id)) {
      return;
    }
    const opRank = operator.jobLevel?.rank ?? LOWEST_RANK;
    const targetRank = target.jobLevel?.rank ?? LOWEST_RANK;
    if (opRank >= targetRank) {
      throw new ForbiddenException('只能调整职级低于自己的用户');
    }
    if (newLevel.rank <= opRank) {
      throw new ForbiddenException('只能调整为低于自己职级的职级');
    }
  }

  /** 部门内职位名额校验: 经理限 1 / 副经理限 2 / 组长与组员不限 */
  private async assertDeptPositionQuota(
    departmentId: number,
    position: DeptPosition,
    excludeUserId?: string,
  ): Promise<void> {
    const quota = DEPT_POSITION_QUOTA[position];
    if (quota == null) return;
    const holders = await this.usersRepository.find({
      where: { department: { id: departmentId }, deptPosition: position },
      select: { id: true },
    });
    const count = holders.filter((h) => h.id !== excludeUserId).length;
    if (count >= quota) {
      throw new BadRequestException(
        `该部门${DEPT_POSITION_LABELS[position]}名额已满(最多 ${quota} 名)`,
      );
    }
  }

  // ---------- 用户管理 ----------

  /** 当前用户可见的用户列表(超管全量;部门成员管理权限持有者限本部门子树;其余仅自己) */
  async listVisible(operator: User): Promise<SafeUser[]> {
    const qb = this.usersRepository
      .createQueryBuilder('u')
      .leftJoinAndSelect('u.jobLevel', 'jl')
      .leftJoinAndSelect('u.department', 'dept')
      .orderBy('u.createdAt', 'ASC');
    if (operator.isSuperAdmin) {
      // 全量
    } else {
      const codes = await this.resolvePermissionCodes(operator);
      if (codes.has('dept:member')) {
        const scope = await this.departmentSubtreeIds(operator.department?.id);
        const scopeIds = scope.size ? [...scope] : [-1];
        qb.where('u.departmentId IN (:...scopeIds)', { scopeIds }).orWhere(
          'u.id = :selfId',
          { selfId: operator.id },
        );
      } else {
        qb.where('u.id = :selfId', { selfId: operator.id });
      }
    }
    const users = await qb.getMany();
    return users.map((u) => this.toSafe(u));
  }

  async adminCreate(
    operator: User,
    dto: CreateUserDto,
    outcome: AuditOutcome = 'auto',
  ): Promise<SafeUser> {
    this.assertConfirm(dto.confirm);

    // 部门: 缺省时非超管归本部门,超管归根部门;非超管限本子树
    let department: Department | null;
    if (dto.departmentId != null) {
      department = await this.getDepartmentOrFail(dto.departmentId);
    } else if (!operator.isSuperAdmin && operator.department) {
      department = operator.department;
    } else {
      department = await this.getRootDepartment();
    }
    if (!department) {
      throw new BadRequestException('请先创建部门');
    }
    if (!operator.isSuperAdmin) {
      const scope = await this.departmentSubtreeIds(operator.department?.id);
      if (!scope.has(department.id)) {
        throw new ForbiddenException('只能在本部门及子部门内创建用户');
      }
    }

    // 职级: 缺省为目标部门最低职级;显式指定时必须属于目标部门
    let jobLevel: JobLevel | null = null;
    if (dto.jobLevelId != null) {
      jobLevel = await this.getJobLevelOrFail(dto.jobLevelId);
      if (jobLevel.departmentId !== department.id) {
        throw new BadRequestException('职级不属于所选部门');
      }
      await this.assertNewUserJobLevel(operator, jobLevel);
    } else {
      jobLevel = await this.getLowestJobLevelOf(department.id);
    }

    // 部门内职位(名额校验在 create 内)
    const deptPosition = dto.deptPosition ?? DeptPosition.MEMBER;

    const created = await this.create(dto.username, dto.password, {
      email: dto.email,
      displayName: dto.displayName ?? dto.username,
      jobLevelId: jobLevel?.id,
      departmentId: department.id,
      deptPosition,
    });
    await this.audit(operator, 'user.create', 'user', created.id, created.username, {
      jobLevel: jobLevel?.name ?? null,
      department: department.name,
      deptPosition,
    }, outcome);
    return created;
  }

  async adminUpdate(
    operator: User,
    targetId: string,
    dto: UpdateUserDto,
    outcome: AuditOutcome = 'auto',
  ): Promise<SafeUser> {
    this.assertConfirm(dto.confirm);
    const target = await this.findById(targetId);
    if (!target) {
      throw new NotFoundException('用户不存在');
    }
    if (!(await this.canManage(operator, target))) {
      throw new ForbiddenException('无权管理该用户');
    }

    const patch: Partial<User> = {};
    const changes: Record<string, unknown> = {};
    let primaryAction = 'user.update_info';

    if (dto.jobLevelId != null && dto.jobLevelId !== target.jobLevel?.id) {
      const newLevel = await this.getJobLevelOrFail(dto.jobLevelId);
      await this.assertCanAdjustJobLevel(operator, target, newLevel);
      patch.jobLevel = newLevel;
      changes.jobLevel = { from: target.jobLevel?.name ?? null, to: newLevel.name };
      primaryAction = 'user.adjust_job_level';
    }

    const departmentChanged =
      dto.departmentId != null && dto.departmentId !== target.department?.id;
    if (departmentChanged) {
      const dept = await this.getDepartmentOrFail(dto.departmentId!);
      if (!operator.isSuperAdmin) {
        const scope = await this.departmentSubtreeIds(operator.department?.id);
        if (!scope.has(dept.id)) {
          throw new ForbiddenException('只能转岗到本部门及子部门');
        }
      }
      patch.department = dept;
      changes.department = { from: target.department?.name ?? null, to: dept.name };
      primaryAction = 'user.transfer_dept';
    }

    // 部门内职位: 调部门后缺省重置为组员;显式指定时校验新部门名额
    const targetDeptId =
      (patch.department as Department | undefined)?.id ?? target.department?.id;
    if (departmentChanged || dto.deptPosition != null) {
      const nextPosition =
        dto.deptPosition ??
        (departmentChanged ? DeptPosition.MEMBER : target.deptPosition);
      if (nextPosition !== target.deptPosition) {
        if (targetDeptId == null) {
          throw new BadRequestException('用户未分配部门,无法设置部门职位');
        }
        await this.assertDeptPositionQuota(targetDeptId, nextPosition, target.id);
        patch.deptPosition = nextPosition;
        changes.deptPosition = {
          from: DEPT_POSITION_LABELS[target.deptPosition],
          to: DEPT_POSITION_LABELS[nextPosition],
        };
      }
    }

    if (dto.email !== undefined && dto.email !== target.email) {
      await this.assertUsernameEmailAvailable(undefined, dto.email);
      patch.email = dto.email;
      changes.email = { from: target.email ?? null, to: dto.email };
    }
    if (dto.displayName !== undefined && dto.displayName !== target.displayName) {
      patch.displayName = dto.displayName;
      changes.displayName = { from: target.displayName ?? null, to: dto.displayName };
    }
    if (dto.status !== undefined && dto.status !== target.status) {
      patch.status = dto.status;
      changes.status = { from: target.status, to: dto.status };
      primaryAction = dto.status === UserStatus.DISABLED ? 'user.disable' : 'user.enable';
    }
    if (dto.newPassword) {
      patch.passwordHash = await bcrypt.hash(dto.newPassword, 10);
      changes.password = '已重置';
    }

    if (Object.keys(patch).length) {
      await this.usersRepository.update(target.id, patch);
      // 禁用/职位调整等直接改变鉴权语义,立即失效该用户的快照缓存
      this.invalidateAuthCache(target.id);
    }
    if (Object.keys(changes).length) {
      await this.audit(
        operator,
        primaryAction,
        'user',
        target.id,
        target.username,
        changes,
        outcome,
      );
    }
    const fresh = await this.findById(target.id);
    return this.toSafe(fresh!);
  }

  async adminRemove(
    operator: User,
    targetId: string,
    outcome: AuditOutcome = 'auto',
  ): Promise<void> {
    const target = await this.findById(targetId);
    if (!target) {
      throw new NotFoundException('用户不存在');
    }
    if (!(await this.canManage(operator, target))) {
      throw new ForbiddenException('无权管理该用户');
    }
    await this.userPermissionsRepository.delete({ userId: target.id });
    await this.usersRepository.delete(target.id);
    this.invalidateAuthCache(target.id);
    await this.audit(operator, 'user.delete', 'user', target.id, target.username, {
      jobLevel: target.jobLevel?.name ?? null,
      department: target.department?.name ?? null,
    }, outcome);
  }

  // ---------- 部门管理 ----------

  listDepartments(): Promise<Department[]> {
    return this.departmentsRepository.find({ order: { id: 'ASC' } });
  }

  async createDepartment(
    operator: User,
    dto: CreateDepartmentDto,
    outcome: AuditOutcome = 'auto',
  ): Promise<Department> {
    this.assertConfirm(dto.confirm);
    let parent: Department | null = null;
    if (dto.parentId != null) {
      parent = await this.getDepartmentOrFail(dto.parentId);
    }
    await this.assertDepartmentNameAvailable(dto.name, dto.parentId ?? null);
    const dept = await this.departmentsRepository.save(
      this.departmentsRepository.create({
        name: dto.name,
        parentId: parent?.id ?? null,
      }),
    );
    // 新部门自动获得一套默认职级(高级/中级/初级)
    await this.seedDeptJobLevels(dept.id);
    await this.audit(operator, 'dept.create', 'department', String(dept.id), dept.name, {
      parent: parent?.name ?? null,
    }, outcome);
    return dept;
  }

  async updateDepartment(
    operator: User,
    id: number,
    dto: UpdateDepartmentDto,
    outcome: AuditOutcome = 'auto',
  ): Promise<Department> {
    this.assertConfirm(dto.confirm);
    const dept = await this.getDepartmentOrFail(id);
    const changes: Record<string, unknown> = {};
    if (dto.name !== undefined && dto.name !== dept.name) {
      await this.assertDepartmentNameAvailable(dto.name, dept.parentId ?? null, id);
      changes.name = { from: dept.name, to: dto.name };
      dept.name = dto.name;
    }
    if (dto.parentId !== undefined && dto.parentId !== dept.parentId) {
      if (dto.parentId === null) {
        throw new BadRequestException('不能将部门调整为根部门');
      }
      const newParent = await this.getDepartmentOrFail(dto.parentId);
      await this.assertNoDepartmentCycle(id, newParent.id);
      changes.parent = { from: dept.parentId ?? null, to: newParent.name };
      dept.parentId = newParent.id;
    }
    const saved = await this.departmentsRepository.save(dept);
    if (Object.keys(changes).length) {
      await this.audit(operator, 'dept.update', 'department', String(id), dept.name, changes, outcome);
    }
    return saved;
  }

  async removeDepartment(
    operator: User,
    id: number,
    outcome: AuditOutcome = 'auto',
  ): Promise<void> {
    const dept = await this.getDepartmentOrFail(id);
    if (dept.parentId == null) {
      throw new BadRequestException('根部门不可删除');
    }
    const children = await this.departmentsRepository.count({
      where: { parentId: id },
    });
    if (children > 0) {
      throw new BadRequestException(`该部门仍有 ${children} 个子部门,请先调整`);
    }
    const scope = await this.departmentSubtreeIds(id);
    const usersInScope = await this.usersRepository.count({
      where: { department: { id: In([...scope]) } },
    });
    if (usersInScope > 0) {
      throw new BadRequestException(
        `该部门及子部门仍有 ${usersInScope} 名用户,请先调整这些用户的部门`,
      );
    }
    await this.departmentsRepository.delete(id);
    await this.audit(operator, 'dept.delete', 'department', String(id), dept.name, null, outcome);
  }

  // ---------- 职级管理 ----------

  listJobLevels(departmentId?: number): Promise<JobLevel[]> {
    return this.jobLevelsRepository.find({
      where: departmentId != null ? { departmentId } : {},
      order: { departmentId: 'ASC', rank: 'ASC' },
    });
  }

  async createJobLevel(
    operator: User,
    dto: CreateJobLevelDto,
    outcome: AuditOutcome = 'auto',
  ): Promise<JobLevel> {
    this.assertConfirm(dto.confirm);
    const dept = await this.getDepartmentOrFail(dto.departmentId);
    await this.assertCanConfigDepartment(operator, dept.id);
    // 职级名称/层级均允许重复(同名按层级区分,同层视为并列),不再做唯一性校验
    const level = await this.jobLevelsRepository.save(
      this.jobLevelsRepository.create({
        name: dto.name,
        rank: dto.rank,
        departmentId: dept.id,
      }),
    );
    await this.audit(operator, 'joblevel.create', 'joblevel', String(level.id), level.name, {
      rank: level.rank,
      department: dept.name,
    }, outcome);
    return level;
  }

  async updateJobLevel(
    operator: User,
    id: number,
    dto: UpdateJobLevelDto,
    outcome: AuditOutcome = 'auto',
  ): Promise<JobLevel> {
    this.assertConfirm(dto.confirm);
    const level = await this.getJobLevelOrFail(id);
    await this.assertCanConfigDepartment(operator, level.departmentId);
    const changes: Record<string, unknown> = {};
    if (dto.name !== undefined && dto.name !== level.name) {
      changes.name = { from: level.name, to: dto.name };
      level.name = dto.name;
    }
    if (dto.rank !== undefined && dto.rank !== level.rank) {
      changes.rank = { from: level.rank, to: dto.rank };
      level.rank = dto.rank;
    }
    const saved = await this.jobLevelsRepository.save(level);
    if (Object.keys(changes).length) {
      await this.audit(operator, 'joblevel.update', 'joblevel', String(id), level.name, changes, outcome);
    }
    return saved;
  }

  async removeJobLevel(
    operator: User,
    id: number,
    outcome: AuditOutcome = 'auto',
  ): Promise<void> {
    const level = await this.getJobLevelOrFail(id);
    await this.assertCanConfigDepartment(operator, level.departmentId);
    const totalInDept = await this.jobLevelsRepository.count({
      where: { departmentId: level.departmentId },
    });
    if (totalInDept <= 1) {
      throw new BadRequestException('每个部门至少保留一个职级');
    }
    // 允许删除被引用的职级: users.jobLevelId 外键 onDelete SET NULL 自动置空;
    // 职级权限绑定随职级一并删除(job_level_permissions 外键 CASCADE)
    await this.jobLevelsRepository.delete(level.id);
    await this.audit(operator, 'joblevel.delete', 'joblevel', String(id), level.name, null, outcome);
  }

  // ---------- 审计查询 ----------

  /** 审计查询: 仅超级管理员(守卫已拦截),全量分页 */
  async queryAuditLogs(
    filters: { keyword?: string; days?: number; page?: number },
  ): Promise<{ total: number; items: AuditLog[] }> {
    const days = Math.min(Math.max(filters.days ?? 7, 1), 90);
    const page = Math.max(filters.page ?? 1, 1);
    const pageSize = 50;
    const since = new Date(Date.now() - days * 24 * 3600 * 1000);

    const qb = this.auditRepository
      .createQueryBuilder('a')
      .where('a.createdAt >= :since', { since })
      .orderBy('a.createdAt', 'DESC')
      .skip((page - 1) * pageSize)
      .take(pageSize);

    if (filters.keyword) {
      qb.andWhere(
        '(a.operatorName LIKE :kw OR a.targetName LIKE :kw OR a.action LIKE :kw)',
        { kw: `%${filters.keyword}%` },
      );
    }
    const [items, total] = await qb.getManyAndCount();
    return { total, items };
  }

  // ---------- 内部辅助 ----------

  private async getRootDepartment(): Promise<Department | null> {
    return this.departmentsRepository.findOne({
      where: { parentId: IsNull() },
      order: { id: 'ASC' },
    });
  }

  private async getDepartmentOrFail(id: number): Promise<Department> {
    const dept = await this.departmentsRepository.findOne({ where: { id } });
    if (!dept) throw new NotFoundException('部门不存在');
    return dept;
  }

  private async assertDepartmentNameAvailable(
    name: string,
    parentId: number | null,
    excludeId?: number,
  ): Promise<void> {
    const exists = await this.departmentsRepository.findOne({
      where: parentId == null ? { name, parentId: IsNull() } : { name, parentId },
    });
    if (exists && exists.id !== excludeId) {
      throw new ConflictException('同一父部门下已存在同名部门');
    }
  }

  /** 防环: 从 newParentId 沿 parentId 上溯,遇到自身 id 或深度超限则拒绝 */
  private async assertNoDepartmentCycle(
    id: number,
    newParentId: number,
  ): Promise<void> {
    if (newParentId === id) {
      throw new BadRequestException('不能将部门挂到自身之下');
    }
    let cursor: number | null | undefined = newParentId;
    for (let depth = 0; depth < 20 && cursor != null; depth++) {
      const dept: Department | null = await this.departmentsRepository.findOne({
        where: { id: cursor },
      });
      if (!dept) break;
      if (dept.parentId === id) {
        throw new BadRequestException('不能将部门挂到其子部门之下(会形成环)');
      }
      cursor = dept.parentId;
    }
  }

  private getTopJobLevelOf(departmentId: number): Promise<JobLevel | null> {
    return this.jobLevelsRepository.findOne({
      where: { departmentId },
      order: { rank: 'ASC' },
    });
  }

  private getLowestJobLevelOf(departmentId: number): Promise<JobLevel | null> {
    return this.jobLevelsRepository.findOne({
      where: { departmentId },
      order: { rank: 'DESC' },
    });
  }

  private async getJobLevelOrFail(id: number): Promise<JobLevel> {
    const level = await this.jobLevelsRepository.findOne({ where: { id } });
    if (!level) {
      throw new NotFoundException('职级不存在');
    }
    return level;
  }

  /**
   * 新建用户的当前职级视为最低,只需校验新职级严格低于操作者职级;
   * 超管与本部门经理(全权)豁免。
   */
  private async assertNewUserJobLevel(operator: User, newLevel: JobLevel): Promise<void> {
    if (operator.isSuperAdmin) return;
    const managerScope = await this.managerScopeIds(operator);
    if (managerScope.has(newLevel.departmentId)) return;
    const opRank = operator.jobLevel?.rank ?? LOWEST_RANK;
    if (newLevel.rank <= opRank) {
      throw new ForbiddenException('只能调整为低于自己职级的职级');
    }
  }

  private assertConfirm(confirm?: boolean): void {
    if (confirm !== true) {
      throw new BadRequestException('请先确认操作');
    }
  }

  private async assertUsernameEmailAvailable(
    username?: string,
    email?: string,
  ): Promise<void> {
    if (username) {
      const exists = await this.findByUsername(username);
      if (exists) throw new ConflictException('用户名已存在');
    }
    if (email) {
      const exists = await this.findByEmail(email);
      if (exists) throw new ConflictException('邮箱已被注册');
    }
  }

  private async audit(
    operator: User,
    action: string,
    targetType: string,
    targetId: string,
    targetName: string,
    detail: Record<string, unknown> | null,
    outcome: AuditOutcome,
  ): Promise<void> {
    await this.auditService.write({
      operatorId: operator.id,
      operatorName: operator.displayName ?? operator.username,
      action,
      targetType,
      targetId,
      targetName,
      detail,
      outcome,
    });
  }
}
