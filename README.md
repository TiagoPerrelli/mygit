# mygit
## Sobre
É um projeto individual que fiquei com o interesse de ver se consigo recriar o git de uma forma simplificada. Ele será para uso pessoal, de acordo com minhas preferências.

## Setup
Basicamente alterar a variável de ambiente PATH no windows e adicionar o local onde está localizado o mygit.py do seu pc. Além disso, alterar o endereço no mygit.bat pra facilitar.
Dessa forma, será possível basicamente botar mygit no terminal e irá funcionar direito.

## O que faz?
Suporte aos seguintes comandos no terminal:
```python
mygit init --author "Seu Nome"
mygit add meu_arquivo.py
mygit commit -m "feat: primeiro commit"
mygit log
mygit diff meu_arquivo.py
mygit remote ../meu_remoto
mygit push
mygit pull
mygit branch              # lista todas as branches
mygit branch --new feat   # cria branch 'feat'
mygit branch --checkout feat  # troca para 'feat'
mygit merge feat          # merge de 'feat' na branch ativa
```
Tem interface interativa com o seguinte comando:
```python
python mygit.py gui
```

# EM DESENVOLVIMENTO
