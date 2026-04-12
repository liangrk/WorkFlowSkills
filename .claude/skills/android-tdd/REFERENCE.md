# Android TDD -- 参考文档

> 本文件包含 SKILL.md 中不常用的参考章节。
> 仅在特定条件下需要时，由 SKILL.md 引导 Read 此文件。

---

### Phase 0.5: 测试基础设施引导 (按需)

**触发条件:** Phase 0 检测到以下任意缺失:
- 无测试框架依赖 (JUnit4/5)
- 无 Mock 框架 (MockK/Mockito)
- 无断言库 (Truth/AssertJ)
- 无 JaCoCo 覆盖率工具配置
- 无测试目录结构 (`app/src/test/` 不存在或为空)

**不触发条件:** 所有测试基础设施齐全 → 跳过此阶段，输出 "Phase 0.5: 跳过 (测试基础设施齐全)"。

**流程:**

1. 生成缺失项列表:
   ```
   检测到以下测试基础设施缺失:
   - ❌ JUnit5 依赖
   - ❌ MockK 依赖
   - ✅ Truth 断言库 (已配置)
   - ❌ JaCoCo 覆盖率配置
   - ❌ 测试目录结构
   ```

2. 使用 AskUserQuestion:
   > 检测到测试基础设施缺失。是否自动配置?
   > - A) 全部自动配置
   > - B) 仅配置缺失项
   > - C) 跳过，我手动配置

3. 如果用户选择 A 或 B，执行以下操作:

   **添加测试依赖** (根据 Phase 0 检测结果选择版本):
   ```kotlin
   // app/build.gradle.kts - dependencies 块
   testImplementation("junit:junit:5:<version>")
   testImplementation("io.mockk:mockk:<version>")
   testImplementation("com.google.truth:truth:<version>")
   ```

   **创建测试目录结构:**
   ```
   app/src/test/java/com/example/<module>/
     ├── <ClassName>Test.kt
     └── fixtures/           ← 测试夹具数据
   ```

   **配置 JaCoCo** (在 app/build.gradle.kts 的 android 块中):
   ```kotlin
   testImplementation("jacoco-org.jacoco:org.jacoco.agent:<version>")
   ```

   ```kotlin
   // android 块中
   testCoverageEnabled = true
   ```

   ```kotlin
   // app/build.gradle.kts 顶层 (after plugins)
   jacoco { toolVersion = "<version>" }
   ```

   **创建验证测试:**
   ```kotlin
   import org.junit.Test
   import com.google.common.truth.Truth.assertThat

   class SmokeTest {
       @Test
       fun `test infrastructure works`() {
           assertThat(true).isTrue()
       }
   }
   ```

4. 运行验证:
   ```bash
   ./gradlew testDebugUnitTest $GRADLE_OPTS --tests ".*SmokeTest" 2>&1 | tail -10
   ```

5. 验证通过后，提示: "测试基础设施配置完成。可以继续 TDD 流程。"

---

## Phase 6: 自动修复循环

当 Phase 2-5 中任何阶段失败时，进入自动修复循环。
4 轮循环，严重程度逐级升级。

### 进入条件

以下任一情况触发 Phase 6:
- Phase 2 (RED): 测试意外通过 (非预期行为)
- Phase 3 (GREEN): 测试仍然失败 (实现有误)
- Phase 4 (REFACTOR): 重构后测试失败
- Phase 5 (Coverage): 覆盖率不达标 (2 轮补充后仍不足)

### Round 1: 机械修复 (自动，无需用户确认)

**目标:** 修复编译错误、配置错误、简单语法问题。

**自动修复范围:**

| 问题类型 | 修复方式 | 示例 |
|---------|---------|------|
| 缺少 import | 添加对应 import 语句 | `import java.io.IOException` |
| 类型不匹配 | 修正变量/返回类型 | `String` → `Int` |
| Mock 配置错误 | 修正 when/thenReturn | `coEvery { ... } returns ...` |
| 测试注解缺失 | 添加 @Test / @Before | JUnit5 注解 |
| 错误的测试运行器 | 修正 @RunWith | `MockKJUnitRunner` |
| 方法签名不匹配 | 修正参数或返回值 | 对齐接口定义 |
| 空安全错误 | 添加 ?./!! 修正 | `user?.email` |

**执行方式:**
1. 读取错误信息
2. 定位出错的文件和行号
3. 使用 Edit 工具直接修复
4. 重新运行测试

