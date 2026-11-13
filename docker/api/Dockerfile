FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY pyproject.toml ./
# 依赖层与业务源码分开；改接口/Worker时不必重新下载全部包。
RUN --mount=type=cache,id=sesrag-api-pip,target=/root/.cache/pip \
    python -c "import pathlib,tomllib; p=tomllib.loads(pathlib.Path('pyproject.toml').read_text()); pathlib.Path('/tmp/runtime-requirements.txt').write_text('\n'.join(p['project']['dependencies']))" \
    && pip install --retries 3 --timeout 120 'setuptools>=69' wheel -r /tmp/runtime-requirements.txt \
    && python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"

COPY backend ./backend
COPY migrations ./migrations
COPY alembic.ini ./

RUN pip install --no-deps --no-build-isolation .

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]

