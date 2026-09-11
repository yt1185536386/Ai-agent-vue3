import { Type } from 'class-transformer';
import {
  IsArray,
  IsBoolean,
  IsEmail,
  IsIn,
  IsInt,
  IsOptional,
  IsString,
  Length,
  MaxLength,
  Min,
  MinLength,
  ValidateNested,
} from 'class-validator';
import { DeptPosition } from './users.entity';

const DEPT_POSITIONS = [
  DeptPosition.MANAGER,
  DeptPosition.DEPUTY,
  DeptPosition.LEADER,
  DeptPosition.MEMBER,
] as const;

export class CreateUserDto {
  /** 登录用户名(唯一) */
  @IsString()
  @MinLength(3)
  @MaxLength(32)
  username: string;

  /** 初始密码 */
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

  /** 职级(可空,缺省为最低职级;只能指派低于操作者自己的职级) */
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  jobLevelId?: number;

  /** 所属部门(可空;非超管缺省归本部门,超管缺省归根部门) */
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  departmentId?: number;

  /** 部门内职位(可空,缺省组员;经理限 1 / 副经理限 2,名额校验在服务层) */
  @IsOptional()
  @IsIn(DEPT_POSITIONS)
  deptPosition?: DeptPosition;

  /** 二次确认硬门槛(Human-in-the-Loop),服务层校验必须为 true */
  @IsOptional()
  @IsBoolean()
  confirm?: boolean;
}

/** 更新:全部字段可选;confirm 为二次确认硬门槛 */
export class UpdateUserDto {
  @IsOptional()
  @IsString()
  @MaxLength(100)
  displayName?: string;

  @IsOptional()
  @IsEmail()
  @MaxLength(120)
  email?: string;

  /** 重置密码(可空) */
  @IsOptional()
  @IsString()
  @MinLength(6)
  @MaxLength(64)
  newPassword?: string;

  /** 状态: 1 启用 / 0 禁用 */
  @IsOptional()
  @Type(() => Number)
  @IsIn([0, 1])
  status?: 0 | 1;

  /** 职级调整: 上级调下级,新职级须低于操作者自己 */
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  jobLevelId?: number;

  /** 转岗: 非超管限本部门子树;调部门后部门职位缺省重置为组员 */
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  departmentId?: number;

  /** 部门内职位调整: 经理限 1 / 副经理限 2,名额校验在服务层 */
  @IsOptional()
  @IsIn(DEPT_POSITIONS)
  deptPosition?: DeptPosition;

  /** 二次确认硬门槛(Human-in-the-Loop),服务层校验必须为 true */
  @IsOptional()
  @IsBoolean()
  confirm?: boolean;
}

export class CreateJobLevelDto {
  /** 职级名称 */
  @IsString()
  @Length(1, 50)
  name: string;

  /** 层级数值,越小级别越高 */
  @Type(() => Number)
  @IsInt()
  @Min(1)
  rank: number;

  /** 所属部门(职级按部门划分) */
  @Type(() => Number)
  @IsInt()
  departmentId: number;

  /** 二次确认硬门槛(Human-in-the-Loop),服务层校验必须为 true */
  @IsOptional()
  @IsBoolean()
  confirm?: boolean;
}

export class UpdateJobLevelDto {
  @IsOptional()
  @IsString()
  @Length(1, 50)
  name?: string;

  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  rank?: number;

  /** 二次确认硬门槛(Human-in-the-Loop),服务层校验必须为 true */
  @IsOptional()
  @IsBoolean()
  confirm?: boolean;
}

export class CreateDepartmentDto {
  /** 部门名称(同一父部门下唯一) */
  @IsString()
  @Length(1, 64)
  name: string;

  /** 父部门 id(可空,缺省挂根层级) */
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  parentId?: number;

  /** 二次确认硬门槛(Human-in-the-Loop),服务层校验必须为 true */
  @IsOptional()
  @IsBoolean()
  confirm?: boolean;
}

export class UpdateDepartmentDto {
  @IsOptional()
  @IsString()
  @Length(1, 64)
  name?: string;

  /** 改父级(防环校验;不允许调整为根) */
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  parentId?: number;

  /** 二次确认硬门槛(Human-in-the-Loop),服务层校验必须为 true */
  @IsOptional()
  @IsBoolean()
  confirm?: boolean;
}

/** 职级批量绑定: 全量覆盖该职级的权限点集合 */
export class SetJobLevelPermsDto {
  @IsArray()
  @IsString({ each: true })
  codes: string[];
}

/** 个人权限覆盖项: allowed 为 null 表示删除该条覆盖(回到继承职级) */
export class UserPermOverrideItem {
  @IsString()
  code: string;

  @IsOptional()
  @IsBoolean()
  allowed?: boolean | null;
}

/** 个人单独绑定: 全量覆盖该用户的个人权限覆盖项 */
export class SetUserPermsDto {
  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => UserPermOverrideItem)
  overrides: UserPermOverrideItem[];
}
