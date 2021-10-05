docker-build:
	docker build -t ghist-bot:docker .

docker-run:
	docker run --name=ghist-botkeeper.service --rm -it ghist-bot:docker

docker-bash:
	docker exec -it ghist-botkeeper.service /bin/bash

link-prod:
	ln -sf ghist-bot.prod.env ghist-bot.env
	ln -sf ghist-bot-config.prod.json ghist-bot-config.json

link-dev:
	ln -sf ghist-bot.dev.env ghist-bot.env
	ln -sf ghist-bot-config.dev.json ghist-bot-config.json
