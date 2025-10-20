# -*- coding: utf-8 -*-
"""
padronizar_urls.py

- Cria colunas ausentes:
    - streams.source_tag_filmes (VARCHAR(255), NULL)
    - streams_series.source_tag  (VARCHAR(255), NULL)
- Normaliza stream_source (JSON list):
    - lista de URLs (strings), trim, remove vazias e duplicadas, mantém ordem
- Preenche:
    - Filmes (streams.type=2): source_tag_filmes = dominio:porta da 1ª URL, se vazio
    - Séries: source_tag = dominio:porta majoritário entre episódios, se vazio

Seguro para rodar em banco com dados existentes (apenas UPDATEs in-place).
"""

import json
import re
import mysql.connector
from urllib.parse import urlparse
from getpass import getpass

AZUL = "\033[94m"
VERDE = "\033[92m"
AMARELO = "\033[93m"
VERMELHO = "\033[91m"
RESET = "\033[0m"

def log(msg): print(msg)

def conectar():
    while True:
        try:
            log(f"{AZUL}\nInforme os dados do seu banco de dados MySQL:{RESET}")
            host = input("Host: ").strip()
            port_input = input("Porta (padrão 3306): ").strip()
            user = input("Usuário: ").strip()
            password = getpass("Senha: ")
            database = input("Nome do Banco de Dados: ").strip()
            port = int(port_input) if port_input else 3306
            c = mysql.connector.connect(host=host, user=user, password=password, database=database, port=port)
            log(f"{VERDE}Conexão bem-sucedida!{RESET}")
            return c
        except Exception as e:
            log(f"{VERMELHO}Erro ao conectar: {e}{RESET}")
            if input("Tentar novamente? (S/N): ").strip().lower() != 's':
                raise

def coluna_existe(cur, schema, tabela, coluna):
    cur.execute("""
        SELECT COUNT(*) 
        FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s
    """, (schema, tabela, coluna))
    return cur.fetchone()[0] > 0

def criar_coluna(cur, conn, schema, tabela, coluna, ddl_tipo):
    if not coluna_existe(cur, schema, tabela, coluna):
        log(f"{AMARELO}Coluna '{coluna}' não encontrada em {tabela}. Criando...{RESET}")
        cur.execute(f"ALTER TABLE `{schema}`.`{tabela}` ADD COLUMN `{coluna}` {ddl_tipo}")
        conn.commit()
        log(f"{VERDE}Coluna '{coluna}' criada com sucesso.{RESET}")
    else:
        log(f"{AZUL}Coluna '{coluna}' já existe em {tabela}.{RESET}")

def json_list_normalizada(valor):
    """
    Retorna (lista_normalizada, mudou_bool, primeira_url_ou_none)
    - aceita string JSON de lista, ou uma string simples (URL), ou None/''.
    - remove vazias, duplicaçao preservando ordem.
    """
    mudou = False
    urls = []

    if not valor:
        return [], False, None

    # tentar JSON
    try:
        data = json.loads(valor)
        if isinstance(data, list):
            candidatos = data
        elif isinstance(data, str):
            candidatos = [data]
            mudou = True
        else:
            candidatos = []
            mudou = True
    except Exception:
        # se não for JSON, tratar como URL simples
        candidatos = [valor]
        mudou = True

    # normalizar / filtrar
    vistos = set()
    for x in candidatos:
        if not isinstance(x, str):
            mudou = True
            continue
        u = x.strip()
        if not u:
            mudou = True
            continue
        if u not in vistos:
            vistos.add(u)
            urls.append(u)
        else:
            mudou = True

    primeira = urls[0] if urls else None
    # Se originalmente já era lista "igual", mudou permanece False; para simplificar,
    # se recompactamos/limpamos, 'mudou' True.
    return urls, mudou, primeira

def extrair_tag(url):
    """
    Retorna 'dominio:porta' a partir da URL.
    Porta inferida: https->443, http->80 quando ausente.
    Domínio em minúsculas.
    """
    try:
        p = urlparse(url)
        host = (p.hostname or "").lower()
        if not host:
            return None
        if p.port:
            porta = p.port
        else:
            if p.scheme == "https":
                porta = 443
            else:
                porta = 80
        return f"{host}:{porta}"
    except Exception:
        return None

