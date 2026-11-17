ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /tools
COPY telemetry_fixture.py volume_inspector.py fixture_server.py /tools/
USER 65534:65534
CMD ["python", "/tools/telemetry_fixture.py", "sink"]
