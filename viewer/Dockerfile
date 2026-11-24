FROM python:3.12-slim
WORKDIR /app
COPY server.py call_logs.py ./
COPY static ./static
USER 65534:65534
EXPOSE 8090
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s CMD python -c "from urllib.request import urlopen; urlopen('http://localhost:8090/health', timeout=2)"
CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8090"]
