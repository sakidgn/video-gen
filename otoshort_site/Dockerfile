FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 VERI_KLASORU=/veri PORT=8000
WORKDIR /app
COPY saas/requirements.txt /tmp/req.txt
RUN pip install --no-cache-dir -r /tmp/req.txt \
 && python -c "import imageio_ffmpeg; imageio_ffmpeg.get_ffmpeg_exe()" \
 && useradd --create-home --uid 1000 app && mkdir -p /veri && chown app:app /veri
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
COPY saas /app/saas
VOLUME /veri
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%s/saglik' % os.environ.get('PORT', '8000'), timeout=4).status == 200 else 1)"
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "-m", "saas"]
