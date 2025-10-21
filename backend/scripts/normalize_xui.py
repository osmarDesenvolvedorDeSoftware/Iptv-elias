#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Script de compatibilidade para padronizar o banco XUI."""

from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass
from getpass import getpass
from typing import Iterable, Sequence
from urllib.parse import urlparse

import mysql.connector
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursor
from mysql.connector.errors import Error

AZUL = "\033[94m"
VERDE = "\033[92m"
AMARELO = "\033[93m"
VERMELHO = "\033[91m"
RESET = "\033[0m"

_ADULT_KEYWORDS = {
    "adulto",
    "xxx",
    "sexo",
    "porn",
    "18+",
    "hot",
    "erotic",
    "x x x",
    "xxx ",
}


@dataclass(slots=True)
class StreamSummary:
    total: int = 0
    normalizados: int = 0
    filmes_tag: int = 0


@dataclass(slots=True)
class SeriesSummary:
    total: int = 0
    atualizadas: int = 0


def log(message: str) -> None:
    try:
        print(message)
    except UnicodeEncodeError:
        print(message.encode("ascii", "ignore").decode())


def _scalar(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, dict):
        try:
            return int(next(iter(value.values())) or 0)
        except StopIteration:
            return 0
    if isinstance(value, (list, tuple)):
        return int(value[0] or 0)
    return int(value)


def categoria_adulta(nome: str | None = None, generos: Iterable[str] | None = None) -> bool:
    if generos:
        for genero in generos:
            if genero and genero.strip().lower() in {"adult", "erotica"}:
                return True
    if not nome:
        return False
    return any(chave in nome.lower() for chave in _ADULT_KEYWORDS)


def dominio_de(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url if "://" in url else f"http://{url}")
    hostname = parsed.hostname or ""
    return hostname.lower() or None


