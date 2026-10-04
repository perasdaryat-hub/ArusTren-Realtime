FROM python:3.12-slim
WORKDIR /app
COPY server.py ./
COPY public ./public
RUN mkdir -p /data
ENV PORT=3000
ENV DB_PATH=/data/arustren.sqlite
VOLUME ["/data"]
EXPOSE 3000
CMD ["python","server.py"]