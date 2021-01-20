docker-build:
	docker build -t ghist-bot:docker .

docker-run:
	docker run --env-file=ghist-bot.env --name=ghist-bot --rm -it ghist-bot:docker

docker-run-detached:
	docker run --env-file=ghist-bot.env --name=ghist-bot -d ghist-bot:docker

docker-stop:
	docker stop ghist-bot
	docker rm ghist-bot

docker-bash:
	docker exec -it ghist-bot /bin/bash