**输出:**
```
=== Round 1: 机械修复 ===
自动修复: N 个问题
  ✅ [F1-001] 缺少 import java.io.IOException
  ✅ [F1-002] Mock 返回类型不匹配
  ✅ [F1-003] 缺少 @OptIn 注解

重新运行测试...
结果: N/N passed ✅ → 覆盖率检查...
```

### Round 2: 逻辑修复 (Subagent 根因分析 + 用户确认)

**触发条件:** Round 1 后测试仍然失败。

**目标:** 深入分析失败的根本原因，提出修复方案。

**执行方式:**

1. 收集失败信息:
   - 失败测试的完整错误消息
   - 失败测试的源码
   - 被测实现的源码
   - Phase 1 的契约定义

2. 派发独立 subagent 进行根因分析:
```
使用 Agent 工具派发:

你是 Android 测试调试专家。分析以下测试失败的根本原因。

契约定义:
<Phase 1 的接口/类型定义>

失败测试代码:
<测试源码>

被测实现代码:
<实现源码>

错误信息:
<测试运行输出>

你的任务:
1. 分析失败的根本原因 (不是表面症状)
2. 判断是测试问题还是实现问题
3. 提出具体的修复方案 (包含代码片段)
4. 评估修复后是否可能引入新问题

输出格式:
- 根因: <一句话描述>
- 修复方案: <具体代码变更>
- 风险评估: <低/中/高>
```

3. 展示修复方案给用户确认:
```
Round 2 分析完成:

根因: Repository 实现中未处理网络超时，导致 ViewModel 测试失败
修复方案: 在 AuthRepositoryImpl 中添加 timeout 配置
风险: 低

是否应用修复?
- A) 应用修复
- B) 跳过，手动处理
- C) 修改修复方案
```

4. 应用修复后重新运行测试

**输出:**
```
=== Round 2: 逻辑修复 ===
Subagent 分析: 1 个根因
  根因: Repository 未处理超时
  修复: 添加 withTimeout 配置
  用户确认: ✅ 已应用

重新运行测试...
结果: N/N passed ✅
```

### Round 3: 架构修复 (报告 + 用户介入)

**触发条件:** Round 2 后测试仍然失败。

**目标:** 问题可能出在架构层面，需要用户决策。

**执行方式:**

1. 生成详细诊断报告:
```
=== Round 3: 架构修复 ===

经过 2 轮修复仍未解决。问题可能是架构层面的。

诊断报告:
  失败测试: LoginViewModelTest.testLoginSuccess
  错误类型: IllegalStateException
  错误位置: LoginViewModel.kt:45
  根因分析: ViewModel 直接持有 Repository 的 MutableLiveData 引用，
           导致在测试中无法隔离。需要通过接口抽象或 StateFlow 解耦。

建议方案:
  A) 回到 Phase 1 重新定义契约 — 将 Repository 返回类型改为 Flow<Result<T>>
  B) 简化测试范围 — 暂时不测试此边界条件
  C) 手动修复 — 由用户直接修改代码
```

2. 使用 AskUserQuestion 让用户选择处理方式

3. 如果用户选择 A: 回到 Phase 1，重新定义契约后重新走 Phase 2-5
4. 如果用户选择 B: 标记该测试为已知限制，继续
5. 如果用户选择 C: 暂停 TDD 流程，等待用户手动修复

### Round 4: 独立验收 Subagent (无上下文继承)

**触发条件:** Round 1-3 完成后（无论是否全部修复），进行独立验收。

**核心原则:** 此 subagent 不继承主对话的任何上下文。
只注入 Phase 1 的契约定义和最终代码。避免确认偏见。

**执行方式:**

1. 派发独立验收 subagent:
```
使用 Agent 工具派发:

你是独立的代码验收员。你不了解任何背景信息，只根据提供的材料进行评估。

## 材料

契约定义 (Phase 1 产出):
<契约定义的接口和类型>

最终测试代码:
<所有测试文件的路径，让 subagent 自己读取>

最终实现代码:
<所有实现文件的路径，让 subagent 自己读取>

覆盖率报告 (Phase 5 产出):
<覆盖率数据>

## 你的任务

评估以下维度:

1. **契约合规性:** 实现是否完全满足契约定义?
2. **测试充分性:** 测试是否覆盖了 happy path + edge cases + error paths?
3. **覆盖率达标:** 是否满足 80% 总体 / 90% 关键路径?
4. **代码质量:** 命名是否清晰? 是否有不必要的复杂性?
5. **Android 最佳实践:** 是否遵循 Android 编码规范?

## 输出格式

结论: PASS / CONDITIONAL PASS / FAIL

如果是 CONDITIONAL PASS 或 FAIL:
- 问题列表 (每项一行，包含文件路径和建议)
- 严重程度: Critical / Important / Minor

如果是 PASS:
- 简要确认 (1-2 句话)
```

