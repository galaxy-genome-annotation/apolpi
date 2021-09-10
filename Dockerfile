FROM python:3.9.7-slim-buster

RUN mkdir /apolpi

WORKDIR /apolpi

COPY requirements.txt requirements.txt

RUN apt-get -q update \
    && DEBIAN_FRONTEND=noninteractive apt-get -yq --no-install-recommends install libpq5 libpq-dev gcc libc6-dev \
    && pip install -r requirements.txt \
    && apt-get purge -y --auto-remove libpq-dev gcc libc6-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY apolpi.py boot.sh ./
RUN chmod +x boot.sh

ENV FLASK_APP apolpi.py
EXPOSE 80

ENTRYPOINT ["/apolpi/boot.sh"]
