# Leilão de Aliyot — Yamim Noraim

Site de leilão de aliyot para Rosh Hashaná e Yom Kipur da Kehilat Or Israel.

As regras de negócio, o escopo e as decisões do projeto estão em `CLAUDE.md`.

## Rodar localmente

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python seed.py
python app.py
```

O site sobe em http://127.0.0.1:5000

Sem `DATABASE_URL` definida, o banco é um arquivo SQLite local (`aliyot.db`).
Em produção o Railway fornece a `DATABASE_URL` do MySQL e o mesmo código roda
sem alteração.

## Estrutura

```
app.py         aplicação Flask e rotas
config.py      configuração lida de variáveis de ambiente
models.py      Occasion, Aliyah, Bid
seed.py        cria as tabelas e carrega as ocasiões e as aliyot
templates/     HTML renderizado no servidor
static/        CSS e imagens
```
