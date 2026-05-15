FROM python:3.12-slim

WORKDIR /app

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ src/
COPY tests/ tests/

# Upgrade pip first to avoid build issues
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel -i https://mirrors.aliyun.com/pypi/simple/

# Install package
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -e .

# Install ALL system dependencies required by Chromium (without downloading browser)
# This covers libxkbcommon, libgbm, libnss3, fonts, etc. - everything CloakBrowser needs
RUN playwright install-deps chromium

# --- CloakBrowser Chromium (anti-detection patched binary) ---
# Pre-download the archive before building:
#   Linux x64:  curl -LO https://cloakbrowser.dev/chromium-v146.0.7680.177.3/cloakbrowser-linux-x64.tar.gz
#   Linux arm64: curl -LO https://cloakbrowser.dev/chromium-v146.0.7680.177.3/cloakbrowser-linux-arm64.tar.gz
#
# Place the downloaded file in the same directory as this Dockerfile, then:
#   docker build -t agent-browser .
#
# To use Playwright's default Chromium instead (no anti-detection), see Dockerfile.playwright

# Copy and extract CloakBrowser patched Chromium
ARG CLOAKBROWSER_ARCHIVE=cloakbrowser-linux-x64.tar.gz
COPY ${CLOAKBROWSER_ARCHIVE} /tmp/cloakbrowser.tar.gz
RUN mkdir -p /root/.cloakbrowser/chromium-146.0.7680.177.3 \
    && tar -xzf /tmp/cloakbrowser.tar.gz -C /root/.cloakbrowser/chromium-146.0.7680.177.3 \
    && rm -f /tmp/cloakbrowser.tar.gz \
    # Flatten single top-level directory if archive wraps contents in one folder
    && cd /root/.cloakbrowser/chromium-146.0.7680.177.3 \
    && count=$(ls -1 | wc -l) \
    && if [ "$count" -eq 1 ] && [ -d "$(ls -1)" ]; then \
         d=$(ls -1); mv "$d"/* . 2>/dev/null; rmdir "$d" 2>/dev/null || true; \
       fi \
    # Ensure chrome binary is executable
    && chmod +x /root/.cloakbrowser/chromium-146.0.7680.177.3/chrome 2>/dev/null || true

# Point agent-browser to the CloakBrowser binary
ENV CLOAKBROWSER_BINARY_PATH=/root/.cloakbrowser/chromium-146.0.7680.177.3/chrome

# Create data directory
RUN mkdir -p /root/.agent-browser

# Default to CLI
ENTRYPOINT ["ab"]
CMD ["--help"]
