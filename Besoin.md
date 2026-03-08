# Home Assistant iOS Notification Addon

## Description

Development of a native Home Assistant addon in Go, specialized in advanced notification management and business logic for iOS. This project adopts a Hexagonal Architecture (Ports & Adapters) to decouple decision logic from Home Assistant APIs, ensuring full testability through a TDD (Test-Driven Development) approach and complete lifecycle automation (DevSecOps).

## Objectives

- **Modularity**: Isolate the "Core" from Home Assistant API changes.
- **Reliability (TDD)**: 100% of iOS notification logic covered by tests prior to implementation.
- **iOS Experience**: Native support for critical notifications, rich actions, and dynamic badge management.
- **Full Automation**: Automated management of versions, dependencies, and infrastructure security.

## Architecture (Hexagonal)

The project will be structured to separate the What (Business) from the How (Technical):

- **`/internal/domain`**: Pure data models (Notification, Device, Event).
- **`/internal/core`**:
  - **Services**: iOS decision logic (e.g., priority calculation).
  - **Ports**: Interfaces defining how the Core communicates with the outside world (e.g., `HassPort`, `ConfigPort`).
- **`/internal/adapter`**:
  - **Hass**: WebSocket/REST implementation (HA Client).
  - **Config**: Reading `/data/options.json`.
- **`/cmd/addon`**: Initialization and Dependency Injection (DI). We will favor manual DI or Google Wire for compile-time safety instead of reflection-based frameworks.

## Acceptance Criteria

### Development & Code (TDD Approach)

- [ ] **TDD Cycle**: Every core feature must have its `_test.go` file written before the logic.
- [ ] **Mocks**: Use mocks for ports (interfaces) to test the rules engine without a Home Assistant instance.
- [ ] **Dependency Injection**: Use a clean DI pattern in `cmd/addon` (Manual or Wire) to wire adapters to the core.
- [ ] **Standardization**: Use Conventional Commits to enable automated releases.
- [ ] **Taskfile**: Implementation of a `Taskfile.yml` for development commands (build, test, local lint).

### Quality & Security (DevSecOps)

- [ ] **Coverage**: Minimum 80% coverage for the `/internal/core` directory.
- [ ] **Linting**: `golangci-lint` for Go and `hadolint` for the Dockerfile.
- [ ] **Security Scans**:
  - `trivy` for dependency and Docker image vulnerabilities.
  - `KICS` to scan the Dockerfile and addon configuration (IaC security).

### CI/CD & Automation (GitHub Actions)

- [ ] **Renovate Bot**: Configuration for automatic updates of Docker base images, GitHub Actions, and Go modules.
- [ ] **Release Please**: Automation of tags, GitHub releases, and `CHANGELOG.md` generation.
- [ ] **Validation Pipeline**: PR workflow including tests, lints (Go/Docker), and security scans.
- [ ] **Multi-Arch Build**: Compilation via `docker/build-push-action` for amd64, aarch64, and armv7.
- [ ] **Addon Linter**: Validation of the addon's `config.yaml` via `ha-addon-linter`.

## Development Strategy

1. **Setup**: Configure Renovate, Release Please, lints (Hadolint/KICS), and define the DI strategy (Manual/Wire).
2. **Red**: Write a test for an iOS notification rule (e.g., critical alert if battery < 5%).
3. **Green**: Implement the minimum code in `/internal/core` to pass the test.
4. **Refactor**: Optimize the code and move to the next rule.
5. **Adapter**: Implement technical adapters and finalize the multi-stage Dockerfile.
