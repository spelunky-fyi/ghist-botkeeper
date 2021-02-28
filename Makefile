docker-build:
	docker build -t ghist-bot:docker .

docker-run:
	docker run --name=ghist-botkeeper.service --rm -it ghist-bot:docker

docker-bash:
	docker exec -it ghist-botkeeper.service /bin/bash
