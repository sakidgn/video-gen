FROM python:3.12-slim
WORKDIR /app
COPY saas/requirements.txt /tmp/req.txt
RUN pip install --no-cache-dir -r /tmp/req.txt
COPY saas /app/saas
ENV VERI_KLASORU=/veri PORT=8000
VOLUME /veri
EXPOSE 8000
CMD ["python", "-m", "saas"]
