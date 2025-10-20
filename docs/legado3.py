# -*- coding: utf-8 -*-
import mysql.connector
import re
import os
import json
import requests
from collections import defaultdict
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from getpass import getpass

# ====== Estilos de log ======
VERDE = "\033[92m"
AZUL = "\033[94m"
AMARELO = "\033[93m"
VERMELHO = "\033[91m"
RESET = "\033[0m"

# ====== Configs ======
IGNORAR_GRUPOS_PREFIXO = ["Series", "Canais"]
IGNORAR_CATEGORIAS_PREFIXO = ["Series", "Canais"]
PALAVRAS_ADULTO = ["adulto", "xxx", "sexo", "porn"]
REQUEST_TIMEOUT = 25

TMDB_API_KEY = "ddb663210423a0bf35985e478396aa0e"  # sua chave
usar_tmdb = False
GENRE_MAP = {}

# ====== Estado ======
relatorio = []
filmes_inseridos = {}
filmes_existentes = {}
arquivos_existentes = set()  # guarda URL COMPLETA
conn = None
cursor = None


# ========================= Utilidades de log =========================
def log(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', 'ignore').decode())
    relatorio.append(re.sub(r'\033\[\d+m', '', msg))


# ========================= DB =========================
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


def ensure_source_tag_filmes_column(cur, conn):
    """
    Garante que a tabela `streams` tenha a coluna `source_tag_filmes` (VARCHAR(255) NULL).
    Cria também um índice auxiliar.
    """
    try:
        dbname = conn.database
        cur.execute("""
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'streams' AND COLUMN_NAME = 'source_tag_filmes'
        """, (dbname,))
        exists = cur.fetchone()[0] > 0
        if not exists:
            log(f"{AMARELO}Coluna 'source_tag_filmes' não encontrada em streams. Criando...{RESET}")
            cur.execute("ALTER TABLE streams ADD COLUMN source_tag_filmes VARCHAR(255) NULL DEFAULT NULL")
            conn.commit()
            try:
                cur.execute("CREATE INDEX idx_streams_tag_filmes ON streams (source_tag_filmes)")
                conn.commit()
            except Exception:
                pass
            log(f"{VERDE}Coluna 'source_tag_filmes' criada com sucesso.{RESET}")
        else:
            log(f"{AZUL}Coluna 'source_tag_filmes' já existe.{RESET}")
    except Exception as e:
        log(f"{VERMELHO}Falha ao garantir coluna source_tag_filmes: {e}{RESET}")


def carregar_arquivos_existentes(cur):
    """
    Cache com as URLs COMPLETAS já presentes no banco,
    para evitar duplicatas por igualdade exata da URL.
    """
    global arquivos_existentes
    cur.execute("SELECT stream_source FROM streams")
    registros = cur.fetchall()

    urls = set()
    for reg in registros:
        try:
            fontes = json.loads(reg[0]) or []
            for fonte in fontes:
                if isinstance(fonte, str):
                    urls.add(fonte.strip())  # guarda URL exata (sem normalizar)
        except Exception:
            continue
    arquivos_existentes = urls
    log(f"{AZUL}Cache de URLs carregado ({len(arquivos_existentes)} URLs existentes).{RESET}")


# ========================= Helpers de URL =========================
def extrair_nome_arquivo(url):
    """
    (mantido por compatibilidade, mas NÃO é mais usado no deduplicador)
    Pega o 'nome do arquivo' da URL (último segmento do path),
    ou 'id' se vier como query (?id=xxx).
    """
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "id" in qs and qs["id"]:
        return qs["id"][0].lower()
    return os.path.basename(parsed.path).lower()


def extrair_extensao(url):
    match = re.search(r'\.([a-z0-9]+)(?:[\?&]|$)', url, re.IGNORECASE)
    return match.group(1).lower() if match else ""


def dominio_de(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().strip()
    except Exception:
        return ""


def verificar_duplicado(url):
    """Deduplicação por URL COMPLETA (string exata)."""
    return (url or "").strip() in arquivos_existentes


# ========================= TMDb =========================
def limpar_nome_tmdb(nome):
    nome = re.sub(r'\s*-\s*\d{4}$', '', nome)
    nome = re.sub(r'\(\d{4}\)', '', nome)
    return nome.strip()


def obter_generos_tmdb():
    global GENRE_MAP
    try:
        url = "https://api.themoviedb.org/3/genre/movie/list"
        params = {"api_key": TMDB_API_KEY, "language": "pt-BR"}
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        GENRE_MAP = {g["id"]: g["name"] for g in data.get("genres", [])}
        log(f"{AZUL}Lista de gêneros carregada do TMDb.{RESET}")
    except Exception as e:
        log(f"{VERMELHO}Erro ao buscar gêneros do TMDb: {e}{RESET}")
        GENRE_MAP = {}


def buscar_info_tmdb(nome):
    nome_limpo = limpar_nome_tmdb(nome)
    try:
        url = "https://api.themoviedb.org/3/search/movie"
        params = {
            "api_key": TMDB_API_KEY,
            "query": nome_limpo,
            "language": "pt-BR"
        }
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        if data.get("results"):
            filme = data["results"][0]
            return {
                "plot": filme.get("overview", "").strip(),
                "release_date": filme.get("release_date", ""),
                "rating": filme.get("vote_average", ""),
                "director": "",
                "cast": "",
                "genre": ", ".join([GENRE_MAP.get(gid, "") for gid in filme.get("genre_ids", [])]),
                "youtube_trailer": "",
                "poster_url": f"https://image.tmdb.org/t/p/w500{filme.get('poster_path')}" if filme.get('poster_path') else "",
                "backdrop_url": f"https://image.tmdb.org/t/p/w780{filme.get('backdrop_path')}" if filme.get('backdrop_path') else ""
            }
    except Exception:
        pass
    return {
        "plot": "", "release_date": "", "rating": "", "director": "", "cast": "",
        "genre": "", "youtube_trailer": "", "poster_url": "", "backdrop_url": ""
    }


def gerar_movie_properties(nome, logo_url):
    tmdb_info = buscar_info_tmdb(nome) if usar_tmdb else {
        "plot": "", "release_date": "", "rating": "", "director": "", "cast": "",
        "genre": "", "youtube_trailer": "", "poster_url": "", "backdrop_url": ""
    }
    capa = tmdb_info["poster_url"] if tmdb_info["poster_url"] else logo_url
    backdrop_img = tmdb_info["backdrop_url"] if tmdb_info["backdrop_url"] else logo_url
    return json.dumps({
        "name": nome, "o_name": nome, "cover_big": capa, "movie_image": capa,
        "release_date": tmdb_info["release_date"], "youtube_trailer": tmdb_info["youtube_trailer"],
        "director": tmdb_info["director"], "actors": tmdb_info["cast"], "cast": tmdb_info["cast"],
        "description": "", "plot": tmdb_info["plot"], "genre": tmdb_info["genre"],
        "backdrop_path": [backdrop_img] if backdrop_img else [], "duration_secs": 0, "duration": "00:00:00",
        "video": [], "audio": [], "bitrate": 0, "rating": tmdb_info["rating"],
        "tmdb_id": "", "age": "", "mpaa_rating": "", "rating_count_kinopoisk": 0,
        "country": "", "kinopoisk_url": ""
    })


# ========================= Bouquets / Categorias =========================
def obter_categorias(cur):
    cur.execute("SELECT id, category_name FROM streams_categories")
    return [c for c in cur.fetchall()
            if not any(c[1].lower().startswith(p.lower()) for p in IGNORAR_CATEGORIAS_PREFIXO)]


def escolher_bouquet(cur, tipo):
    cur.execute("SELECT id, bouquet_name FROM bouquets")
    lista = cur.fetchall()
    log(f"\n{AZUL}Bouquets disponíveis:{RESET}")
    for b in lista:
        log(f"{b[0]}. {b[1]}")
    while True:
        try:
            esc = int(input(f"\nDigite o ID do bouquet para {tipo}: "))
            if any(b[0] == esc for b in lista):
                return esc
        except Exception:
            pass
        log(f"{VERMELHO}ID inválido.{RESET}")


def atualizar_bouquet(cur, conn, bouquet_id, novos_ids):
    cur.execute("SELECT bouquet_movies FROM bouquets WHERE id = %s", (bouquet_id,))
    resultado = cur.fetchone()
    existentes = json.loads(resultado[0]) if resultado and resultado[0] else []
    for nid in novos_ids:
        if nid not in existentes:
            existentes.append(nid)
    cur.execute("UPDATE bouquets SET bouquet_movies = %s WHERE id = %s",
                (json.dumps(existentes), bouquet_id))
    conn.commit()
    log(f"{AZUL}Bouquet atualizado com {len(novos_ids)} novos filmes.{RESET}")


def salvar_relatorio():
    with open('importacaofilmes.txt', 'w', encoding='utf-8') as f:
        f.write("Relatório de Importação de Filmes\n")
        f.write(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n")
        if filmes_inseridos:
            f.write("📌 Filmes Inseridos:\n\n")
            for cat, filmes in filmes_inseridos.items():
                f.write(f"✅ Categoria: {cat}\n")
                for nome in filmes:
                    f.write(f"  - {nome}\n")
                f.write("\n")
        if filmes_existentes:
            f.write("📌 Filmes Ignorados (já existiam):\n\n")
            for cat, filmes in filmes_existentes.items():
                f.write(f"🔄 Categoria: {cat}\n")
                for nome in filmes:
                    f.write(f"  - {nome}\n")
                f.write("\n")
    log(f"\n{AZUL}Relatório salvo em 'importacaofilmes.txt'{RESET}")


def processar_categoria(cur, conn, grupo, filmes, cat_id, bouquet_id):
    log(f"\n{AMARELO}========== Iniciando processamento da categoria: {grupo} =========={RESET}")
    novos_ids = []
    for f in filmes:
        url_full = (f['url'] or "").strip()
        dom = dominio_de(url_full)  # domínio:porta para gravar no source_tag_filmes

        if verificar_duplicado(url_full):
            log(f"{VERMELHO}Filme '{f['nome']}' já existe no banco (URL idêntica). Ignorado.{RESET}")
            filmes_existentes.setdefault(grupo, []).append(f['nome'])
            continue

        movie_properties = gerar_movie_properties(f['nome'], f['logo'])

        cur.execute("""
            INSERT INTO streams
                (category_id, stream_display_name, stream_source, stream_icon, type,
                 movie_properties, direct_source, target_container, source_tag_filmes)
            VALUES
                (%s, %s, %s, %s, 2, %s, 1, %s, %s)
        """, (f"[{cat_id}]",
              f['nome'],
              json.dumps([url_full]),
              f['logo'],
              movie_properties,
              extrair_extensao(url_full),
              dom))

        stream_id = cur.lastrowid
        conn.commit()

        log(f"{VERDE}Filme '{f['nome']}' inserido (source_tag_filmes={dom}).{RESET}")
        novos_ids.append(stream_id)
        filmes_inseridos.setdefault(grupo, []).append(f['nome'])

        # adiciona a URL COMPLETA ao cache anti-duplicado
        arquivos_existentes.add(url_full)

    if novos_ids:
        atualizar_bouquet(cur, conn, bouquet_id, novos_ids)
    log(f"{AMARELO}========== Categoria '{grupo}' finalizada =========={RESET}")


def sugerir_categoria(grupo, categorias_db):
    nome_limpo = grupo.lower().strip()
    for c in categorias_db:
        if c[1].lower().strip() == nome_limpo:
            return c
    return None


def categoria_adulta(nome):
    nome = nome.lower()
    return any(p in nome for p in PALAVRAS_ADULTO)


# ========================= IPTV / M3U =========================
def parse_m3u_link(link_m3u):
    """
    Extrai scheme, domínio, porta, usuário e senha do link M3U.
    Suporta:
      - http(s)://dominio[:porta]/get.php?username=USER&password=PASS&type=m3u_plus&output=ts
      - http(s)://dominio[:porta]/playlist/USER/PASS/m3u_plus
    """
    link_m3u = link_m3u.strip()
    p = urlparse(link_m3u)
    scheme = p.scheme or "http"
    netloc = p.netloc
    path = p.path or ""
    qs = parse_qs(p.query or "")

    # Domínio / Porta
    if ":" in netloc:
        dominio, porta = netloc.split(":", 1)
    else:
        dominio = netloc
        porta = "443" if scheme == "https" else "80"

    # Usuário/Senha
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


def fetch_vod_categories(base_url, user, pwd):
    """
    Tenta obter nomes das categorias:
      action=get_vod_categories -> [{category_id, category_name, ...}]
    Retorna {cat_id(str): category_name} ou {} se falhar.
    """
    try:
        url = f"{base_url}/player_api.php?username={user}&password={pwd}&action=get_vod_categories"
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        catmap = {}
        fonte = data if isinstance(data, list) else data.get("categories", []) if isinstance(data, dict) else []
        for c in fonte:
            cid = str(c.get("category_id", "")).strip()
            cname = c.get("category_name", "").strip() or f"Categoria_{cid}"
            if cid:
                catmap[cid] = cname
        if catmap:
            log(f"{AZUL}Categorias carregadas da API ({len(catmap)}).{RESET}")
        return catmap
    except Exception as e:
        log(f"{AMARELO}Não foi possível carregar nomes das categorias da API: {e}{RESET}")
        return {}


def buscar_lista_api():
    """
    Pede um link M3U (ou permite modo manual) e coleta os VODs via get_vod_streams.
    Retorna lista de dicts no formato:
      { 'nome', 'categoria_txt', 'logo', 'url' }
    """
    log(f"{AZUL}\nCole o link M3U ou pressione ENTER para informar manualmente os dados:{RESET}")
    link_m3u = input("URL M3U (ex: http://dominio:porta/get.php?username=USER&password=PASS&type=m3u_plus&output=ts): ").strip()

    if link_m3u:
        try:
            scheme, dominio, porta, usuario, senha = parse_m3u_link(link_m3u)
        except Exception as e:
            log(f"{VERMELHO}Erro ao interpretar o link M3U: {e}{RESET}")
            exit()
    else:
        # Método manual (antigo)
        log(f"{AZUL}\nInforme os dados da sua API IPTV manualmente:{RESET}")
        raw_dom = input("Domínio (ex: painel.iptvpro.com): ").strip()
        raw_dom = raw_dom.replace("http://", "").replace("https://", "").strip().strip("/")
        dominio = raw_dom.split("/")[0]
        porta = input("Porta (ex: 8080): ").strip() or "80"
        scheme = "http"
        usuario = input("Usuário: ").strip()
        senha = getpass("Senha: ")

    base_url = montar_base_url(scheme, dominio, porta)
    url_api = f"{base_url}/player_api.php?username={usuario}&password={senha}&action=get_vod_streams"

    log(f"{AZUL}\nConectando à API: {url_api}{RESET}")
    try:
        resp = requests.get(url_api, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        dados = resp.json()
        if not isinstance(dados, list):
            dados = dados.get("available_channels", []) if isinstance(dados, dict) else []
    except Exception as e:
        log(f"{VERMELHO}Erro ao buscar dados da API: {e}{RESET}")
        exit()

    # Tenta mapear nomes das categorias
    catmap = fetch_vod_categories(base_url, usuario, senha)

    filmes = []
    for item in dados:
        try:
            nome = (item.get("name") or "").strip()
            cat_id = str(item.get("category_id", "")).strip()
            logo = (item.get("stream_icon") or "").strip()
            ext = (item.get("container_extension") or "mp4").strip()
            stream_id = item.get("stream_id")

            if not nome or not stream_id:
                continue

            url_real = f"{base_url}/movie/{usuario}/{senha}/{stream_id}.{ext}"

            filmes.append({
                "nome": nome,
                "categoria_txt": catmap.get(cat_id, f"Categoria_{cat_id}"),
                "logo": logo,
                "url": url_real
            })
        except Exception as e:
            log(f"{VERMELHO}Erro ao processar item da API: {e}{RESET}")
            continue

    log(f"{AZUL}Total de filmes carregados da API: {len(filmes)}{RESET}")
    return filmes


# ========================= TXT =========================
def ler_lista_txt(path='lista.txt'):
    """
    Aceita dois formatos:
    1) M3U estendido: linhas #EXTINF com tvg-name, group-title, tvg-logo, seguida da URL
    2) Pipe-separated: nome|categoria|logo|url
    """
    if not os.path.exists(path):
        log(f"{VERMELHO}Arquivo {path} não encontrado!{RESET}")
        return []

    with open(path, 'r', encoding='utf-8') as f:
        conteudo = f.read()

    filmes = []
    if "#EXTINF" in conteudo:
        # M3U
        linhas = conteudo.splitlines()
        i = 0
        while i < len(linhas):
            linha = linhas[i].strip()
            if linha.startswith('#EXTINF'):
                info = linha
                url = linhas[i + 1].strip() if (i + 1) < len(linhas) else ''
                nome = re.search(r'tvg-name="([^"]+)"', info)
                cat = re.search(r'group-title="([^"]+)"', info)
                logo = re.search(r'tvg-logo="([^"]+)"', info)
                if nome and cat and logo and url:
                    filmes.append({
                        'nome': nome.group(1).strip(),
                        'categoria_txt': cat.group(1).strip(),
                        'logo': logo.group(1).strip(),
                        'url': url
                    })
                i += 2
            else:
                i += 1
    else:
        # Pipe-separated
        for linha in conteudo.splitlines():
            partes = linha.strip().split("|")
            if len(partes) >= 4:
                filmes.append({
                    "nome": partes[0].strip(),
                    "categoria_txt": partes[1].strip(),
                    "logo": partes[2].strip(),
                    "url": partes[3].strip()
                })

    log(f"{AZUL}Total de filmes carregados de {path}: {len(filmes)}{RESET}")
    return filmes


# ========================= Main =========================
def main():
    global usar_tmdb, conn, cursor

    conn = conectar()
    cursor = conn.cursor()

    # Garante a coluna source_tag_filmes em `streams`
    ensure_source_tag_filmes_column(cursor, conn)

    carregar_arquivos_existentes(cursor)
    log(f"{AZUL}Iniciando importação de filmes...{RESET}")

    # Escolha da origem
    log(f"{AZUL}\nEscolha a origem dos filmes:{RESET}")
    log("1. Carregar via API IPTV (M3U)")
    log("2. Carregar de arquivo lista.txt")
    escolha = input("Escolha (1 ou 2): ").strip()

    if escolha == "2":
        filmes = ler_lista_txt()
    else:
        filmes = buscar_lista_api()

    if not filmes:
        log(f"{VERMELHO}Nenhum filme encontrado.{RESET}")
        return

    log(f"{AZUL}Total de filmes encontrados: {len(filmes)}{RESET}")

    if input(f"\n{AMARELO}Deseja buscar informações do TMDb para cada filme? (S/N): {RESET}").strip().lower() == 's':
        usar_tmdb = True
        obter_generos_tmdb()
        log(f"{AZUL}Busca no TMDb ativada.{RESET}")
    else:
        log(f"{AMARELO}Busca no TMDb desativada.{RESET}")

    # Agrupa por categoria "lógica"
    grupos = defaultdict(list)
    for f in filmes:
        grupos[f['categoria_txt']].append(f)

    # Remove grupos ignorados por prefixo
    grupos = {
        k: v for k, v in grupos.items()
        if not any(k.lower().startswith(p.lower()) for p in IGNORAR_GRUPOS_PREFIXO)
    }

    # Carrega categorias do DB
    categorias_db = obter_categorias(cursor)

    # Escolha dos bouquets
    bouquet_id_normal = escolher_bouquet(cursor, "filmes")
    bouquet_id_adulto = escolher_bouquet(cursor, "adultos")

    # Loop de seleção de categorias
    while True:
        if not grupos:
            log(f"{AMARELO}Não há categorias para processar.{RESET}")
            break

        log(f"\n{AMARELO}Categorias disponíveis:{RESET}")
        lista_grupos = list(grupos.keys())
        for idx, grupo in enumerate(lista_grupos, 1):
            log(f"{idx}. {grupo}")

        escolha = input(f"\nDigite os números das categorias que deseja processar (separados por vírgula) ou 'S' para sair: ")
        if escolha.lower().strip() == 's':
            break

        try:
            indices = [int(i.strip()) for i in escolha.split(',') if i.strip()]
            selecionadas = [lista_grupos[i - 1] for i in indices if 1 <= i <= len(lista_grupos)]
            if not selecionadas:
                raise ValueError
        except Exception:
            log(f"{VERMELHO}Entrada inválida.{RESET}")
            continue

        # Mapeamento de categorias "texto" -> ID no DB
        mapeamento = {}
        for grupo in selecionadas:
            sugestao = sugerir_categoria(grupo, categorias_db)
            if sugestao:
                log(f"\n{AMARELO}Vincular '{grupo}' à categoria sugerida '{sugestao[1]}' (ID {sugestao[0]})?{RESET}")
            else:
                log(f"\nVincular '{grupo}' a qual categoria (ID)?")

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

        # Processa cada categoria selecionada
        for grupo in selecionadas:
            filmes_cat = grupos[grupo]
            is_adulto = categoria_adulta(grupo)
            bouquet_usar = bouquet_id_adulto if is_adulto else bouquet_id_normal
            processar_categoria(cursor, conn, grupo, filmes_cat, mapeamento[grupo], bouquet_usar)

        # Remove as categorias já processadas
        for g in selecionadas:
            grupos.pop(g, None)

    cursor.close()
    conn.close()
    salvar_relatorio()
    log(f"\n{AZUL}Processamento finalizado.{RESET}")


if __name__ == "__main__":
    main()
