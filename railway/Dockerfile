FROM python:3.12-slim
# video-library Railway 서버: 표준 라이브러리만 쓰므로 설치할 패키지가 없다.
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 VL_HOME=/data
WORKDIR /srv
COPY plugin/video-library/skills/video-library/scripts ./scripts
COPY plugin/video-library/skills/video-library/web ./web
EXPOSE 8080
CMD ["python", "scripts/vl.py", "serve", "--hosted"]
