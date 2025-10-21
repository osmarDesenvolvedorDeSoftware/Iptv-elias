# -*- coding: utf-8 -*-
import re
import json
import os
import sys
import time
from pathlib import Path

import mysql.connector
import requests
from collections import defaultdict
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from getpass import getpass

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

# ========= Estilo de logs =========
VERDE = "\033[92m"
AZUL = "\033[94m"
AMARELO = "\033[93m"
VERMELHO = "\033[91m"
RESET = "\033[0m"

# ========= Configurações =========
DELAY_INSERCAO = 0               # pausa (seg) entre inserts
REQUEST_TIMEOUT = 25             # timeout de rede (s)
THROTTLE_EVERY = 25              # pausa a cada X séries (modo API)
THROTTLE_SECS = 1                # duração da pausa (s)

# ignorar grupos/categorias com estes prefixos (quando ler do arquivo)
IGNORAR_GRUPOS_PREFIXO = ["Filmes", "Canais"]
IGNORAR_CATEGORIAS_PREFIXO = ["Filmes", "Canais"]

# detectar conteúdo adulto
PALAVRAS_ADULTO = ["adulto", "xxx", "sexo", "porn", "18+", "hot", "erotic", "x x x", "xxx "]

# TMDb TV
TMDB_API_KEY = "ddb663210423a0bf35985e478396aa0e"  # <<< sua chave
usar_tmdb = False
GENRE_MAP = {}

# ========= Estado (relatório / cache duplicatas) =========
relatorio = []
series_novas = {}
series_atualizadas = {}
urls_existentes = set()  # guarda URL COMPLETA existente

conn = None
cursor = None


_SETTINGS_BOOTSTRAPPED = False


