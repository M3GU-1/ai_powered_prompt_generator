#!/bin/bash
# Package the project into a distributable zip/tar.gz
set -e

VERSION="${1:-v1.0.0}"
PKG_NAME="sd-prompt-tag-generator-${VERSION}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DIST_DIR="${PROJECT_ROOT}/dist"

echo "=== Packaging ${PKG_NAME} ==="

rm -rf "${DIST_DIR}/${PKG_NAME}"
mkdir -p "${DIST_DIR}/${PKG_NAME}"

# Copy files
cp -r "${PROJECT_ROOT}/backend" "${DIST_DIR}/${PKG_NAME}/backend/"
cp -r "${PROJECT_ROOT}/frontend" "${DIST_DIR}/${PKG_NAME}/frontend/"
cp -r "${PROJECT_ROOT}/scripts" "${DIST_DIR}/${PKG_NAME}/scripts/"
cp "${PROJECT_ROOT}/danbooru_tags.csv" "${DIST_DIR}/${PKG_NAME}/"
cp "${PROJECT_ROOT}/anima_danbooru.csv" "${DIST_DIR}/${PKG_NAME}/"
cp "${PROJECT_ROOT}/config.example.yaml" "${DIST_DIR}/${PKG_NAME}/"
cp "${PROJECT_ROOT}/requirements.txt" "${DIST_DIR}/${PKG_NAME}/"
cp "${PROJECT_ROOT}/start.sh" "${DIST_DIR}/${PKG_NAME}/"
cp "${PROJECT_ROOT}/start.bat" "${DIST_DIR}/${PKG_NAME}/"
cp "${PROJECT_ROOT}/README.md" "${DIST_DIR}/${PKG_NAME}/"

# Clean up Python cache
find "${DIST_DIR}/${PKG_NAME}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "${DIST_DIR}/${PKG_NAME}" -name "*.pyc" -delete 2>/dev/null || true

# Ensure scripts are executable
chmod +x "${DIST_DIR}/${PKG_NAME}/start.sh"
chmod +x "${DIST_DIR}/${PKG_NAME}/scripts/"*.sh 2>/dev/null || true

# Create archives
cd "${DIST_DIR}"
zip -r "${PKG_NAME}.zip" "${PKG_NAME}/"
tar -czf "${PKG_NAME}.tar.gz" "${PKG_NAME}/"

# Cleanup temp directory
rm -rf "${DIST_DIR}/${PKG_NAME}"

echo ""
echo "=== Done ==="
echo "  ${DIST_DIR}/${PKG_NAME}.zip"
echo "  ${DIST_DIR}/${PKG_NAME}.tar.gz"
