FROM ubuntu:18.04

ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update && apt-get install -y tzdata python3.8 python3-pip

ADD https://github.com/ufoscout/docker-compose-wait/releases/download/2.6.0/wait /usr/bin/waitc
RUN chmod +x /usr/bin/waitc

# Uncomment to setup timezone
# ENV TZ=Europe/Moscow
# RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /srv
ADD requirements.txt .
RUN python3.8 -m pip install -r requirements.txt

ADD aiopypay ./aiopypay
