variable "GITHUB_REPOSITORY" {}
variable "GITHUB_REF_NAME" {}
variable "GITHUB_SHA" {}
variable "REGISTRY" {}

# Function to sanitize Docker tag names by replacing invalid characters
# Docker tags specification allows: a-z, A-Z, 0-9, _, ., -
# This function normalizes to lowercase and replaces invalid characters with dashes
# Also trims leading and trailing dashes to ensure valid Docker tag format
function "sanitize" {
  params = [tag]
  result = trimprefix(
    trimsuffix(
      lower(
        replace(
          replace(
            replace(
              replace(
                replace(tag, "[", "-"),
                "]", "-"
              ),
              "/", "-"
            ),
            ":", "-"
          ),
          " ", "-"
        )
      ),
      "-"
    ),
    "-"
  )
}

# Strip the "v" prefix from version tags (v0.1.0 → 0.1.0)
function "strip_v" {
  params = [tag]
  result = trimprefix(tag, "v")
}

group "default" {
  targets = ["frigate-event-manager"]
}

variable "IMAGE" {
  default = "${REGISTRY}/${sanitize(GITHUB_REPOSITORY)}"
}

# Base target : push main → tag "main"
target "frigate-event-manager" {
  context    = "."
  dockerfile = "Dockerfile"
  platforms  = ["linux/amd64", "linux/arm64"]
  tags       = ["${IMAGE}:${sanitize(GITHUB_REF_NAME)}"]
  cache-from = ["type=gha"]
  cache-to   = ["type=gha,mode=max"]
  labels = {
    "org.opencontainers.image.source"   = "https://github.com/${GITHUB_REPOSITORY}"
    "org.opencontainers.image.revision" = "${GITHUB_SHA}"
  }
}

# Stable release : v1.0.0 → tags "1.0.0" + "latest"
target "release" {
  inherits = ["frigate-event-manager"]
  tags = [
    "${IMAGE}:${strip_v(sanitize(GITHUB_REF_NAME))}",
    "${IMAGE}:latest",
  ]
}

# Prerelease : v1.0.0-rc1 → tag "1.0.0-rc1" seulement (pas de latest)
target "prerelease" {
  inherits = ["frigate-event-manager"]
  tags = [
    "${IMAGE}:${strip_v(sanitize(GITHUB_REF_NAME))}",
  ]
}
