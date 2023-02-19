# syntax=docker/dockerfile:1

FROM python:3.11-slim-buster

# Install build-essential package and sqlite3
RUN apt-get update && \
    apt-get install -y gnupg2 && \
    echo "deb http://security.debian.org/debian-security stretch/updates main" >> /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y libsqlite3-dev
    
WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]