2. 处理验收结果:

| 验收结果 | 处理 |
|---------|------|
| PASS | 进入 Phase 7 |
| CONDITIONAL PASS | 记录问题，进入 Phase 7，在报告中标注 |
| FAIL | 回到 Round 1，附带验收报告作为新上下文 (最多 1 次重试) |
| FAIL (重试后仍失败) | 停止 TDD，输出完整诊断报告给用户 |

### 循环终止条件

```
修复循环终止:
  ✅ 所有测试通过 + Round 4 PASS → Phase 7
  ⚠️ Round 4 CONDITIONAL PASS → Phase 7 (报告标注条件性通过)
  ❌ Round 4 FAIL (重试后) → 停止，输出诊断报告
  🛑 用户在任何轮次选择停止 → 保存当前状态
```

### 修复循环记录格式

```
=== 修复循环摘要 ===
Round 1 (机械修复): 3 个问题自动修复
Round 2 (逻辑修复): 1 个根因，用户确认后修复
Round 3: 未触发
Round 4 (独立验收): PASS
总耗时: ~5 分钟
```

---

## 文件结构

```
项目根目录/
├── docs/
│   └── reviews/
│       ├── <branch>-tdd-report.md          ← 本 skill 产出的 TDD 报告
│       └── <branch>-qa-report.md           ← android-qa 产出 (后续)
└── ...
```

---

## 异常情况处理

| 场景 | 处理方式 |
|------|----------|
| 不在 git 仓库中 | 报错: "android-tdd 需要 git 仓库" |
| 不是 Android 项目 | 报错: "未检测到 Android 项目" |
| Gradle 不可用 | 报错: "gradlew 未找到或不可执行" |
| JaCoCo 未配置 | 提示配置 JaCoCo，使用测试通过率替代 |
| 无设备/模拟器 | 跳过 Instrumented 测试，记录受影响测试 |
| 修复循环 4 轮后仍失败 | 恢复到 TDD 前状态 (`git stash pop` 恢复 savepoint)，输出完整诊断报告。已通过的测试和实现代码保留在工作区供用户参考 |
| 用户中断修复循环 | 保存当前状态，记录到 tasks.json |
| worktree-runner 未找到 tasks.json | 以独立模式运行，不更新 TDD 状态 |
| Gradle 依赖拉取失败 (网络问题) | 切换到阿里云镜像后重试 (见下方 Gradle 网络回退策略) |

### Gradle 网络回退策略

当运行 `./gradlew` 命令时，如果遇到 AGP 或其他依赖因网络问题无法拉取的错误
（如 `Connection timed out`、`Unable to resolve`、`Could not GET` 等），自动切换到阿里云镜像:

1. **检测到网络拉取失败后**，在项目根目录的 `settings.gradle` 或 `settings.gradle.kts` 中
   配置阿里云 Maven 镜像:

   **settings.gradle.kts:**
   ```kotlin
   dependencyResolutionManagement {
       // repositoriesMode 保留项目原有配置，不要覆盖
       repositories {
           maven { url = uri("https://maven.aliyun.com/repository/google") }
           maven { url = uri("https://maven.aliyun.com/repository/central") }
           maven { url = uri("https://maven.aliyun.com/repository/public") }
           google()
           mavenCentral()
       }
   }
   ```

   **settings.gradle (Groovy):**
   ```groovy
   dependencyResolutionManagement {
       // repositoriesMode 保留项目原有配置，不要覆盖
       repositories {
           maven { url 'https://maven.aliyun.com/repository/google' }
           maven { url 'https://maven.aliyun.com/repository/central' }
           maven { url 'https://maven.aliyun.com/repository/public' }
           google()
           mavenCentral()
       }
   }
   ```

2. 阿里云镜像仓库放在 `google()` 和 `mavenCentral()` **之前**，确保优先从镜像拉取。
3. 配置完成后重新运行失败的 Gradle 命令。
4. **注意:** 仅在检测到网络拉取失败时才添加镜像配置，不要主动修改用户已有的仓库配置。
   不要覆盖项目原有的 `repositoriesMode` 设置。
5. **回滚:** 如果添加镜像后仍然失败，移除镜像配置恢复原状，提示用户检查网络代理或 VPN 设置。
