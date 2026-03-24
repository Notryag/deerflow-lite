# 06 Documentation Governance

## Document Role

- Purpose: 定义文档规范、更新流程、冲突处理和维护约束
- Audience: 所有维护者、AI CLI、后续协作者
- Source of truth for: 文档治理规则

## 1. Governance Goals

文档治理必须同时服务两个目标：

- 让人能快速判断项目边界和实现方式
- 让 AI 能低成本读取、保持上下文一致、直接执行

## 2. Documentation Structure Rules

仓库文档必须遵守以下规则：

- 根 README 只做入口和导航
- 每个主题只有一个 source-of-truth 文档
- 新文档必须放在 `docs/` 下，并使用有序编号
- 文档名必须直接表达主题，不用模糊命名

## 3. Required Document Header

新的规范类文档 SHOULD 统一包含以下三个小节：

- `Document Role`
- `Purpose`
- `Source of truth for`

如果文档承担规范职责，就不应省略这些信息。

## 4. Normative Language

规范文档必须使用统一措辞：

- `MUST`: 强制要求
- `SHOULD`: 默认要求，允许有明确理由的偏离
- `MAY`: 可选项
- `MUST NOT`: 禁止项

避免使用以下模糊措辞作为规范结论：

- 建议
- 尽量
- 可以先
- 看情况
- 以后再说

这些词只能出现在说明性文字里，不能代替规范。

## 5. Conflict Resolution

文档冲突时，按以下规则处理：

1. 主题文档优先于根 README
2. 更具体的 contract 优先于更宽泛的描述
3. 如果 scope 和实现细节冲突，以 scope 文档为准，先收缩实现
4. 如果测试标准和实现计划冲突，以测试和验收文档为准

发生冲突时，必须在同一次修改中完成统一，不允许长期共存。

## 6. Change Triggers

出现以下情况时，必须同步更新文档：

- 新增或移除 MVP 能力
- 修改目录结构
- 修改 `RunState` 字段
- 修改任一 tool I/O
- 修改 agent 输出结构
- 修改测试门槛或验收标准
- 把 stub 替换成真实能力

## 7. Update Checklist

每次更新规范前，先执行以下检查：

1. 这次变更属于哪个 source-of-truth 文档
2. 是否有其他文档引用了旧约束
3. 是否需要同步更新测试或验收条件
4. 是否会影响 AI 的读取顺序或上下文裁剪建议

## 8. Duplication Policy

为保证上下文一致性，文档必须控制重复：

- README 可以摘要，但不得复制完整规范
- 一个 contract 只能在一个地方做主定义
- 其他文档引用时应链接，不应重新表述一遍

## 9. Maintenance Policy

维护时遵守以下原则：

- 先改 source of truth，再改引用文档
- 同一次变更里完成文档和实现同步
- 对废弃内容，要删除或明确标注 deprecated
- 不保留过期 TODO，TODO 必须可执行且可归档

## 10. Recommended Review Routine

每次较大改动后，建议按以下顺序复核文档：

1. `01` 检查边界是否被突破
2. `02` 检查架构和目录是否一致
3. `03` 检查 state、agent、tool contract 是否漂移
4. `05` 检查测试和完成定义是否仍成立

## 11. Documentation Quality Bar

高质量规范文档至少应满足：

- 能被拆分读取
- 能直接指导实现
- 能支持测试设计
- 能定位唯一事实来源
- 能在半年后仍可维护
