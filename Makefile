docker-build:
	docker build -t ghist-bot:docker .

docker-run:
	docker run --name=ghist-bot --rm -it ghist-bot:docker

docker-stop:
	docker stop ghist-bot
	docker rm ghist-bot

docker-bash:
	docker exec -it ghist-bot /bin/bash
