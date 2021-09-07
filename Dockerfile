FROM python:3.9-slim
LABEL maintainer="David Sn <divad.nnamtdeis@gmail.com>"
WORKDIR /app
ADD requirements.txt .
RUN pip install -r requirements.txt
ADD . ./
ENTRYPOINT ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