def padronizar_streams(cur, conn, schema):
    """
    - Normaliza streams.stream_source (todos os tipos)
    - Para tipo=2 (filmes), preenche streams.source_tag_filmes se vazio
    Retorna contadores.
    """
    log(f"{AZUL}\n1) Normalizando STREAMS (todas as linhas) e preenchendo source_tag_filmes para filmes...{RESET}")
    cur.execute(f"SELECT id, type, stream_source, source_tag_filmes FROM `{schema}`.`streams`")
    rows = cur.fetchall()

    upd_stream_source = 0
    upd_filmes_tag = 0
    total = len(rows)

    for (sid, stype, stream_source, tag_atual) in rows:
        # normalizar lista
        lista, mudou, primeira = json_list_normalizada(stream_source)
        if mudou:
            novo_json = json.dumps(lista, ensure_ascii=False)
            cur.execute(f"UPDATE `{schema}`.`streams` SET stream_source=%s WHERE id=%s", (novo_json, sid))
            upd_stream_source += 1

        # Filmes (type=2): set source_tag_filmes se vazio e se houver 1ª URL válida
        if stype == 2:
            vazio = (tag_atual or "").strip() == ""
            if vazio and primeira:
                tag = extrair_tag(primeira)
                if tag:
                    cur.execute(f"UPDATE `{schema}`.`streams` SET source_tag_filmes=%s WHERE id=%s", (tag, sid))
                    upd_filmes_tag += 1

    conn.commit()
    log(f"{VERDE}Streams normalizados: {upd_stream_source}/{total} JSONs ajustados.{RESET}")
    log(f"{VERDE}Filmes com source_tag_filmes preenchido: {upd_filmes_tag}.{RESET}")
    return upd_stream_source, upd_filmes_tag, total

def padronizar_series(cur, conn, schema):
    """
    Para cada série:
      - busca episódios (streams.type=5) ligados via streams_episodes
      - calcula domínio:porta mais frequente entre a 1ª URL de cada episódio
      - se streams_series.source_tag estiver vazio -> preenche com o majoritário
    Retorna contadores.
    """
    log(f"{AZUL}\n2) Preenchendo source_tag em STREAMS_SERIES (com base nos episódios)...{RESET}")
    # pegar séries com o campo vazio
    cur.execute(f"SELECT id, title, source_tag FROM `{schema}`.`streams_series`")
    series_rows = cur.fetchall()

    upd_series_tag = 0
    analisadas = 0
    total = len(series_rows)

    for (series_id, title, tag_atual) in series_rows:
        if (tag_atual or "").strip():
            continue  # já tem tag

        # buscar episódios da série
        cur.execute(f"""
            SELECT s.stream_source
            FROM `{schema}`.`streams_episodes` se
            JOIN `{schema}`.`streams` s ON s.id = se.stream_id
            WHERE se.series_id = %s AND s.type = 5
        """, (series_id,))
        eps = cur.fetchall()

        if not eps:
            continue

        # contar domínio:porta pela 1ª URL de cada episódio
        cont = {}
        for (stream_source,) in eps:
            lista, _, primeira = json_list_normalizada(stream_source)
            if not primeira:
                continue
            tag = extrair_tag(primeira)
            if not tag:
                continue
            cont[tag] = cont.get(tag, 0) + 1

        if not cont:
            continue

        # maior frequência
        major_tag = max(cont.items(), key=lambda kv: kv[1])[0]

        cur.execute(f"UPDATE `{schema}`.`streams_series` SET source_tag=%s WHERE id=%s", (major_tag, series_id))
        upd_series_tag += 1
        analisadas += 1

    conn.commit()
    log(f"{VERDE}Séries atualizadas com source_tag: {upd_series_tag}/{total}.{RESET}")
    return upd_series_tag, total

def main():
    conn = conectar()
    cur = conn.cursor()

    # Descobrir schema atual (database)
    cur.execute("SELECT DATABASE()")
    schema = cur.fetchone()[0]

    # 1) Criar colunas se faltarem
    criar_coluna(cur, conn, schema, "streams", "source_tag_filmes", "VARCHAR(255) NULL")
    criar_coluna(cur, conn, schema, "streams_series", "source_tag", "VARCHAR(255) NULL")

    # 2) Padronizar streams (normalização + source_tag_filmes)
    padronizar_streams(cur, conn, schema)

    # 3) Padronizar séries (source_tag a partir dos episódios)
    padronizar_series(cur, conn, schema)

    cur.close()
    conn.close()
    log(f"{AZUL}\nConcluído com sucesso.{RESET}")

if __name__ == "__main__":
    main()
