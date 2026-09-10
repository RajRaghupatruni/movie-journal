# Production image for Render's single same-origin web service.
FROM node:22-bookworm-slim AS frontend-build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html vite.config.js tsconfig.json eslint.config.js tailwind.config.js postcss.config.cjs ./
COPY src ./src
COPY public ./public
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY backend/pyproject.toml backend/requirements.lock ./
RUN pip install --no-cache-dir --requirement requirements.lock \
    && useradd --create-home --system tandem
COPY backend/app ./app
COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
RUN pip install --no-cache-dir --no-deps .
COPY --from=frontend-build /src/dist ./dist
RUN chown -R tandem:tandem /app
USER tandem
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*' --no-access-log"]
