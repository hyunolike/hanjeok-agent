plugins {
    kotlin("jvm") version "2.2.21"
    kotlin("plugin.spring") version "2.2.21"
    id("org.springframework.boot") version "4.1.0"
    id("io.spring.dependency-management") version "1.1.7"
}

group = "com.hermes"
version = "0.1.0"

kotlin {
    jvmToolchain(21)
    compilerOptions { freeCompilerArgs.add("-Xjsr305=strict") }
}

sourceSets {
    main {
        kotlin.srcDir("server/src/main/kotlin")
        resources.srcDir("server/src/main/resources")
    }
    test {
        kotlin.srcDir("server/src/test/kotlin")
        resources.srcDir("server/src/test/resources")
    }
    // 평가는 단위 테스트가 아니다 — 돈이 들고 비결정적이라 `./gradlew test` 에 섞이면 안 된다.
    create("harness") {
        kotlin.srcDir("harness/src/main/kotlin")
        compileClasspath += sourceSets.main.get().output
        runtimeClasspath += sourceSets.main.get().output
    }
}

val harnessImplementation: Configuration by configurations.getting {
    extendsFrom(configurations.implementation.get())
}

repositories { mavenCentral() }

dependencyManagement {
    imports {
        mavenBom("org.springframework.modulith:spring-modulith-bom:2.1.0")
        mavenBom("org.springframework.ai:spring-ai-bom:2.0.1")
    }
}

dependencies {
    implementation("org.springframework.boot:spring-boot-starter")
    implementation("org.jetbrains.kotlin:kotlin-reflect")
    implementation("org.springframework.ai:spring-ai-anthropic")
    implementation("org.springframework.ai:spring-ai-openai")
    implementation("org.springframework.ai:spring-ai-client-chat")
    implementation("com.anthropic:anthropic-java:2.52.0")
    implementation("com.openai:openai-java:4.49.0")
    implementation("com.fasterxml.jackson.module:jackson-module-kotlin")
    implementation("org.springframework.boot:spring-boot-starter-webmvc")
    implementation("org.springframework.boot:spring-boot-starter-restclient")
    implementation("org.springframework.boot:spring-boot-starter-actuator")
    implementation("org.springframework.modulith:spring-modulith-starter-core")
    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testImplementation("org.springframework.modulith:spring-modulith-starter-test")
    testImplementation("org.springframework.boot:spring-boot-starter-webmvc-test")
}

tasks.test { useJUnitPlatform() }

/**
 * 프로젝트 루트의 `.env` 를 읽어 돈 쓰는 태스크에만 환경변수로 넘긴다.
 *
 * `.env` 는 `.gitignore` 에 있다. 이 저장소는 공개이므로, 키가 추적되는 순간
 * 되돌릴 수 없다 — 커밋을 지워도 이미 공개된 키는 폐기하는 것 말고 방법이 없다.
 * 그래서 이 파일은 절대 커밋되면 안 되고, 아래 doFirst 가 매 실행마다 그것을
 * 확인한다.
 *
 * 형식은 `KEY=value` 또는 `export KEY=value`, 한 줄에 하나. `#` 로 시작하는 줄은
 * 주석이다.
 */
fun readDotEnv(): Map<String, String> {
    val file = rootProject.file(".env")
    if (!file.exists()) return emptyMap()
    return file.readLines()
        .map { it.trim() }
        .filter { it.isNotEmpty() && !it.startsWith("#") }
        .mapNotNull { line ->
            val body = line.removePrefix("export ").trim()
            val separator = body.indexOf('=')
            if (separator <= 0) {
                null
            } else {
                body.substring(0, separator).trim() to
                    body.substring(separator + 1).trim().removeSurrounding("\"").removeSurrounding("'")
            }
        }
        .toMap()
}

/**
 * 값은 절대 찍지 않는다 — 이름과 "비었는지"만 보고한다.
 *
 * 빈 값을 조용히 통과시키면 실행은 401 로 실패하고, 그 401 은 "키가 틀렸다"와
 * "키를 넣다 말았다"를 구분해 주지 않는다. 실제로 그 혼동이 한 번 있었다.
 */
fun JavaExec.applyDotEnv() {
    val values = readDotEnv()
    values.forEach { (key, value) -> environment(key, value) }

    doFirst {
        val tracked = providers.exec {
            commandLine("git", "ls-files", "--error-unmatch", ".env")
            isIgnoreExitValue = true
        }.result.get().exitValue == 0
        check(!tracked) {
            ".env is tracked by git. This repository is public — remove it from the index " +
                "and rotate every key it contains before continuing."
        }

        if (values.isEmpty()) {
            logger.lifecycle("no .env found — relying on the ambient environment")
        } else {
            val blank = values.filterValues { it.isBlank() }.keys
            logger.lifecycle("loaded from .env: ${values.keys.sorted().joinToString(", ")}")
            check(blank.isEmpty()) {
                "these .env entries have an empty value: ${blank.sorted().joinToString(", ")}. " +
                    "An empty key is not a missing key — it reaches the provider and comes back 401, " +
                    "which reads like a wrong key rather than an unfinished edit."
            }
        }
    }
}

// Spring AI 2.0.1 은 victools 5.0.0 을 끌어온다. 그런데 Anthropic SDK 의 구조화
// 출력이 4.x 시그니처를 부르므로, 5.0.0 이 이기면 스키마 유도가 런타임에
// NoSuchMethodError 로 죽는다. 컴파일은 통과하므로 이 핀이 유일한 방어선이다.
// DependencyPinTest 가 이것을 지킨다.
configurations.all {
    resolutionStrategy.force(
        "com.github.victools:jsonschema-generator:4.38.0",
        "com.github.victools:jsonschema-module-jackson:4.38.0",
        "com.github.victools:jsonschema-module-swagger-2:4.38.0",
    )
}

tasks.register<JavaExec>("eval") {
    group = "verification"
    description = "금지 행동 8종을 센다. API 키가 필요하고 실제 비용이 발생한다."
    classpath = sourceSets["harness"].runtimeClasspath
    mainClass.set("com.hermes.harness.EvalMainKt")
    applyDotEnv()
}

tasks.register<JavaExec>("demoReachability") {
    group = "verification"
    description = "고정 데모 코스가 한적에서 아직 조회되는지 확인한다. 한적 호출이 발생한다."
    classpath = sourceSets["harness"].runtimeClasspath
    mainClass.set("com.hermes.harness.DemoReachabilityMainKt")
    applyDotEnv()
}
