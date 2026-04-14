# Android 实战知识库

> 所有 android-* skill 共享。模型在执行任何 skill 前,先读取此文件获取 Android 特有知识。

## Gradle 实战

### 构建加速

```bash
# 永远使用 --parallel --configure-on-demand
./gradlew assembleDebug --parallel --configure-on-demand -Dorg.gradle.daemon=true

# 增量编译开启 (gradle.properties)
org.gradle.parallel=true
org.gradle.configureondemand=true
org.gradle.caching=true
```

### 常见构建失败

| 错误 | 原因 | 解法 |
|------|------|------|
| `Manifest merger failed` | 权限/SDK 版本冲突 | `<tools:replace="android:xxx">` |
| `Duplicate class` | 依赖传递冲突 | `./gradlew :app:dependencies` 查树,`exclude` 排除 |
| `Could not resolve` | 仓库顺序错 | `google()` 必须在 `mavenCentral()` 前面 |
| `AGP 版本不兼容` | Gradle/AGP 不匹配 | 查 compatibility table,同步升级 |

### 模块依赖顺序

```
app → feature → domain → data → core
```

永远不要反向依赖。Circular dependency = 架构问题。

## Compose 实战

### 重组陷阱

```kotlin
// ❌ 错误: 每次重组都创建新对象
@Composable fun MyScreen() {
    val state = remember { mutableStateOf(0) }
    LaunchedEffect(Unit) { ... } // Unit 导致无限重组
}

// ✅ 正确
@Composable fun MyScreen() {
    var count by remember { mutableIntStateOf(0) }
    LaunchedEffect(key1 = count) { ... } // 有明确 key
}
```

### 性能要点

- `derivedStateOf` 用于减少不必要的重组
- `LazyColumn` 永远比 `Column + for` 高效
- `Modifier` 链顺序影响布局 (padding 在 background 前面)

## AndroidManifest 合并

```xml
<!-- 主 Manifest 优先级 > library Manifest -->
<!-- 冲突解决: -->
<application tools:replace="android:icon,android:theme">
    <activity tools:node="merge" />  <!-- 合并 -->
    <activity tools:node="remove" />  <!-- 删除 -->
</application>
```

## 测试实战

### 单元测试 (JUnit 5 + MockK)

```kotlin
@Test fun `test name`() = runTest {
    // given
    every { mock.doSomething() } returns "result"
    // when
    val actual = subject.action()
    // then
    assertEquals("expected", actual)
}
```

### UI 测试 (Compose Testing)

```kotlin
@Test fun testClick() {
    composeTestRule.setContent { MyComposable() }
    composeTestRule.onNodeWithText("Click Me").performClick()
    composeTestRule.onNodeWithText("Done").assertIsDisplayed()
}
```

## 线程模型

| 任务 | 线程 | API |
|------|------|-----|
| UI 更新 | Main | `withContext(Dispatchers.Main)` |
| 网络请求 | IO | `viewModelScope.launch(Dispatchers.IO)` |
| CPU 计算 | Default | `withContext(Dispatchers.Default)` |
| Room 数据库 | IO (自动) | `@Query` 自动切线程 |

**永远不要在 Main 线程做 IO/CPU 密集操作。**

## 生命周期要点

- `ViewModel` 在配置变更时存活,在 `onDestroy()` 后销毁
- `LaunchedEffect` 随 Composable 进入/离开 composition
- `rememberSaveable` 在进程被杀后恢复状态

## 资源管理

- `dimens.xml` 管理尺寸,不要硬编码 dp
- `strings.xml` 管理文本,支持多语言
- `colors.xml` 管理色值,支持深色模式
- 图片放 `drawable/`,向量图优先 (`vectorDrawables.useSupportLibrary = true`)

## 依赖注入 (Hilt)

```kotlin
@HiltAndroidApp class MyApp : Application()
@AndroidEntryPoint class MainActivity : AppCompatActivity()
@Module @InstallIn(SingletonComponent::class) class AppModule {
    @Provides fun provideRepo(): Repository = ...
}
```

## 网络 (Retrofit + OkHttp)

```kotlin
interface ApiService {
    @GET("users/{id}") suspend fun getUser(@Path("id") id: String): User
}
// 永远用 suspend 函数,自动切到 IO 线程
```

## 数据库 (Room)

```kotlin
@Database(entities = [User::class], version = 1)
abstract class AppDatabase : RoomDatabase() {
    abstract fun userDao(): UserDao
}
// migration: version++ + Migration(1,2){...}
```

## 常见 Bug 模式

| Bug | 症状 | 根因 | 修复 |
|-----|------|------|------|
| Context 泄漏 | OOM, ANR | 静态持有 Activity Context | 用 Application Context |
| 内存泄漏 | 内存持续增长 | 未取消的协程/监听器 | `viewModelScope` 自动取消 |
| ANR | 应用无响应 5s+ | Main 线程阻塞 | 切到 IO/Default 线程 |
| ClassCastException | 类型转换失败 | Layout 中 view 类型错 | 检查 XML 中 class 属性 |
| NullPointerException | 空指针 | View 未初始化 | `findViewById` 检查 null |
