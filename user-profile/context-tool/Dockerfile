FROM python:3.12-slim
WORKDIR /app
COPY generate.py server.py crosswalk.json form.html ./
# The viewer's styles.css and favicon.svg are mounted read-only at /app/viewer-static (docker-compose.yml).
ENV VIEWER_STATIC=/app/viewer-static PYTHONDONTWRITEBYTECODE=1
USER 65534:65534
EXPOSE 8095
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s CMD python -c "from urllib.request import urlopen; urlopen('http://localhost:8095/health', timeout=2)"
CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8095"]
