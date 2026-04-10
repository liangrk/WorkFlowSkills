# Android Shared Detection Module

> This is a shared reference module containing consolidated environment detection scripts.
> Skills that need project environment detection should link to this document rather than
> duplicating the detection logic. Each skill still contains its own inline detection code
> for self-contained execution, but this document serves as the canonical reference.

---

## 1. Project Root Detection

Locate the Android project root by searching upward for git repo root + build.gradle.

```bash
# Project root
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$PROJECT_ROOT" ]; then
  echo "ERROR: Not a git repository"
  exit 1
fi

# Confirm Android project
if [ ! -f "$PROJECT_ROOT/build.gradle" ] && [ ! -f "$PROJECT_ROOT/build.gradle.kts" ] && \
   [ ! -f "$PROJECT_ROOT/app/build.gradle" ] && [ ! -f "$PROJECT_ROOT/app/build.gradle.kts" ] && \
   [ ! -f "$PROJECT_ROOT/settings.gradle" ] && [ ! -f "$PROJECT_ROOT/settings.gradle.kts" ]; then
  echo "ERROR: Not an Android project (missing build.gradle / settings.gradle)"
  exit 1
fi

echo "PROJECT_ROOT: $PROJECT_ROOT"
```

---

## 2. Gradle Wrapper Detection

Check for the Gradle wrapper and ensure it is executable.

```bash
# Gradle wrapper
if [ -f "$PROJECT_ROOT/gradlew" ]; then
  [ ! -x "$PROJECT_ROOT/gradlew" ] && chmod +x "$PROJECT_ROOT/gradlew"
  echo "GRADLE_WRAPPER: available"
  ./gradlew --version 2>&1 | head -3
else
  echo "GRADLE_WRAPPER: not found"
fi

# Gradle directory
ls "$PROJECT_ROOT/gradle" 2>/dev/null && echo "GRADLE_DIR"
```

---

## 3. Base Branch Detection

Determine the base branch (main or master) for diff operations.

```bash
# Determine base branch (main or master)
BASE_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH=$(git branch -r | grep -E 'origin/(main|master)' | head -1 | sed 's@.*origin/@@' | tr -d ' ')
fi
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH="main"
fi

# Current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

echo "BASE_BRANCH: $BASE_BRANCH"
echo "CURRENT_BRANCH: $CURRENT_BRANCH"
```

---

## 4. Tech Stack Detection

Scan the project to detect frameworks and libraries. Produce a tech stack profile.

### 4.1 UI Framework

```bash
# Compose detection
grep -r "androidx.compose" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
grep -rl "@Composable" "$PROJECT_ROOT/app/src" 2>/dev/null | head -5

# XML Views detection
find "$PROJECT_ROOT/app/src/main/res/layout" -name "*.xml" 2>/dev/null | head -5
```

### 4.2 Async Framework

```bash
grep -r "kotlinx.coroutines" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
grep -rl "import kotlinx.coroutines" "$PROJECT_ROOT/app/src" 2>/dev/null | head -5
grep -rl "import io.reactivex" "$PROJECT_ROOT/app/src" 2>/dev/null | head -5
```

### 4.3 Dependency Injection

```bash
grep -r "com.google.dagger:hilt" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
grep -r "io.insert-koin" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
```

### 4.4 Network Library

```bash
grep -r "com.squareup.retrofit2" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
grep -r "io.ktor" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
```

### 4.5 Database

```bash
grep -r "androidx.room" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
grep -r "app.cash.sqldelight" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
```

### 4.6 Image Loading

```bash
grep -r "io.coil-kt" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
grep -r "com.github.bumptech.glide" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
```

### 4.7 Navigation

```bash
grep -r "androidx.navigation" "$PROJECT_ROOT/app/build.gradle" "$PROJECT_ROOT/app/build.gradle.kts" 2>/dev/null
```

### 4.8 Output Tech Stack Profile

```
=== Tech Stack Profile ===
UI:         Compose / XML Views / Mixed
Async:      Coroutines / RxJava / None
DI:         Hilt / Koin / None
Network:    Retrofit / Ktor / None
Database:   Room / SQLDelight / None
Image:      Coil / Glide / None
Navigation: Navigation Compose / Navigation Component / None
```

---

## 5. Architecture Pattern Detection

Detect the project's architecture pattern from package structure and code patterns.

```bash
# Read package structure
find "$PROJECT_ROOT/app/src/main/java" -type d 2>/dev/null | head -20
find "$PROJECT_ROOT/app/src/main/kotlin" -type d 2>/dev/null | head -20

# Detect layer keywords
grep -rl "ViewModel" "$PROJECT_ROOT/app/src" 2>/dev/null | head -5
grep -rl "Repository" "$PROJECT_ROOT/app/src" 2>/dev/null | head -5
grep -rl "UseCase\|Interactor" "$PROJECT_ROOT/app/src" 2>/dev/null | head -5
grep -rl "Reducer\|Action\|Event" "$PROJECT_ROOT/app/src" 2>/dev/null | head -5
```

**Inference rules:**
- `ui/` + `viewmodel/` + `repository/` -> MVVM
- `presentation/` + `domain/` + `data/` -> Clean Architecture
- `reducer/` + `action/` + `state/` -> MVI
- Other -> Record observed pattern

**Output:**
```
=== Architecture ===
Inferred: MVVM
Package: com.example.app.ui / .viewmodel / .repository / .data.remote
Note: Inference only, does not constrain plan
```

---

## 6. Gradle Command Patterns

Standard Gradle commands used across all Android skills.

### 6.1 Build

```bash
# Debug build (primary verification)
./gradlew assembleDebug 2>&1
BUILD_EXIT=$?

# Release build (when needed)
./gradlew assembleRelease 2>&1
```

### 6.2 Test

```bash
# JVM unit tests (default variant: Debug)
./gradlew testDebugUnitTest 2>&1
TEST_EXIT=$?

# Instrumented tests (requires device/emulator)
./gradlew connectedDebugAndroidTest 2>&1
```

### 6.3 Lint

```bash
# Lint check
./gradlew lintDebug 2>&1
LINT_EXIT=$?

# Lint report locations
# HTML: app/build/reports/lint-results-debug.html
# XML:  app/build/reports/lint-results-debug.xml
```

### 6.4 Coverage (JaCoCo)

```bash
# Run tests with coverage
./gradlew testDebugUnitTest 2>&1

# Find JaCoCo reports
JACOCO_XML=$(find "$PROJECT_ROOT" -path "*/reports/jacoco/*/*.xml" -type f 2>/dev/null | head -1)
JACOCO_HTML=$(find "$PROJECT_ROOT" -path "*/reports/jacoco/*/index.html" -type f 2>/dev/null | head -1)
```

---

## Consuming Skills

The following skills reference this shared detection module:

| Skill | Detection Sections Used |
|-------|------------------------|
| android-autoplan | Project Root, Tech Stack, Architecture, Gradle Commands |
| android-tdd | Project Root, Gradle Wrapper, Gradle Commands |
| android-worktree-runner | Project Root, Gradle Commands |
| android-qa | Project Root, Base Branch, Tech Stack, Gradle Commands |
| android-code-review | Project Root, Tech Stack, Architecture |
| android-investigate | Project Root, Tech Stack |

> 以下 skill 有独立的检测逻辑 (包含 Figma MCP、文档 diff 等专项检测)，不引用本模块:
> android-design-review, android-document-release, android-checkpoint, android-brainstorm
