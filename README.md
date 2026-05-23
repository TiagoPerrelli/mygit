# mygit
## Sobre
É um projeto individual que fiquei com o interesse de ver se consigo recriar o git de uma forma simplificada. Ele será para uso pessoal, de acordo com minhas preferências.

## Setup
Basicamente alterar a variável de ambiente PATH no windows e adicionar o local onde está localizado o mygit.py do seu pc. Além disso, alterar o endereço no mygit.bat pra facilitar.
Dessa forma, será possível basicamente botar mygit no terminal e irá funcionar direito.

Para ter interação com o GDrive, precisa instalar a seguinte biblioteca:
```bash
# Biblioteca
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

# Guia de setup de comunicação com repositório do GDrive:
python mygit.py gdrive-setup
```


## O que faz?
Suporte aos seguintes comandos no terminal:
```bash
# Inicializa um repositório no diretório atual
python mygit.py init
python mygit.py init --author "Seu Nome"

# Exibe o status atual (branch, HEAD, arquivos no stage)
python mygit.py status

# Exibe o histórico de commits da branch ativa
python mygit.py log
```

### Arquivos

```bash
# Adiciona um arquivo ao stage
python mygit.py add arquivo.txt

# Adiciona todos os arquivos recursivamente (respeita o .mygitignore)
python mygit.py add .

# Cria um commit com os arquivos no stage
python mygit.py commit -m "mensagem do commit"

# Compara um arquivo com a versão do último commit
python mygit.py diff arquivo.txt
```

### Branches

```bash
# Lista todas as branches (* indica a ativa)
python mygit.py branch

# Cria uma nova branch a partir do commit atual
python mygit.py branch --new nome-da-branch

# Troca para outra branch (restaura o snapshot dela)
python mygit.py branch --checkout nome-da-branch

# Faz merge de uma branch na branch ativa
python mygit.py merge nome-da-branch
```

> O merge usa o algoritmo **three-way merge**. Se houver conflito (mesmo arquivo alterado de formas diferentes nas duas branches), o merge é abortado e os arquivos conflitantes são listados.

### Remoto local

```bash
# Define uma pasta local como repositório remoto
python mygit.py remote ./caminho/do/remoto

# Envia commits locais para o remoto
python mygit.py push

# Baixa commits do remoto para o local
python mygit.py pull
```

### Google Drive

```bash
# Exibe o guia completo de configuração
python mygit.py gdrive-setup

# Envia commits locais para o Drive
python mygit.py gdrive-push

# Baixa os commits mais recentes do Drive
python mygit.py gdrive-pull

# Restaura um commit específico pelo hash (não altera o HEAD local)
python mygit.py gdrive-pull --hash 2cf5035b

# Lista os commits salvos no Drive
python mygit.py gdrive-log

# Mostra quantos commits locais ainda não foram enviados
python mygit.py gdrive-status
```
Tem interface interativa com o seguinte comando:
```python
python mygit.py gui
```

# EM DESENVOLVIMENTO
Intenção de criar comandos fetch, ajustar para salvar png, entre outros...