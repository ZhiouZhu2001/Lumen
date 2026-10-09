# Official Python image with slim variant for smaller size
FROM python:3.12-slim

# get the uv tool
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /uvx /bin/

# All following commands will be run inside the /app directory
WORKDIR /app

# Settings for uv tool
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy code
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

# Document the port, and start the server reachable from outside the container
EXPOSE 8001

# Apply database migrations, then start the server
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8001"]