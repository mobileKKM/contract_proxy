FROM python:3.9-slim
LABEL maintainer="David Sn <divad.nnamtdeis@gmail.com>"

# Install dependencies
RUN set -ex && \
    DEBIAN_FRONTEND=noninteractive \
    apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy app files
WORKDIR /app
ADD requirements.txt .
RUN pip install -r requirements.txt
ADD . ./
ENTRYPOINT ["uvicorn", "main:app"]

CMD ["--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl --silent --fail http://localhost:8080/healthcheck || exit 1
