# CruxHive UI — read-only workspace dashboard.
# Mounts host /workspace (one or more project .llm/ dirs) and serves the
# cross-project review/dashboard UI on port 3847.
FROM python:3.12-slim

WORKDIR /opt/cruxhive

# System deps (none beyond Python — sqlite3 is in stdlib)
RUN pip install --no-cache-dir --upgrade pip

# Install cruxhive-mcp with UI extras from the build context
COPY . /opt/cruxhive/src
RUN pip install --no-cache-dir '/opt/cruxhive/src[ui]'

ENV CRUXHIVE_WORKSPACE=/workspace
EXPOSE 3847

# Host 0.0.0.0 so it's reachable through Docker; workspace mode = cross-project
CMD ["cruxhive-ui", "--host", "0.0.0.0", "--port", "3847", "--workspace"]