# ===================== Utils de log =====================
def log(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', 'ignore').decode())
    relatorio.append(re.sub(r'\033\[\d+m', '', msg))


# ===================== MySQL =====================


def ensure_backend_settings() -> None:
    global _SETTINGS_BOOTSTRAPPED
    if _SETTINGS_BOOTSTRAPPED:
        return

    _SETTINGS_BOOTSTRAPPED = True

    raw_user_id = os.getenv("IPTV_USER_ID")
    if not raw_user_id:
        log(f"{AMARELO}IPTV_USER_ID não definido; prosseguindo sem criar settings automaticamente.{RESET}")
        return

    try:
        user_id = int(raw_user_id)
    except ValueError:
        log(f"{AMARELO}Valor inválido para IPTV_USER_ID: {raw_user_id}.{RESET}")
        return

    try:
        from backend.app import create_app
        from backend.app.services.settings import get_or_create_settings
    except Exception as exc:  # pragma: no cover - script auxiliar
        log(f"{AMARELO}Não foi possível inicializar o backend para criar settings: {exc}{RESET}")
        return

    app = create_app()
    with app.app_context():
        get_or_create_settings(user_id)

    log(f"{AZUL}Settings básicos garantidos para o usuário {user_id}.{RESET}")


def conectar():
    ensure_backend_settings()
    while True:
        try:
            log(f"{AZUL}\nInforme os dados do seu banco de dados MySQL:{RESET}")
            host = input("Host: ").strip()
            port_input = input("Porta (padrão 3306): ").strip()
            user = input("Usuário: ").strip()
            password = getpass("Senha: ")
            database = input("Nome do Banco de Dados: ").strip()

            port = int(port_input) if port_input else 3306

            c = mysql.connector.connect(
                host=host,
                user=user,
                password=password,
                database=database,
                port=port
            )
            log(f"{VERDE}Conexão bem-sucedida!{RESET}")
            return c
        except Exception as e:
            log(f"{VERMELHO}Erro ao conectar no banco: {e}{RESET}")
            retry = input("Deseja tentar novamente? (S/N): ").strip().lower()
            if retry != 's':
                exit()


def ensure_source_tag_column(cur, conn):
    """
    Garante que streams_series tenha a coluna source_tag (VARCHAR(255) NULL).
    """
    try:
        dbname = conn.database
        cur.execute("""
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'streams_series' AND COLUMN_NAME = 'source_tag'
        """, (dbname,))
        exists = cur.fetchone()[0] > 0
        if not exists:
            log(f"{AMARELO}Coluna 'source_tag' não encontrada em streams_series. Criando...{RESET}")
            cur.execute("ALTER TABLE streams_series ADD COLUMN source_tag VARCHAR(255) NULL DEFAULT NULL")
            conn.commit()
            try:
                cur.execute("CREATE INDEX idx_streams_series_title_tag ON streams_series (title, source_tag)")
                conn.commit()
            except Exception:
                pass
            log(f"{VERDE}Coluna 'source_tag' criada com sucesso.{RESET}")
        else:
            log(f"{AZUL}Coluna 'source_tag' já existe.{RESET}")
    except Exception as e:
        log(f"{VERMELHO}Falha ao garantir coluna source_tag: {e}{RESET}")


def carregar_urls_existentes(cur):
    """
    Carrega cache de URLs COMPLETAS já presentes (para deduplicação por igualdade exata).
    """
    global urls_existentes
    cur.execute("SELECT stream_source FROM streams")
    registros = cur.fetchall()

    urls = set()
    for reg in registros:
        try:
            fontes = json.loads(reg[0]) or []
            for fonte in fontes:
                if isinstance(fonte, str):
                    urls.add(fonte.strip())
        except Exception:
            continue
    urls_existentes = urls
    log(f"{AZUL}Cache de URLs carregado ({len(urls_existentes)} URLs existentes).{RESET}")


# ===================== Helpers de URL / duplicatas =====================
def extrair_extensao(url):
    m = re.search(r'\.([a-z0-9]+)(?:[\?&]|$)', url, re.IGNORECASE)
    return m.group(1).lower() if m else ""


def url_ja_existe(url):
    """True se a URL COMPLETA já existe no banco."""
    return (url or "").strip() in urls_existentes


def dominio_de(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().strip()
    except Exception:
        return ""


def categoria_adulta(nome):
    n = (nome or "").lower()
    return any(p in n for p in PALAVRAS_ADULTO)


# ===================== TMDb (TV) =====================
def limpar_nome_tmdb(nome):
    nome = re.sub(r'\s*-\s*\d{4}$', '', nome)
    nome = re.sub(r'\(\d{4}\)', '', nome)
    return nome.strip()


def obter_generos_tmdb():
    global GENRE_MAP
    try:
        url = "https://api.themoviedb.org/3/genre/tv/list"
        params = {"api_key": TMDB_API_KEY, "language": "pt-BR"}
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        GENRE_MAP = {g["id"]: g["name"] for g in data.get("genres", [])}
        log(f"{AZUL}Lista de gêneros carregada do TMDb.{RESET}")
    except Exception as e:
        log(f"{VERMELHO}Erro ao buscar gêneros do TMDb: {e}{RESET}")
        GENRE_MAP = {}


def buscar_serie_tmdb(nome):
    nome_limpo = limpar_nome_tmdb(nome)
    try:
        url = "https://api.themoviedb.org/3/search/tv"
        params = {"api_key": TMDB_API_KEY, "query": nome_limpo, "language": "pt-BR"}
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        if data.get("results"):
            serie = data["results"][0]
            plot = (serie.get("overview") or "").strip()
            genres = [GENRE_MAP.get(gid, "") for gid in (serie.get("genre_ids") or [])]
            rating = serie.get("vote_average", "")
            poster_url = f"https://image.tmdb.org/t/p/w500{serie.get('poster_path')}" if serie.get('poster_path') else ""
            backdrop_url = f"https://image.tmdb.org/t/p/w780{serie.get('backdrop_path')}" if serie.get('backdrop_path') else ""
            return {
                "plot": plot,
                "genre": ", ".join([g for g in genres if g]),
                "rating": rating,
                "poster_url": poster_url,
                "backdrop_url": backdrop_url
            }
    except Exception:
        pass
    return {"plot": "", "genre": "", "rating": "", "poster_url": "", "backdrop_url": ""}


# ===================== DB helpers: séries com source_tag =====================
def obter_categorias(cur):
    cur.execute("SELECT id, category_name FROM streams_categories")
    categorias = cur.fetchall()
    categorias = [c for c in categorias if not any(c[1].lower().startswith(pref.lower()) for pref in IGNORAR_CATEGORIAS_PREFIXO)]
    return categorias


def escolher_bouquet(cur, rotulo):
    cur.execute("SELECT id, bouquet_name FROM bouquets")
    lista = cur.fetchall()
    log(f"\n{AZUL}Bouquets disponíveis:{RESET}")
    for b in lista:
        log(f"{b[0]}. {b[1]}")
    while True:
        try:
            esc = int(input(f"\nDigite o ID do bouquet para {rotulo}: "))
            if any(b[0] == esc for b in lista):
                return esc
        except Exception:
            pass
        log(f"{VERMELHO}ID inválido.{RESET}")


def get_ou_criar_serie_por_tag(cur, conn, titulo_base: str, cat_id_db: int, poster: str, tmdb_info: dict, tag: str, bouquet_id: int) -> int:
    """
    Retorna o ID da série com (title=titulo_base, source_tag=tag).
    - Se não existir, cria com source_tag=tag.
    - Se existir uma série com title=titulo_base e source_tag NULL/vazio, adota/atualiza para tag.
    Já vincula ao bouquet.
    """
    # 1) tenta (title, tag)
    cur.execute("SELECT id FROM streams_series WHERE title = %s AND source_tag = %s", (titulo_base, tag))
    r = cur.fetchone()
    if r:
        return r[0]

    # 2) tenta herdar de (title, NULL/empty)
    cur.execute("SELECT id FROM streams_series WHERE title = %s AND (source_tag IS NULL OR source_tag = '')", (titulo_base,))
    r = cur.fetchone()
    if r:
        serie_id = r[0]
        try:
            cur.execute("UPDATE streams_series SET source_tag = %s WHERE id = %s", (tag, serie_id))
            conn.commit()
            log(f"{AMARELO}Série '{titulo_base}' sem tag atualizada para source_tag='{tag}'.{RESET}")
        except Exception as e:
            log(f"{VERMELHO}Falha ao atualizar source_tag: {e}{RESET}")
        _garantir_bouquet_serie(cur, conn, bouquet_id, serie_id)
        return serie_id

    # 3) criar nova
    capa = (tmdb_info.get("poster_url") or poster or "").strip()
    backdrop_img = (tmdb_info.get("backdrop_url") or poster or "").strip()
    backdrop = json.dumps([backdrop_img] if backdrop_img else [])
    plot = tmdb_info.get("plot", "")
    rating = tmdb_info.get("rating", "")

    cur.execute("""
        INSERT INTO streams_series (title, category_id, cover, cover_big, backdrop_path, plot, cast, rating, youtube_trailer, tmdb_language, source_tag)
        VALUES (%s, %s, %s, %s, %s, %s, '', %s, '', 'pt-BR', %s)
    """, (titulo_base, f"[{cat_id_db}]", capa, capa, backdrop, plot, rating, tag))
    serie_id = cur.lastrowid
    conn.commit()
    log(f"{VERDE}  Série criada: '{titulo_base}' (ID {serie_id}) com source_tag='{tag}'{RESET}")

    _garantir_bouquet_serie(cur, conn, bouquet_id, serie_id)
    series_novas.setdefault(f"{titulo_base} [{tag}]", [])
    return serie_id


def _garantir_bouquet_serie(cur, conn, bouquet_id, serie_id):
    cur.execute("SELECT bouquet_series FROM bouquets WHERE id = %s", (bouquet_id,))
    res = cur.fetchone()
    existentes = json.loads(res[0]) if res and res[0] else []
    if serie_id not in existentes:
        existentes.append(serie_id)
        cur.execute("UPDATE bouquets SET bouquet_series = %s WHERE id = %s", (json.dumps(existentes), bouquet_id))
        conn.commit()


# ===================== IPTV / M3U / API Xtream =====================
def parse_m3u_link(link_m3u):
    link_m3u = link_m3u.strip()
    p = urlparse(link_m3u)
    scheme = p.scheme or "http"
    netloc = p.netloc
    path = p.path or ""
    qs = parse_qs(p.query or "")

    if ":" in netloc:
        dominio, porta = netloc.split(":", 1)
    else:
        dominio = netloc
        porta = "443" if scheme == "https" else "80"

    usuario = qs.get("username", [None])[0]
    senha = qs.get("password", [None])[0]
    if not usuario or not senha:
        m = re.search(r"/playlist/([^/]+)/([^/]+)/", path)
        if m:
            usuario, senha = m.group(1), m.group(2)

    if not (dominio and usuario and senha):
        raise ValueError("Não foi possível extrair domínio/usuário/senha do link M3U.")

    return scheme, dominio, porta, usuario, senha


def montar_base_url(scheme, dominio, porta):
    return f"{scheme}://{dominio}:{porta}"


def fetch_series_categories(base_url, user, pwd):
    try:
        url = f"{base_url}/player_api.php?username={user}&password={pwd}&action=get_series_categories"
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            fonte = data
        elif isinstance(data, dict):
            fonte = data.get("categories", [])
        else:
            fonte = []

        out = {}
        for c in fonte:
            cid = str(c.get("category_id", "")).strip()
            cname = (c.get("category_name") or "").strip()
            if cid:
                out[cid] = cname or f"Categoria_{cid}"
        if out:
            log(f"{AZUL}Categorias de SÉRIES carregadas da API ({len(out)}).{RESET}")
        return out
    except Exception as e:
        log(f"{AMARELO}Não foi possível carregar categorias de séries: {e}{RESET}")
        return {}


def api_get_series(base_url, user, pwd):
    url = f"{base_url}/player_api.php?username={user}&password={pwd}&action=get_series"
    resp = requests.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list) and isinstance(data, dict):
        data = data.get("series", [])
    return data if isinstance(data, list) else []


def api_get_series_info(base_url, user, pwd, series_id):
    url = f"{base_url}/player_api.php?username={user}&password={pwd}&action=get_series_info&series_id={series_id}"
    resp = requests.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def montar_url_episodio(base_url, user, pwd, episode_id, ext):
    return f"{base_url}/series/{user}/{pwd}/{episode_id}.{ext}"


# ===================== Leitura de ARQUIVO M3U/TXT (playlist) =====================
def ler_playlist_m3u(path_default="lista.txt"):
    caminho = input(f"Caminho do arquivo M3U/TXT (ENTER = {path_default}): ").strip() or path_default
    if not os.path.exists(caminho):
        log(f"{VERMELHO}Arquivo {caminho} não encontrado!{RESET}")
        return []

    with open(caminho, 'r', encoding='utf-8', errors='ignore') as f:
        linhas = f.readlines()

    episodios = []
    i = 0
    while i < len(linhas):
        linha = linhas[i].strip()
        if linha.startswith('#EXTINF'):
            info = linha
            url = linhas[i + 1].strip() if (i + 1) < len(linhas) else ''
            nome = re.search(r'tvg-name="([^"]+)"', info)
            categoria = re.search(r'group-title="([^"]+)"', info)
            logo = re.search(r'tvg-logo="([^"]+)"', info)

            if nome and categoria and logo and url:
                nome_tvg = nome.group(1).strip()
                m = re.search(r'^(.*?)[\s._-]*[Ss](\d+)[\s._-]*[Ee](\d+)\s*$', nome_tvg)
                if m:
                    serie = m.group(1).strip()
                    temporada = int(m.group(2))
                    episodio = int(m.group(3))
                    episodios.append({
                        'serie': serie,
                        'temp': temporada,
                        'ep': episodio,
                        'nome_completo': nome_tvg,
                        'logo': logo.group(1).strip(),
                        'categoria_txt': categoria.group(1).strip(),
                        'url': url
                    })
        i += 1

    log(f"{AZUL}Total de episódios lidos do arquivo: {len(episodios)}{RESET}")
    return episodios


# ===================== Inserção incremental (API) =====================
def inserir_serie_e_episodios_api(series_item, base_url, usuario, senha, cat_id_db, bouquet_id):
    """
    Regras:
      - Dedup por URL completa
      - Sempre usar série identificada por title + source_tag (domínio)
      - Mesmo S/E + mesmo domínio + URL diferente => cria NOVO episódio
      - Ao final, log por domínio
    """
    global usar_tmdb

    title_base = (series_item.get("name") or series_item.get("title") or "").strip()
    poster = (series_item.get("cover") or series_item.get("series_cover") or series_item.get("cover_big") or series_item.get("stream_icon") or "").strip()
    series_id_api = series_item.get("series_id") or series_item.get("id") or series_item.get("stream_id")
    if series_id_api is None or not title_base:
        return

    tmdb_info = buscar_serie_tmdb(title_base) if usar_tmdb else {"plot": "", "genre": "", "rating": "", "poster_url": "", "backdrop_url": ""}

    info = api_get_series_info(base_url, usuario, senha, series_id_api)
    eps_by_season = (info.get("episodes") or {}) if isinstance(info, dict) else {}
    temporadas_ordenadas = sorted(list(eps_by_season.keys()), key=lambda x: int(x) if str(x).isdigit() else 999999)

    inseridos_por_dom = defaultdict(int)

    for season_key in temporadas_ordenadas:
        for ep in (eps_by_season.get(season_key) or []):
            try:
                ep_id = ep.get("id")
                if not ep_id:
                    continue
                ext = (ep.get("container_extension") or "mp4").strip()
                ep_info = ep.get("info") or {}
                temporada = int(ep_info.get("season") or season_key or 0)
                episodio = int(ep_info.get("episode_num") or ep.get("episode_num") or 0)
                ep_title = (ep.get("title") or f"{title_base} S{temporada:02}E{episodio:02}").strip()
                url_real = montar_url_episodio(base_url, usuario, senha, ep_id, ext)

                # 1) dedup por URL COMPLETA
                if url_ja_existe(url_real):
                    continue

                # 2) determina domínio e pega/cria série com source_tag = domínio
                dom = dominio_de(url_real) or "desconhecido"
                serie_id = get_ou_criar_serie_por_tag(cursor, conn, title_base, cat_id_db, poster, tmdb_info, dom, bouquet_id)

                # 3) inserir episódio (sempre cria novo)
                props = {
                    "release_date": "",
                    "plot": tmdb_info.get("plot", ""),
                    "duration_secs": 0,
                    "duration": "00:00:00",
                    "movie_image": poster,
                    "video": [],
                    "audio": [],
                    "bitrate": 0,
                    "rating": tmdb_info.get("rating", ""),
                    "season": str(temporada),
                    "tmdb_id": "",
                    "genre": tmdb_info.get("genre", ""),
                    "actors": "",
                    "youtube_trailer": ""
                }
                stream_source = json.dumps([url_real])
                container = extrair_extensao(url_real) or "mp4"

                cursor.execute("""
                    INSERT INTO streams (stream_display_name, stream_source, stream_icon, type, movie_properties, direct_source, target_container)
                    VALUES (%s, %s, %s, 5, %s, 1, %s)
                """, (ep_title, stream_source, poster, json.dumps(props), container))
                stream_id = cursor.lastrowid

                cursor.execute("""
                    INSERT INTO streams_episodes (season_num, episode_num, series_id, stream_id)
                    VALUES (%s, %s, %s, %s)
                """, (temporada, episodio, serie_id, stream_id))
                conn.commit()

                urls_existentes.add(url_real)
                inseridos_por_dom[dom] += 1

                series_atualizadas.setdefault(f"{title_base} [{dom}]", []).append(
                    {'temp': temporada, 'ep': episodio, 'nome_completo': ep_title}
                )

                if DELAY_INSERCAO:
                    time.sleep(DELAY_INSERCAO)
            except Exception as e:
                log(f"{AMARELO}    Falha ao inserir episódio: {e}{RESET}")
                continue

    # logs por domínio
    for dom, qtd in inseridos_por_dom.items():
        log(f"{AZUL}Concluído: '{title_base}' -> {qtd} eps inseridos (domínio via source_tag > {dom}).{RESET}")


# ===================== Inserção incremental (ARQUIVO) =====================
def inserir_serie_e_episodios_txt(serie, eps_serie, cat_id_db, bouquet_id):
    """
    - Dedup por URL completa
    - Sempre usa série (title, source_tag=domínio)
    - Mesmo S/E + mesmo domínio + URL diferente => cria NOVO episódio
    - Ao final, log por domínio
    """
    global usar_tmdb

    poster = eps_serie[0].get('logo', '').strip() if eps_serie else ""
    title_base = (serie or "").strip()
    if not title_base:
        return

    tmdb_info = buscar_serie_tmdb(title_base) if usar_tmdb else {"plot": "", "genre": "", "rating": "", "poster_url": "", "backdrop_url": ""}

    eps_serie.sort(key=lambda x: (x.get('temp', 0), x.get('ep', 0)))
    inseridos_por_dom = defaultdict(int)

    for ep in eps_serie:
        try:
            temporada = int(ep.get("temp") or 0)
            episodio = int(ep.get("ep") or 0)
            ep_title = ep.get("nome_completo") or f"{title_base} S{temporada:02}E{episodio:02}"
            poster_ep = ep.get("logo") or poster
            url_real = (ep.get("url") or "").strip()
            if not url_real:
                continue

            # 1) dedup por URL COMPLETA
            if url_ja_existe(url_real):
                continue

            # 2) série por domínio
            dom = dominio_de(url_real) or "desconhecido"
            serie_id = get_ou_criar_serie_por_tag(cursor, conn, title_base, cat_id_db, poster_ep, tmdb_info, dom, bouquet_id)

            # 3) inserir episódio (sempre cria novo)
            props = {
                "release_date": "",
                "plot": tmdb_info.get("plot", ""),
                "duration_secs": 0,
                "duration": "00:00:00",
                "movie_image": poster_ep,
                "video": [],
                "audio": [],
                "bitrate": 0,
                "rating": tmdb_info.get("rating", ""),
                "season": str(temporada),
                "tmdb_id": "",
                "genre": tmdb_info.get("genre", ""),
                "actors": "",
                "youtube_trailer": ""
            }
            stream_source = json.dumps([url_real])
            container = extrair_extensao(url_real) or "mp4"

            cursor.execute("""
                INSERT INTO streams (stream_display_name, stream_source, stream_icon, type, movie_properties, direct_source, target_container)
                VALUES (%s, %s, %s, 5, %s, 1, %s)
            """, (ep_title, stream_source, poster_ep, json.dumps(props), container))
            stream_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO streams_episodes (season_num, episode_num, series_id, stream_id)
                VALUES (%s, %s, %s, %s)
            """, (temporada, episodio, serie_id, stream_id))
            conn.commit()

            urls_existentes.add(url_real)
            inseridos_por_dom[dom] += 1

            series_atualizadas.setdefault(f"{title_base} [{dom}]", []).append(
                {'temp': temporada, 'ep': episodio, 'nome_completo': ep_title}
            )

            if DELAY_INSERCAO:
                time.sleep(DELAY_INSERCAO)
        except Exception as e:
            log(f"{AMARELO}    Falha ao inserir episódio: {e}{RESET}")
            continue

    # logs por domínio
    for dom, qtd in inseridos_por_dom.items():
        log(f"{AZUL}Concluído: '{title_base}' -> {qtd} eps inseridos (domínio via source_tag > {dom}).{RESET}")


# ===================== Relatório =====================
def salvar_relatorio():
    with open("importacaodeseries.txt", 'w', encoding='utf-8') as f:
        f.write("Relatório de Importação de Séries\n")
        f.write(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n")

        if series_novas:
            f.write("📌 Séries Novas:\n\n")
            for serie, episodios in series_novas.items():
                f.write(f"✅ {serie}\n")
                for ep in episodios:
                    f.write(f"  - S{ep['temp']:02}E{ep['ep']:02} - {ep['nome_completo']}\n")
                f.write("\n")

        if series_atualizadas:
            f.write("📌 Séries Atualizadas:\n\n")
            for serie, episodios in series_atualizadas.items():
                if episodios:
                    f.write(f"🔄 {serie}\n")
                    for ep in episodios:
                        f.write(f"  - S{ep['temp']:02}E{ep['ep']:02} - {ep['nome_completo']}\n")
                    f.write("\n")

    log(f"\n{AZUL}Relatório salvo em 'importacaodeseries.txt'{RESET}")


# ===================== Main =====================
def main():
    global usar_tmdb, conn, cursor

    # Conexão
    conn = conectar()
    cursor = conn.cursor(buffered=True)

    # Garante a coluna source_tag
    ensure_source_tag_column(cursor, conn)

    # Carrega URLs existentes
    carregar_urls_existentes(cursor)

    log(f"{AZUL}Iniciando importação de séries...{RESET}")

    # Escolha da origem
    log(f"{AZUL}\nOrigem dos dados:{RESET}\n1) API IPTV (M3U)\n2) Arquivo M3U/TXT (#EXTINF)")
    modo = input("Escolha (1 ou 2): ").strip()

    # ======== escolher bouquets (normal x adulto) ========
    bouquet_id_normal = escolher_bouquet(cursor, "séries")
    bouquet_id_adulto = escolher_bouquet(cursor, "adultos")

    if modo == "2":
        # ========= MODO ARQUIVO =========
        episodios = ler_playlist_m3u()
        if not episodios:
            log(f"{VERMELHO}Nenhum episódio encontrado no arquivo.{RESET}")
            return

        # TMDb?
        if input(f"\n{AMARELO}Deseja buscar informações do TMDb para cada série? (S/N): {RESET}").strip().lower() == 's':
            usar_tmdb = True
            obter_generos_tmdb()
            log(f"{AZUL}Busca no TMDb ativada.{RESET}")
        else:
            log(f"{AMARELO}Busca no TMDb desativada.{RESET}")

        # agrupar por categoria (group-title)
        grupos = defaultdict(list)
        for ep in episodios:
            grupos[ep['categoria_txt']].append(ep)

        # remove grupos ignorados
        grupos = {k: v for k, v in grupos.items()
                  if not any(k.lower().startswith(pref.lower()) for pref in IGNORAR_GRUPOS_PREFIXO)}

        categorias_db = obter_categorias(cursor)

        while True:
            if not grupos:
                log(f"{AMARELO}Não há categorias para processar.{RESET}")
                break

            log(f"\n{AMARELO}Categorias encontradas no arquivo:{RESET}")
            lista_grupos = list(grupos.keys())
            for idx, grupo in enumerate(lista_grupos, 1):
                log(f"{idx}. {grupo}")

            escolha_cats = input("\nDigite os números das categorias para processar (vírgula) ou 'S' para sair: ").strip().lower()
            if escolha_cats == 's':
                break

            try:
                indices = [int(i.strip()) for i in escolha_cats.split(',') if i.strip()]
                selecionadas = [lista_grupos[i - 1] for i in indices if 1 <= i <= len(lista_grupos)]
                if not selecionadas:
                    raise ValueError
            except Exception:
                log(f"{VERMELHO}Entrada inválida.{RESET}")
                continue

            # mapear categoria txt -> id no DB
            mapeamento = {}
            for grupo in selecionadas:
                sugestao = None
                for c in categorias_db:
                    if c[1].lower().strip() == grupo.lower().strip():
                        sugestao = c
                        break

                if sugestao:
                    log(f"\n{AMARELO}Vincular '{grupo}' à categoria sugerida '{sugestao[1]}' (ID {sugestao[0]})?{RESET}")
                else:
                    log(f"\nVincular '{grupo}' a qual categoria do DB (ID)?")

                log(f"\n{AZUL}Categorias disponíveis no banco:{RESET}")
                for c in categorias_db:
                    log(f"{c[0]}. {c[1]}")

                entrada = input("\nPressione ENTER para confirmar sugestão ou digite outro ID: ").strip()
                if sugestao and entrada == "":
                    mapeamento[grupo] = sugestao[0]
                    continue

                while True:
                    try:
                        cat_id = int(entrada) if entrada else int(input(f"ID para '{grupo}': ").strip())
                        if any(c[0] == cat_id for c in categorias_db):
                            mapeamento[grupo] = cat_id
                            break
                        else:
                            log(f"{VERMELHO}ID inválido.{RESET}")
                    except Exception:
                        log(f"{VERMELHO}Entrada inválida.{RESET}")
                    entrada = input(f"ID para '{grupo}': ").strip()

            # processar cada categoria selecionada
            for grupo in selecionadas:
                eps_cat = grupos[grupo]

                # agrupar por série
                series_map = defaultdict(list)
                for ep in eps_cat:
                    series_map[ep['serie']].append(ep)

                # escolher bouquet por categoria (adulto ou normal)
                is_adulto = categoria_adulta(grupo)
                bouquet_id = bouquet_id_adulto if is_adulto else bouquet_id_normal

                for serie_nome, eps_serie in series_map.items():
                    inserir_serie_e_episodios_txt(serie_nome, eps_serie, mapeamento[grupo], bouquet_id)

                # remover categoria já processada
                grupos.pop(grupo, None)

        cursor.close()
        conn.close()
        salvar_relatorio()
        log(f"\n{AZUL}Processamento finalizado (arquivo).{RESET}")
        return

    # ========= MODO API =========
    log(f"{AZUL}\nCole o link M3U ou pressione ENTER para informar manualmente os dados:{RESET}")
    link_m3u = input("URL M3U (ex: http://dominio:porta/get.php?username=USER&password=PASS&type=m3u_plus&output=ts): ").strip()

    if link_m3u:
        try:
            scheme, dominio, porta, usuario, senha = parse_m3u_link(link_m3u)
        except Exception as e:
            log(f"{VERMELHO}Erro ao interpretar o link M3U: {e}{RESET}")
            exit()
    else:
        log(f"{AZUL}\nInforme os dados da sua API IPTV manualmente:{RESET}")
        raw_dom = input("Domínio (ex: painel.iptvpro.com): ").strip()
        raw_dom = raw_dom.replace("http://", "").replace("https://", "").strip().strip("/")
        dominio = raw_dom.split("/")[0]
        porta = input("Porta (ex: 8080): ").strip() or "80"
        scheme = "http"
        usuario = input("Usuário: ").strip()
        senha = getpass("Senha: ")

    base_url = montar_base_url(scheme, dominio, porta)

    # Lista de séries
    log(f"{AZUL}\nBuscando séries (get_series)...{RESET}")
    try:
        series_list = api_get_series(base_url, usuario, senha)
    except Exception as e:
        log(f"{VERMELHO}Erro em get_series: {e}{RESET}")
        exit()

    if not series_list:
        log(f"{AMARELO}Nenhuma série retornada pela API.{RESET}")
        return

    total_series_all = len(series_list)
    log(f"{AZUL}Total de séries retornadas: {total_series_all}{RESET}")

    # Carrega nomes de categorias
    catmap = fetch_series_categories(base_url, usuario, senha)

    # Mostra resumo categorias
    cont_por_cat = defaultdict(int)
    for s in series_list:
        cid = str(s.get("category_id", "")).strip()
        cont_por_cat[cid] += 1

    if cont_por_cat:
        log(f"\n{AMARELO}Categorias encontradas (séries por categoria):{RESET}")
        pares = []
        for cid, qtd in cont_por_cat.items():
            nome = catmap.get(cid, f"Categoria_{cid or 'SemID'}")
            pares.append((cid, nome, qtd))
        pares.sort(key=lambda x: x[2], reverse=True)
        for cid, nome, qtd in pares[:100]:
            log(f"  - {cid or 'SemID'} | {nome} -> {qtd} séries")
        log("(mostrando até 100 linhas)")

    # Filtros
    filtro_cids = input("\nDigite os category_id da API que deseja (separados por vírgula) ou ENTER para todas: ").strip()
    filtro_cids_set = set([c.strip() for c in filtro_cids.split(",") if c.strip()]) if filtro_cids else None
    if filtro_cids_set:
        series_list = [s for s in series_list if str(s.get('category_id', '')).strip() in filtro_cids_set]
        log(f"{AZUL}Séries após filtro de categorias: {len(series_list)}{RESET}")

    try:
        limite = input("Limite de séries para processar (ENTER = todas): ").strip()
        if limite:
            limite = int(limite)
            if limite > 0:
                series_list = series_list[:limite]
                log(f"{AZUL}Aplicado limite: processando {len(series_list)} séries{RESET}")
    except Exception:
        pass

    # TMDb?
    if input(f"\n{AMARELO}Deseja buscar informações do TMDb para cada série? (S/N): {RESET}").strip().lower() == 's':
        usar_tmdb = True
        obter_generos_tmdb()
        log(f"{AZUL}Busca no TMDb ativada.{RESET}")
    else:
        log(f"{AMARELO}Busca no TMDb desativada.{RESET}")

    # Mapear categorias da API -> categorias do DB
    categorias_db = obter_categorias(cursor)
    api_catids_usadas = sorted({str(s.get("category_id", "")).strip() for s in series_list})
    mapeamento_api_to_db = {}

    for api_cid in api_catids_usadas:
        nome_api = catmap.get(api_cid, f"Categoria_{api_cid or 'SemID'}")
        sugestao = None
        for c in categorias_db:
            if c[1].lower().strip() == nome_api.lower().strip():
                sugestao = c
                break

        if sugestao:
            log(f"\n{AMARELO}Vincular categoria API '{nome_api}' (id {api_cid}) à categoria DB sugerida '{sugestao[1]}' (ID {sugestao[0]})?{RESET}")
        else:
            log(f"\nVincular categoria API '{nome_api}' (id {api_cid}) a qual categoria do DB (ID)?")

        log(f"\n{AZUL}Categorias disponíveis no banco:{RESET}")
        for c in categorias_db:
            log(f"{c[0]}. {c[1]}")

        entrada = input("\nPressione ENTER para confirmar sugestão ou digite outro ID: ").strip()
        if sugestao and entrada == "":
            mapeamento_api_to_db[api_cid] = sugestao[0]
            continue

        while True:
            try:
                cat_id = int(entrada) if entrada else int(input(f"ID para '{nome_api}': ").strip())
                if any(c[0] == cat_id for c in categorias_db):
                    mapeamento_api_to_db[api_cid] = cat_id
                    break
                else:
                    log(f"{VERMELHO}ID inválido.{RESET}")
            except Exception:
                log(f"{VERMELHO}Entrada inválida.{RESET}")
            entrada = input(f"ID para '{nome_api}': ").strip()

    # Processamento incremental
    total = len(series_list)
    log(f"{AZUL}\nBuscando episódios e inserindo no banco ({total} séries selecionadas)...{RESET}")

    for idx, s in enumerate(series_list, start=1):
        try:
            title = (s.get("name") or s.get("title") or "").strip()
            cid = str(s.get("category_id", "")).strip()
            cat_id_db = mapeamento_api_to_db.get(cid)
            if not title or not cat_id_db:
                continue

            # escolher bouquet conforme categoria (adulto/normal)
            cat_name = (catmap.get(cid, "") or "").strip()
            is_adulto = categoria_adulta(cat_name)
            bouquet_escolhido = (bouquet_id_adulto if is_adulto else bouquet_id_normal)

            if idx == 1 or idx % 10 == 0 or idx == total:
                log(f"{AZUL}[{idx}/{total}] {title} | Categoria: {cat_name or 'N/A'} | Bouquet: {'adultos' if is_adulto else 'séries'}{RESET}")

            inserir_serie_e_episodios_api(s, base_url, usuario, senha, cat_id_db, bouquet_escolhido)

            if THROTTLE_EVERY and idx % THROTTLE_EVERY == 0:
                time.sleep(THROTTLE_SECS)

        except KeyboardInterrupt:
            log(f"{VERMELHO}\nInterrompido pelo usuário. Encerrando com o que já foi inserido...{RESET}")
            break
        except Exception as e:
            log(f"{AMARELO}Erro ao processar série: {e}{RESET}")
            continue

    cursor.close()
    conn.close()
    salvar_relatorio()
    log(f"\n{AZUL}Processamento finalizado (API).{RESET}")


if __name__ == "__main__":
    main()
