FROM python:3.9-slim-buster

COPY requirements.txt /ghist/
WORKDIR /ghist
RUN pip install -r requirements.txt
COPY . /ghist

ENTRYPOINT ["python", "ghist-botkeeper.py"]
CMD []