def extrair_tag(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        return None
    if parsed.port:
        return f"{host}:{parsed.port}"
    if parsed.scheme == "https":
        return f"{host}:443"
    if parsed.scheme == "http":
        return f"{host}:80"
    if parsed.scheme:
        return host
    # Sem esquema informado
    fallback = dominio_de(url)
    if fallback:
        return f"{fallback}:80"
    return None


def json_list_normalizada(valor: str | Sequence[str] | None) -> tuple[list[str], bool, str | None]:
    mudou = False
    urls: list[str] = []

    if not valor:
        return [], False, None

    candidatos: Sequence[str] | list[str]
    if isinstance(valor, (list, tuple)):
        candidatos = list(valor)
    else:
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
        except (TypeError, ValueError):
            candidatos = [valor]
            mudou = True

    vistos: set[str] = set()
    for item in candidatos:
        if not isinstance(item, str):
            mudou = True
            continue
        normalizado = item.strip()
        if not normalizado:
            mudou = True
            continue
        if normalizado in vistos:
            mudou = True
            continue
        vistos.add(normalizado)
        urls.append(normalizado)

    primeira = urls[0] if urls else None
    return urls, mudou, primeira


def solicitar_conexao() -> MySQLConnection:
    while True:
        try:
            log(f"{AZUL}\nInforme os dados do seu banco de dados MySQL:{RESET}")
            host = input("Host: ").strip()
            port_input = input("Porta (padrão 3306): ").strip()
            usuario = input("Usuário: ").strip()
            senha = getpass("Senha: ")
            banco = input("Nome do Banco de Dados: ").strip()
            porta = int(port_input) if port_input else 3306

            conexao = mysql.connector.connect(
                host=host,
                port=porta,
                user=usuario,
                password=senha,
                database=banco,
            )
            log(f"{VERDE}Conexão bem-sucedida!{RESET}")
            return conexao
        except Error as exc:
            log(f"{VERMELHO}Erro ao conectar: {exc}{RESET}")
            tentar = input("Tentar novamente? (S/N): ").strip().lower()
            if tentar != "s":
                raise


def obter_schema(cursor: MySQLCursor) -> str:
    cursor.execute("SELECT DATABASE()")
    resultado = cursor.fetchone()
    schema = resultado[0] if isinstance(resultado, (list, tuple)) else next(iter(resultado.values()))
    if not schema:
        raise RuntimeError("Não foi possível identificar o schema atual")
    return schema


def coluna_existe(cursor: MySQLCursor, schema: str, tabela: str, coluna: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s
        """,
        (schema, tabela, coluna),
    )
    return _scalar(cursor.fetchone()) > 0


def indice_existe(cursor: MySQLCursor, schema: str, tabela: str, indice: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND INDEX_NAME=%s
        """,
        (schema, tabela, indice),
    )
    return _scalar(cursor.fetchone()) > 0


def garantir_coluna(cursor: MySQLCursor, conexao: MySQLConnection, schema: str, tabela: str, coluna: str, ddl_tipo: str) -> bool:
    if coluna_existe(cursor, schema, tabela, coluna):
        log(f"{AZUL}Coluna '{coluna}' já existe em {tabela}.{RESET}")
        return False

    log(f"{AMARELO}Coluna '{coluna}' não encontrada em {tabela}. Criando...{RESET}")
    cursor.execute(f"ALTER TABLE `{schema}`.`{tabela}` ADD COLUMN `{coluna}` {ddl_tipo}")
    conexao.commit()
    log(f"{VERDE}Coluna '{coluna}' criada com sucesso.{RESET}")
    return True


def garantir_indice(cursor: MySQLCursor, conexao: MySQLConnection, schema: str, tabela: str, indice: str, definicao: str) -> None:
    if indice_existe(cursor, schema, tabela, indice):
        log(f"{AZUL}Índice '{indice}' já existe em {tabela}.{RESET}")
        return
    log(f"{AMARELO}Criando índice '{indice}' em {tabela}...{RESET}")
    cursor.execute(definicao)
    conexao.commit()
    log(f"{VERDE}Índice '{indice}' criado com sucesso.{RESET}")


def padronizar_streams(conexao: MySQLConnection, schema: str) -> StreamSummary:
    resumo = StreamSummary()
    cursor = conexao.cursor(dictionary=True)
    try:
        log(f"{AZUL}\n1) Normalizando STREAMS (todas as linhas) e preenchendo source_tag_filmes...{RESET}")
        cursor.execute(
            f"SELECT id, type, stream_source, source_tag_filmes FROM `{schema}`.`streams`"
        )
        registros = cursor.fetchall()
        for registro in registros:
            resumo.total += 1
            stream_id = registro["id"]
            stream_type = registro.get("type")
            try:
                stream_type_int = int(stream_type)
            except (TypeError, ValueError):
                stream_type_int = None
            stream_source = registro.get("stream_source")
            tag_atual = registro.get("source_tag_filmes") or ""

            lista, mudou, primeira = json_list_normalizada(stream_source)
            novo_json = json.dumps(lista, ensure_ascii=False, separators=(",", ":"))
            if mudou or (stream_source or "") != novo_json:
                cursor.execute(
                    f"UPDATE `{schema}`.`streams` SET stream_source=%s WHERE id=%s",
                    (novo_json, stream_id),
                )
                resumo.normalizados += 1

            if stream_type_int == 2 and not tag_atual.strip() and primeira:
                tag = extrair_tag(primeira)
                if tag:
                    cursor.execute(
                        f"UPDATE `{schema}`.`streams` SET source_tag_filmes=%s WHERE id=%s",
                        (tag, stream_id),
                    )
                    resumo.filmes_tag += 1
        conexao.commit()
        log(
            f"{VERDE}Streams normalizados: {resumo.normalizados}/{resumo.total} registros atualizados.{RESET}"
        )
        log(f"{VERDE}Filmes com source_tag_filmes preenchido: {resumo.filmes_tag}.{RESET}")
        return resumo
    finally:
        cursor.close()


def padronizar_series(conexao: MySQLConnection, schema: str) -> SeriesSummary:
    resumo = SeriesSummary()
    cursor = conexao.cursor(dictionary=True)
    episodios_cursor = conexao.cursor(dictionary=True)
    try:
        log(f"{AZUL}\n2) Preenchendo source_tag em STREAMS_SERIES (com base nos episódios)...{RESET}")
        cursor.execute(f"SELECT id, source_tag FROM `{schema}`.`streams_series`")
        series = cursor.fetchall()
        for registro in series:
            resumo.total += 1
            tag_atual = (registro.get("source_tag") or "").strip()
            if tag_atual:
                continue
            series_id = registro["id"]
            episodios_cursor.execute(
                f"""
                SELECT s.stream_source
                FROM `{schema}`.`streams_episodes` se
                JOIN `{schema}`.`streams` s ON s.id = se.stream_id
                WHERE se.series_id = %s AND s.type = 5
                """,
                (series_id,),
            )
            episodios = episodios_cursor.fetchall()
            if not episodios:
                continue
            contagem: Counter[str] = Counter()
            for episodio in episodios:
                stream_source = episodio.get("stream_source")
                lista, _, primeira = json_list_normalizada(stream_source)
                if not primeira:
                    continue
                tag = extrair_tag(primeira)
                if not tag:
                    continue
                contagem[tag] += 1
            if not contagem:
                continue
            majoritario, _ = contagem.most_common(1)[0]
            cursor.execute(
                f"UPDATE `{schema}`.`streams_series` SET source_tag=%s WHERE id=%s",
                (majoritario, series_id),
            )
            resumo.atualizadas += 1
        conexao.commit()
        log(
            f"{VERDE}Séries atualizadas com source_tag: {resumo.atualizadas}/{resumo.total}.{RESET}"
        )
        return resumo
    finally:
        episodios_cursor.close()
        cursor.close()


def executar() -> None:
    conexao = None
    try:
        conexao = solicitar_conexao()
        cursor = conexao.cursor()
        try:
            schema = obter_schema(cursor)
        finally:
            cursor.close()

        cursor = conexao.cursor()
        colunas_criadas = 0
        try:
            if garantir_coluna(cursor, conexao, schema, "streams", "source_tag_filmes", "VARCHAR(255) NULL"):
                colunas_criadas += 1
            if garantir_coluna(cursor, conexao, schema, "streams_series", "source_tag", "VARCHAR(255) NULL"):
                colunas_criadas += 1
            if garantir_coluna(cursor, conexao, schema, "streams_series", "tmdb_data", "JSON NULL"):
                colunas_criadas += 1
            garantir_indice(
                cursor,
                conexao,
                schema,
                "streams",
                "idx_streams_tag_filmes",
                f"CREATE INDEX idx_streams_tag_filmes ON `{schema}`.`streams` (source_tag_filmes)",
            )
            garantir_indice(
                cursor,
                conexao,
                schema,
                "streams_series",
                "idx_streams_series_title_tag",
                f"CREATE INDEX idx_streams_series_title_tag ON `{schema}`.`streams_series` (title, source_tag)",
            )
        finally:
            cursor.close()

        streams_resumo = padronizar_streams(conexao, schema)
        series_resumo = padronizar_series(conexao, schema)
        conexao.commit()

        log(f"{AZUL}\nResumo final:{RESET}")
        log(f"{VERDE}Colunas criadas: {colunas_criadas}.{RESET}")
        log(
            f"{VERDE}Streams normalizados: {streams_resumo.normalizados}/{streams_resumo.total}.{RESET}"
        )
        log(f"{VERDE}Filmes com source_tag_filmes: {streams_resumo.filmes_tag}.{RESET}")
        log(f"{VERDE}Séries com source_tag: {series_resumo.atualizadas}.{RESET}")
        log(f"{VERDE}✅ Banco XUI padronizado com sucesso.{RESET}")
    except KeyboardInterrupt:
        if conexao:
            conexao.rollback()
        log(f"{AMARELO}Operação cancelada pelo usuário.{RESET}")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        if conexao:
            conexao.rollback()
        log(f"{VERMELHO}Falha ao padronizar o banco: {exc}{RESET}")
        sys.exit(1)
    finally:
        if conexao:
            conexao.close()


if __name__ == "__main__":
    executar()
