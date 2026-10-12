#!/usr/bin/env python3
"""
Verificador da Urna do Garoto;  —  não confie em ninguém. Nem em mim. Confere.
por Garoto do Programa;  (github.com/garotodoprograma404/urna-do-garoto)

Pega o mural público (um JSON) e refaz TUDO sozinho:
  1. o grupo matemático é o do grupo.py (e, com --paranoico, refeito da semente pública)?
  2. a cerimônia: cada guardião provou que conhece a parte dele? a chave é o produto das partes?
  3. cada cédula: cifras no grupo, "0 ou 1" em cada opção, "soma = 1" na cédula, nenhuma cifra copiada?
  4. as urnas: só as do manifesto, cada corrente inteira, cada ficha numa sessão só, e (com a ata das
     portas) o elo final e as contas da mesa batem com o que foi fotografado na seção?
  5. cada cédula desafiada: os segredos reproduzem exatamente as cifras?
  6. a soma cifrada é mesmo o produto das cédulas depositadas?
  7. a apuração: k guardiões, cada fatia com prova, e o resultado anunciado é o que a soma abre?

Este arquivo NÃO importa a urna (urna.py): refaz as receitas de hash a partir da especificação
(PROTOCOLO.md). Mas usa cripto.py e guardioes.py, as MESMAS peças matemáticas que a urna e os guardiões
usam pra provar: um bug nelas engana os dois. Por isso o PROTOCOLO.md tem vetores de teste. Escreve o SEU
verificador, na sua linguagem. Se o seu e o meu disserem OK, não precisa confiar em nenhum dos dois.

Uso:
  python3 verificador.py mural.json --ata ata.json        # confere tudo, com a ata das portas
  python3 verificador.py mural.json --ata ata.json --contexto 1a2b…   # e amarra no que foi publicado antes
  python3 verificador.py mural.json --ata minhas.json --ata-parcial    # só as seções que VOCÊ fotografou
  python3 verificador.py mural.json --paranoico           # e ainda refaz o grupo da semente (~20-30 s)
  python3 verificador.py mural.json --recibo 8FFF-… --ficha 3A9C-…              # eu CONFIRMEI
  python3 verificador.py mural.json --recibo 8FFF-… --ficha 3A9C-… --desafiei   # eu DESAFIEI
  python3 verificador.py mural.json --recibos coleta.txt  # coleta pública: dois eleitores com o mesmo recibo?
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cripto as C
import guardioes as GU
from grupo import GRUPO, IMPRESSAO_DIGITAL, gerar_grupo, valida_grupo

P, Q, G = GRUPO.p, GRUPO.q, GRUPO.g
VERSAO = "urna-do-garoto/v2"
HEX = re.compile(r"0|[1-9a-f][0-9a-f]{0,799}")  # canônico: minúsculo, sem zero à esquerda
FICHA = re.compile(r"[0-9a-f]{16}")
RECIBO = re.compile(r"[0-9a-f]{32,64}")  # o recibo impresso tem 32 dígitos; o QR code, os 64
DEPOSITADA, DESAFIADA, SEM_VOTO = "DEPOSITADA", "DESAFIADA", "SEM_VOTO"
COR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def pinta(texto: object, codigo: str) -> str:
    return f"\033[{codigo}m{texto}\033[0m" if COR else str(texto)


def limpo(x: object, n: int = 300) -> str:
    """Texto que veio do mural, seguro pra imprimir: sem escape de terminal e sem quebra de linha."""
    return "".join(ch if ch.isprintable() else "�" for ch in str(x))[:n]


def qtd(n: int, palavra: str, plural: str | None = None) -> str:
    return f"{n} {palavra if n == 1 else plural or palavra + 's'}"


def cedulas(n: int) -> str:
    return qtd(n, "cédula")


def eleitores_(n: int) -> str:
    return qtd(n, "eleitor", "eleitores")


def sessoes(n: int) -> str:
    return qtd(n, "sessão sem voto", "sessões sem voto")


def devolvidas_(n: int) -> str:
    return qtd(n, "ficha devolvida", "fichas devolvidas")


def so_digitos(x: str) -> str:
    return x.replace("-", "").replace(" ", "").lower()


def ficha_impressa(ficha: str) -> str:
    return "-".join(ficha[i : i + 4] for i in range(0, 16, 4)).upper()


@functools.cache
def problemas_do_grupo(paranoico: bool = False) -> tuple[str, ...]:
    """Miller-Rabin no p de 3072 bits leva uns segundos: confere uma vez por execução."""
    problemas = valida_grupo(GRUPO)
    if GRUPO.impressao_digital() != IMPRESSAO_DIGITAL:
        problemas.append("a impressão digital do grupo não é a publicada")
    if paranoico and gerar_grupo() != GRUPO:
        problemas.append("refazendo da semente pública, o grupo deu OUTRO número")
    return tuple(problemas)


class MuralInvalido(Exception):
    pass


ERROS_DE_FORMATO = (KeyError, TypeError, ValueError, AttributeError, IndexError, RecursionError, MuralInvalido)


def num(x: object) -> int:
    """Hexadecimal do mural → inteiro. Só a forma canônica; qualquer coisa estranha é recusada."""
    if not isinstance(x, str) or not HEX.fullmatch(x):
        raise MuralInvalido(f"número mal formado: {limpo(x, 40)!r}")
    return int(x, 16)


def inteiro(x: object, campo: str) -> int:
    """Contagem do mural: int de verdade (True não vale 1) e não negativo."""
    if type(x) is not int or x < 0:
        raise MuralInvalido(f"{campo} inválido: {limpo(x, 40)!r}")
    return x


def texto(x: object, campo: str) -> str:
    if not isinstance(x, str) or not x or len(x) > 200:
        raise MuralInvalido(f"{campo} inválido: {limpo(x, 40)!r}")
    return x


def ficha(x: object) -> str:
    if not isinstance(x, str) or not FICHA.fullmatch(x):
        raise MuralInvalido(f"ficha inválida: {limpo(x, 40)!r}")
    return x


def campos(obj: object, esperados: set[str], onde: str) -> dict:
    """Só os campos do protocolo. Campo a mais (um "cpf" escondido na cédula, por exemplo) é recusado."""
    if not isinstance(obj, dict):
        raise MuralInvalido(f"{onde} não é um objeto")
    if set(obj) != esperados:
        diferenca = sorted(set(obj) ^ esperados)
        raise MuralInvalido(f"{onde} com campos fora do protocolo: {diferenca[:4]}")
    return obj


CAMPOS_MURAL = {
    "versao",
    "grupo",
    "manifesto",
    "cerimonia",
    "chave",
    "contexto",
    "urnas",
    "cedulas",
    "apuracao",
    "lacre",
}
CAMPOS_CEDULA = {"id", "urna", "anterior", "ficha", "codigo", "cifras", "provas", "prova_soma", "estado", "abertura"}
CAMPOS_SEM_VOTO = {"id", "urna", "anterior", "ficha", "codigo", "estado"}
CAMPOS_FECHO = {"comparecimento", "devolvidas", "depositadas", "sem_voto", "elo_final", "fechamento"}
CAMPOS_PORTA = {"comparecimento", "devolvidas", "depositadas", "sem_voto", "elo_final"}


def textos_unicos(xs: object, campo: str) -> list[str]:
    if not isinstance(xs, list) or not xs or len({texto(x, campo) for x in xs}) != len(xs):
        raise MuralInvalido(f"lista de {campo} inválida ou repetida")
    return xs


# ---------------------------------------------------------------- receitas de hash (PROTOCOLO.md, seção 3)
def pre_contexto(man: dict) -> str:
    return C.hash_hex(
        "pre-contexto",
        P,
        Q,
        G,
        man["eleicao"],
        tuple(man["opcoes"]),
        tuple(man["guardioes"]),
        man["quorum"],
        tuple(man["urnas"]),
    )


def contexto(pre: str, compromissos: list[GU.Compromissos]) -> str:
    return C.hash_hex("contexto", pre, [(c.numero, c.nome, c.coeficientes) for c in compromissos])


def codigo_da_cedula(ctx: str, reg: dict, cifras: list[C.Cifra], provas: list[C.ProvaZeroOuUm], soma) -> str:
    return C.hash_hex(
        "codigo",
        ctx,
        reg["anterior"],
        reg["id"],
        reg["ficha"],
        [(cf.alfa, cf.beta) for cf in cifras],
        [(p.c0, p.c1, p.v0, p.v1) for p in provas],
        (soma.c, soma.v),
    )


def codigo_sem_voto(ctx: str, reg: dict) -> str:
    return C.hash_hex("sem-voto", ctx, reg["anterior"], reg["id"], reg["ficha"])


# ---------------------------------------------------------------- 3. uma cédula (roda em paralelo)
def _inicia_trabalhador(chave: int) -> None:
    C.fixa(chave)


def confere_cedula(args: tuple) -> tuple[list[str], list[int]]:
    """Confere a matemática de UMA cédula. Devolve (problemas, alfas) — os alfas servem pra achar cópia."""
    reg, ctx, chave, n = args
    if not isinstance(reg, dict):
        return ["cédula que não é um objeto"], []
    rid = limpo(reg.get("id"), 40)
    if reg.get("estado") == SEM_VOTO:  # sessão sem voto: entra na corrente, sem cifra nenhuma
        try:
            campos(reg, CAMPOS_SEM_VOTO, f"sessão sem voto {rid}")
            texto(reg["id"], "id")
            texto(reg["anterior"], "anterior")
            ficha(reg["ficha"])
        except ERROS_DE_FORMATO as e:
            return [f"{rid}: sessão sem voto mal formada ({e})"], []
        if reg.get("codigo") != codigo_sem_voto(ctx, reg):
            return [f"{rid}: o código da sessão sem voto não bate"], []
        return [], []
    try:
        campos(reg, CAMPOS_CEDULA, f"cédula {rid}")
        if reg["abertura"] is not None:
            campos(reg["abertura"], {"escolha", "segredos"}, f"abertura da {rid}")
        texto(reg["id"], "id")
        texto(reg["anterior"], "anterior")
        ficha(reg["ficha"])
        cifras = [C.Cifra(num(a), num(b)) for a, b in reg["cifras"]]
        provas = [C.ProvaZeroOuUm(*(num(x) for x in pr)) for pr in reg["provas"]]
        soma = C.ProvaIgualdade(*(num(x) for x in reg["prova_soma"]))
    except ERROS_DE_FORMATO as e:
        return [f"{rid}: cédula mal formada ({e})"], []
    if len(cifras) != n or len(provas) != n:
        return [f"{rid}: número de opções errado"], []
    problemas = []
    if not all(cf.valida() for cf in cifras):
        problemas.append(f"{rid}: cifra fora do grupo")
    else:
        for i, (cf, pr) in enumerate(zip(cifras, provas, strict=True)):
            if not C.confere_zero_ou_um(pr, (ctx, reg["id"], i), chave, cf):
                motivo = " (segredo zero: o voto está em claro)" if cf.alfa == 1 else ""
                problemas.append(f'{rid}: prova "0 ou 1" da opção {i} não fecha{motivo}')
        total = math.prod(cifras, start=C.CIFRA_ZERO)
        if not C.confere_soma(soma, (ctx, reg["id"]), chave, total, 1):
            problemas.append(f'{rid}: prova "soma = 1" não fecha (mais de um voto, ou nenhum)')
    if reg.get("codigo") != codigo_da_cedula(ctx, reg, cifras, provas, soma):
        problemas.append(f"{rid}: o código de confirmação não bate com a cédula (o recibo do eleitor não aparece)")
    return problemas, [cf.alfa for cf in cifras]


def confere_abertura(ctx: str, chave: int, opcoes: tuple[str, ...], reg: dict) -> str | None:
    """Refaz as cifras com os segredos revelados. Devolve a opção que a urna cifrou de verdade, ou None se a
    abertura não reproduzir a cédula. NÃO confere se a cédula é a do código impresso: na cabine, use
    confere_desafio_na_cabine."""
    abertura = reg.get("abertura")
    if not isinstance(abertura, dict):
        return None
    escolha, segredos = abertura.get("escolha"), abertura.get("segredos")
    if escolha not in opcoes or not isinstance(segredos, list) or len(segredos) != len(opcoes):
        return None
    try:
        rs = [num(r) for r in segredos]
        cifras = [C.Cifra(num(a), num(b)) for a, b in reg["cifras"]]
    except ERROS_DE_FORMATO:
        return None
    if len(cifras) != len(opcoes) or not all(GRUPO.expoente(r) for r in rs):
        return None
    for i, (r, cf) in enumerate(zip(rs, cifras, strict=True)):
        if C.cifra(chave, int(opcoes[i] == escolha), r) != cf:
            return None
    return escolha


def confere_desafio_na_cabine(
    ctx: str, chave: int, opcoes: tuple[str, ...], reg: dict, codigo_impresso: str, na_tela: str, ficha=None
) -> str | None:
    """O app do eleitor (ou do fiscal), NA CABINE, logo depois do DESAFIA. Devolve None se está tudo certo,
    ou o motivo da reclamação. A cédula aberta tem que ser a do código impresso ANTES do botão: sem isso,
    a urna troca a cédula na hora do desafio e abre uma honesta."""
    problemas, _ = confere_cedula((reg, ctx, chave, len(opcoes)))  # provas, e o código = hash da cédula
    if problemas:
        return problemas[0]
    if reg.get("estado") != DESAFIADA:
        return "a urna não marcou a cédula como DESAFIADA"
    if not reg["codigo"].startswith(so_digitos(codigo_impresso)) or len(so_digitos(codigo_impresso)) < 32:
        return "a urna abriu OUTRA cédula, não a do código que ela imprimiu antes do botão"
    if ficha is not None and reg["ficha"] != so_digitos(ficha):
        return "a cédula aberta não tem a minha ficha"
    cifrou = confere_abertura(ctx, chave, opcoes, reg)
    if cifrou is None:
        return "os segredos não reproduzem a cédula (a urna mentiu no desafio)"
    if cifrou != na_tela:
        return f"na tela {na_tela!r}, a urna cifrou {cifrou!r}"
    return None


# ---------------------------------------------------------------- o verificador
class Verificador:
    def __init__(
        self, mural: dict, saida=print, paralelo=True, ata=None, ate=7, paranoico=False, ata_parcial=False
    ) -> None:
        self.mural, self.saida, self.paralelo = mural, saida, paralelo
        self.ata, self.ate, self.paranoico, self.ata_parcial = ata, ate, paranoico, ata_parcial
        self.problemas: list[str] = []
        self.sem_porta: list[str] = []  # com --ata-parcial: as seções que ninguém te mostrou a foto

    def falha(self, texto: str) -> None:
        self.problemas.append(texto)

    def passo(self, numero: int, titulo: str) -> int:
        self.saida(pinta(f"\n[{numero}/7] {titulo}", "1"))
        return len(self.problemas)

    def resultado_do_passo(self, antes: int, ok: str) -> None:
        novos = self.problemas[antes:]
        for p in novos[:8]:
            self.saida(pinta(f"   ✗ {limpo(p)}", "31"))
        if len(novos) > 8:
            self.saida(pinta(f"   ✗ … e mais {len(novos) - 8}", "31"))
        if not novos:
            self.saida(pinta(f"   ✓ {limpo(ok, 400)}", "32"))

    def roda(self) -> list[str]:
        try:
            self._roda()
        except ERROS_DE_FORMATO as e:
            self.falha(f"mural mal formado: {e!r}"[:300])
            self.saida(pinta(f"   ✗ mural mal formado: {limpo(repr(e))}", "31"))
        return self.problemas

    def _roda(self) -> None:
        m = self.mural
        if not isinstance(m, dict) or m.get("versao") != VERSAO:
            raise MuralInvalido("não é um mural da Urna do Garoto v2")
        campos(m, CAMPOS_MURAL, "o mural")

        antes = self.passo(1, "o grupo matemático")
        grupo = campos(m["grupo"], {"p", "q", "g"}, "o grupo")
        if (num(grupo["p"]), num(grupo["q"]), num(grupo["g"])) != (P, Q, G):
            self.falha("o mural usa outro grupo, não o da semente pública")
        for problema in problemas_do_grupo(self.paranoico):
            self.falha(problema)
        origem = "refeitos da semente agora" if self.paranoico else "iguais aos do grupo.py (--paranoico refaz)"
        self.resultado_do_passo(
            antes,
            f"p de {P.bit_length()} bits e q de {Q.bit_length()} bits, primos, {origem}; "
            f"impressão digital {GRUPO.impressao_digital()[:16]}…",
        )

        antes = self.passo(2, "a cerimônia das chaves")
        man = campos(m["manifesto"], {"eleicao", "opcoes", "guardioes", "quorum", "urnas"}, "o manifesto")
        texto(man["eleicao"], "nome da eleição")
        opcoes = textos_unicos(man["opcoes"], "opções")
        nomes = textos_unicos(man["guardioes"], "guardiões")
        urnas = textos_unicos(man["urnas"], "urnas")
        quorum = inteiro(man["quorum"], "quórum")
        if not 2 <= quorum <= len(nomes):
            raise MuralInvalido("quórum fora do intervalo (de 2 até o número de guardiões)")
        compromissos = [
            GU.Compromissos(
                inteiro(c["numero"], "número do guardião"),
                texto(c["nome"], "nome do guardião"),
                tuple(num(x) for x in c["coeficientes"]),
                tuple(C.ProvaConhecimento(num(a), num(b)) for a, b in c["provas"]),
            )
            for c in (campos(x, {"numero", "nome", "coeficientes", "provas"}, "guardião") for x in m["cerimonia"])
        ]
        pre = pre_contexto(man)
        if [(c.numero, c.nome) for c in compromissos] != [(i + 1, nome) for i, nome in enumerate(nomes)]:
            self.falha("os guardiões da cerimônia não são os do manifesto")
        for c in compromissos:
            if not GU.confere_compromissos(c, pre, quorum):
                self.falha(f"guardião {c.nome}: prova de conhecimento não fecha (chave pirata?)")
        chave = num(m["chave"])
        if self.problemas[antes:]:  # compromisso fora do grupo: nem faz a conta da chave
            self.resultado_do_passo(antes, "")
            return
        if chave != GU.chave_da_eleicao(compromissos) or not C.pertence(chave) or chave == 1:
            self.falha("a chave da eleição não é o produto das partes dos guardiões")
        ctx = contexto(pre, compromissos)
        if m["contexto"] != ctx:
            self.falha("o contexto da eleição não bate")
        if self.problemas[antes:]:
            self.resultado_do_passo(antes, "")
            return  # sem chave confiável, conferir cédula não faz sentido
        C.fixa(chave)
        self.resultado_do_passo(antes, f"{len(nomes)} guardiões, cada um provou a sua parte; abre com {quorum}")

        antes = self.passo(3, "a matemática de cada cédula")
        cedulas = m["cedulas"]
        if not isinstance(cedulas, list):
            raise MuralInvalido("cédulas não é uma lista")
        tarefas = [(reg, ctx, chave, len(opcoes)) for reg in cedulas]
        if self.paralelo and len(tarefas) > 20:
            with ProcessPoolExecutor(initializer=_inicia_trabalhador, initargs=(chave,)) as pool:
                resultados = list(pool.map(confere_cedula, tarefas, chunksize=8))
        else:
            resultados = [confere_cedula(t) for t in tarefas]
        vistos: dict[int, str] = {}
        for reg, (problemas, alfas) in zip(cedulas, resultados, strict=True):
            for p in problemas:
                self.falha(p)
            for alfa in alfas:
                if alfa in vistos:
                    self.falha(f"{reg['id']}: cifra copiada de {vistos[alfa]} (ataque de repetição)")
                vistos[alfa] = reg["id"]
        if self.problemas[antes:]:
            self.resultado_do_passo(antes, "")
            return
        votos = [reg for reg in cedulas if reg["estado"] != SEM_VOTO]
        self.resultado_do_passo(antes, f"{qtd(len(votos), 'cédula')}: 0 ou 1 em cada opção, soma 1, nenhuma cópia")

        antes = self.passo(4, "as urnas: lista do manifesto, corrente, fichas e ata das portas")
        depositadas_total, sem_voto_total = self._urnas(m, ctx, urnas)
        ancora = "(sem a ata das portas)"
        if self.ata is not None:
            com_porta = len(urnas) - len(self.sem_porta)
            ancora = (
                "e com a ata das portas" if not self.sem_porta else f"e com a ata de {com_porta} de {len(urnas)} portas"
            )
        sem_voto = f", {qtd(sem_voto_total, 'ficha')} sem voto" if sem_voto_total else ""
        self.resultado_do_passo(
            antes,
            f"{qtd(len(urnas), 'urna')} do manifesto, corrente inteira, "
            f"{depositadas_total} cédulas = {depositadas_total} eleitores{sem_voto} {ancora}",
        )

        antes = self.passo(5, "as cédulas desafiadas")
        desafiadas = [reg for reg in cedulas if reg["estado"] == DESAFIADA]
        for reg in desafiadas:
            if confere_abertura(ctx, chave, tuple(opcoes), reg) is None:
                self.falha(f"{reg['id']}: os segredos revelados não reproduzem a cédula (urna mentiu no desafio)")
        for reg in cedulas:
            if reg["estado"] == DEPOSITADA and reg.get("abertura") is not None:
                self.falha(f"{reg['id']}: cédula depositada com segredos expostos (voto deixou de ser secreto)")
        self.resultado_do_passo(
            antes,
            f"{qtd(len(desafiadas), 'desafio')}: os segredos abrem cada cédula desafiada "
            "(quem desafiou confere se é a opção que viu na tela)",
        )
        if self.ate <= 5:
            return

        antes = self.passo(6, "a soma cifrada")
        somas = totais(m)
        if m["apuracao"] is None:
            raise MuralInvalido("o mural não tem apuração")
        ap = campos(m["apuracao"], {"totais", "fatias", "recusados", "resultado"}, "a apuração")
        if [C.Cifra(num(a), num(b)) for a, b in ap["totais"]] != somas:
            self.falha("a soma cifrada publicada não é o produto das cédulas depositadas")
        self.resultado_do_passo(antes, "multipliquei as cifras das depositadas de novo: dá a soma publicada")

        antes = self.passo(7, "a apuração")
        presentes = [
            inteiro(campos(f, {"guardiao", "por_opcao"}, "fatia")["guardiao"], "guardião") for f in ap["fatias"]
        ]
        if len(set(presentes)) != len(presentes) or len(presentes) < quorum:
            self.falha(f"apuração com {len(set(presentes))} guardiões diferentes; precisa de {quorum}")
        if not set(presentes) <= set(range(1, len(nomes) + 1)):
            raise MuralInvalido("guardião desconhecido na apuração")
        recusados = ap["recusados"]
        if (
            not isinstance(recusados, list)
            or len(set(recusados)) != len(recusados)
            or not set(recusados) <= set(nomes) - {nomes[i - 1] for i in presentes}
        ):
            self.falha("a lista de guardiões recusados não faz sentido")
        fatias_por_guardiao = {}
        for f in ap["fatias"]:
            numero = f["guardiao"]
            verificacao = GU.chave_de_verificacao(compromissos, numero)
            fatias = [
                GU.FatiaDecifrada(numero, num(mm), C.ProvaIgualdade(num(c), num(v))) for mm, c, v in f["por_opcao"]
            ]
            if len(fatias) != len(opcoes):
                raise MuralInvalido("fatia com número de opções errado")
            for i, (fatia, total) in enumerate(zip(fatias, somas, strict=True)):
                if not GU.confere_fatia(fatia, ctx, i, verificacao, total):
                    self.falha(f"guardião {nomes[numero - 1]}: a fatia da opção {opcoes[i]!r} não tem prova válida")
            fatias_por_guardiao[numero] = fatias
        anunciado = ap["resultado"]
        if not isinstance(anunciado, dict) or list(anunciado) != list(opcoes):
            self.falha("o resultado não traz as opções do manifesto")
            anunciado = {}
        for opcao, votos in anunciado.items():
            if type(votos) is not int or not 0 <= votos <= depositadas_total:
                mostra = str(votos)
                if len(mostra) > 12:
                    mostra = f"{mostra[:7]}… ({len(mostra.lstrip('-'))} dígitos)"
                self.falha(f"{opcao}: {mostra} votos está fora de 0 a {depositadas_total} (conta que deu a volta?)")
        if anunciado and len(self.problemas) == antes:
            for i, (opcao, total) in enumerate(zip(opcoes, somas, strict=True)):
                alfa_s = GU.combina([fs[i] for fs in fatias_por_guardiao.values()])
                g_votos = total.beta * pow(alfa_s, -1, P) % P
                if pow(G, anunciado[opcao], P) != g_votos:
                    aberto = C.log_pequeno(g_votos, depositadas_total)
                    self.falha(f"{opcao}: anunciaram {anunciado[opcao]}, a soma cifrada abre {aberto}")
            if sum(anunciado.values()) != depositadas_total:
                self.falha(f"o resultado soma {sum(anunciado.values())} votos, mas foram {depositadas_total} cédulas")
        placar = " · ".join(f"{k} {v}" for k, v in anunciado.items())
        self.resultado_do_passo(antes, f"{len(presentes)} guardiões abriram a soma, cada fatia com prova: {placar}")

        if m.get("lacre") != lacre(m):
            self.falha("o lacre do mural não bate (o arquivo foi mexido depois de lacrado)")
            self.saida(pinta("\n   ✗ o lacre do mural não bate", "31"))

    def _urnas(self, m: dict, ctx: str, urnas: list[str]) -> tuple[int, int]:
        """Passo 4. Devolve (depositadas, sessões sem voto) somadas em todas as urnas."""
        atas = m["urnas"]
        if not isinstance(atas, dict):
            raise MuralInvalido("urnas não é um objeto")
        for fantasma in sorted(set(atas) - set(urnas)):
            self.falha(f"urna fantasma: {fantasma!r} não está no manifesto")
        for sumida in sorted(set(urnas) - set(atas)):
            self.falha(f"a urna {sumida!r} do manifesto sumiu do mural")
        por_urna: dict[str, list[dict]] = defaultdict(list)
        for reg in m["cedulas"]:
            if reg["urna"] not in urnas:
                self.falha(f"{reg['id']}: cédula de urna fora do manifesto")
            por_urna[reg["urna"]].append(reg)
        externa = None
        if self.ata is not None:
            campos(self.ata, {"versao", "contexto", "urnas"}, "a ata")
            if self.ata["versao"] != VERSAO or self.ata["contexto"] != ctx or not isinstance(self.ata["urnas"], dict):
                raise MuralInvalido("a ata não é desta eleição")
            externa = self.ata["urnas"]
            for estranha in sorted(set(externa) - set(urnas)):
                self.falha(f"a ata traz uma urna que não está no manifesto: {estranha!r}")
        depositadas_total = sem_voto_total = 0
        for urna in urnas:
            if urna not in atas:
                continue
            fecho = campos(atas[urna], CAMPOS_FECHO, f"o fechamento da {urna}")
            elo = C.hash_hex("inicio", ctx, urna)
            depositadas = sem_voto = 0
            sessao, usadas, da_sessao = None, set(), []
            for seq, reg in enumerate(por_urna.get(urna, []), start=1):
                if reg["id"] != f"{urna}/{seq:06d}":
                    self.falha(f"{urna}: esperava a cédula {seq:06d}, veio {reg['id']} (cédula sumiu ou foi enfiada)")
                if reg["anterior"] != elo:
                    self.falha(f"{reg['id']}: a corrente quebrou aqui (alguém mexeu na cédula anterior)")
                estado = reg["estado"]
                if estado not in (DEPOSITADA, DESAFIADA, SEM_VOTO):
                    raise MuralInvalido(f"{reg['id']}: estado inválido")
                # a sessão de uma ficha: desafios (zero ou mais) e UM fim: DEPOSITADA ou SEM_VOTO
                if sessao is None:
                    if reg["ficha"] in usadas:
                        da_sessao.append(f"{reg['id']}: a ficha {ficha_impressa(reg['ficha'])} já tinha sido usada")
                    sessao = reg["ficha"]
                elif reg["ficha"] != sessao:
                    da_sessao.append(f"{reg['id']}: a sessão da ficha {ficha_impressa(sessao)} acabou sem fim")
                    usadas.add(sessao)
                    sessao = reg["ficha"]
                if estado != DESAFIADA:
                    usadas.add(sessao)
                    sessao = None
                depositadas += estado == DEPOSITADA
                sem_voto += estado == SEM_VOTO
                elo = C.hash_hex("elo", ctx, reg["codigo"], estado)
            if sessao is not None:
                da_sessao.append(f"{urna}: a última sessão (ficha {ficha_impressa(sessao)}) não terminou")
            depositadas_total += depositadas
            sem_voto_total += sem_voto
            comparecimento = inteiro(fecho["comparecimento"], "comparecimento")
            devolvidas = inteiro(fecho["devolvidas"], "devolvidas")
            if elo != fecho["elo_final"] or fecho["fechamento"] != C.hash_hex(
                "fechamento", ctx, urna, elo, depositadas, sem_voto
            ):
                self.falha(f"{urna}: o elo final do mural não bate com a corrente")
            eleitores = comparecimento - devolvidas  # fichas liberadas menos as que voltaram sem voto
            if not depositadas == inteiro(fecho["depositadas"], "depositadas") == eleitores:
                self.falha(f"{urna}: {cedulas(depositadas)} no mural × {eleitores_(eleitores)} contados pela mesa")
            if not sem_voto == inteiro(fecho["sem_voto"], "sem voto") == devolvidas:
                self.falha(f"{urna}: {sessoes(sem_voto)} no mural × {devolvidas_(devolvidas)} na mesa")
            if externa is not None:
                porta = externa.get(urna)
                if porta is None and self.ata_parcial:
                    self.sem_porta.append(urna)
                elif porta is None:
                    self.falha(f"{urna}: não tem ata (ninguém fotografou a porta)")
                else:
                    campos(porta, CAMPOS_PORTA, f"a ata da {urna}")
                    na_ata = inteiro(porta["comparecimento"], "comparecimento da ata") - inteiro(
                        porta["devolvidas"], "devolvidas da ata"
                    )
                    if depositadas != na_ata:
                        self.falha(f"{urna}: {cedulas(depositadas)} no mural × {eleitores_(na_ata)} na ata da mesa")
                    if porta["elo_final"] != elo:
                        self.falha(f"{urna}: o elo final não é o que está colado na porta da seção")
                    impressas = (inteiro(porta["depositadas"], "depositadas"), inteiro(porta["sem_voto"], "sem voto"))
                    if impressas != (depositadas, sem_voto):
                        self.falha(
                            f"{urna}: a urna imprimiu na porta {impressas[0]} depositadas e {impressas[1]} sem voto; "
                            f"o mural tem {depositadas} e {sem_voto}"
                        )
                    if sem_voto != porta["devolvidas"]:
                        self.falha(
                            f"{urna}: {sessoes(sem_voto)} no mural × {devolvidas_(porta['devolvidas'])} na ata da mesa"
                        )
            for problema in da_sessao:
                self.falha(problema)
        if externa is None:
            self.saida(pinta("   ⚠ sem --ata: comparecimento e elo final conferidos só contra o próprio mural", "33"))
        elif self.sem_porta:
            faltam = ", ".join(self.sem_porta[:5]) + (" …" if len(self.sem_porta) > 5 else "")
            self.saida(pinta(f"   ⚠ sem a foto da porta: {faltam}", "33"))
        return depositadas_total, sem_voto_total


def totais(mural: dict) -> list[C.Cifra]:
    """Multiplica as cifras das cédulas depositadas: a soma de cada opção, ainda cifrada (ninguém abre nada)."""
    somas = [C.CIFRA_ZERO] * len(mural["manifesto"]["opcoes"])
    for reg in mural["cedulas"]:
        if reg["estado"] == DEPOSITADA:
            for i, (a, b) in enumerate(reg["cifras"]):
                somas[i] = somas[i] * C.Cifra(num(a), num(b))
    return somas


_JA_CONFERIDOS: dict[str, tuple[str, ...]] = {}


def confere_para_apuracao(mural: dict, ata: dict) -> tuple[str, ...]:
    """Os passos 1 a 5, com a ata: o que cada guardião roda antes de abrir a parte dele.
    Na simulação os guardiões moram no mesmo processo; o mesmo arquivo não precisa ser conferido 3 vezes."""
    try:
        digital = hashlib.sha256(json.dumps([mural, ata], sort_keys=True).encode()).hexdigest()
    except (TypeError, ValueError):
        return tuple(verifica(mural, saida=lambda _: None, ata=ata, ate=5))
    if digital not in _JA_CONFERIDOS:
        _JA_CONFERIDOS[digital] = tuple(verifica(mural, saida=lambda _: None, ata=ata, ate=5))
    return _JA_CONFERIDOS[digital]


def lacre(mural: dict) -> str:
    corpo = {k: v for k, v in mural.items() if k != "lacre"}
    return C.hash_hex("lacre", json.dumps(corpo, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def verifica(mural: dict, saida=print, paralelo=True, ata=None, ate=7, paranoico=False) -> list[str]:
    return Verificador(mural, saida, paralelo, ata, ate, paranoico).roda()


# ---------------------------------------------------------------- o eleitor em casa
def procura_recibo(mural: dict, recibo: str) -> list[dict]:
    """Todas as cédulas cujo código começa pelo recibo inteiro (32 dígitos impressos, ou os 64 do QR code)."""
    alvo = so_digitos(recibo)
    if not RECIBO.fullmatch(alvo):
        return []
    return [
        reg
        for reg in mural["cedulas"]
        if isinstance(reg, dict) and isinstance(reg.get("codigo"), str) and reg["codigo"].startswith(alvo)
    ]


def confere_recibo(mural: dict, recibo: str, desafiei: bool = False, ficha: str | None = None) -> tuple[bool, str]:
    """O eleitor em casa. Devolve (tudo certo?, mensagem). A decisão dele importa: se ele CONFIRMOU e o
    mural diz DESAFIADA, a urna trocou a cédula depois do botão. E a FICHA dele também: se o código está lá
    com a ficha de outro, a urna deu a ele o recibo de outro eleitor (ataque de clash)."""
    minha = None
    if ficha is not None:
        minha = so_digitos(ficha)
        if not FICHA.fullmatch(minha):
            return False, "a ficha tem 16 dígitos (4 grupos de 4): confere o que você digitou."
    if not RECIBO.fullmatch(so_digitos(recibo)):
        return False, "o recibo tem 32 dígitos (8 grupos de 4): digita todos, ou lê o QR code (o código inteiro)."
    achadas = procura_recibo(mural, recibo)
    if not achadas:
        jogada_fora = [
            reg
            for reg in mural["cedulas"]
            if minha and isinstance(reg, dict) and reg.get("estado") == SEM_VOTO and reg.get("ficha") == minha
        ]
        if jogada_fora:
            return False, (
                f"o recibo {recibo} NÃO está no mural, e a tua ficha aparece em {jogada_fora[0]['id']} como "
                "SEM VOTO: a urna jogou teu voto fora. Guarda o papel e reclama."
            )
        return False, (
            f"o recibo {recibo} NÃO está no mural. Confere se digitou certo (ou lê o QR code). "
            "Se estiver certo, tua cédula sumiu: guarda o papel e reclama."
        )
    if len(achadas) > 1:
        return False, "mais de uma cédula com esse começo de código: confere pelo QR code (código inteiro)."
    reg = achadas[0]
    n = len(mural["manifesto"]["opcoes"])
    problemas, _ = confere_cedula((reg, mural["contexto"], num(mural["chave"]), n))
    if problemas:
        return False, f"a tua cédula está no mural, mas não confere: {problemas[0]}"
    if minha is not None and reg["ficha"] != minha:
        return False, (
            f"o código {recibo} está no mural ({reg['id']}), mas com a ficha {ficha_impressa(reg['ficha'])}, "
            "não a tua: a urna te deu o recibo de OUTRO eleitor (ataque de clash). Guarda o papel e reclama."
        )
    aviso = (
        ""
        if minha
        else " ⚠ Confere também a tua ficha (--ficha): sem ela, não dá pra saber se a urna te deu o recibo de "
        "outro eleitor."
    )
    if not desafiei:
        if reg["estado"] == DEPOSITADA:
            return (
                True,
                f"recibo encontrado: {reg['id']} DEPOSITADA. Tua cédula está lá, cifrada, e entra na soma." + aviso,
            )
        return False, (
            f"você CONFIRMOU, mas o mural diz que {reg['id']} foi {reg['estado']}: a urna trocou a tua cédula "
            "depois do botão. Guarda o papel e reclama."
        )
    if reg["estado"] != DESAFIADA:
        return False, f"você DESAFIOU, mas {reg['id']} entrou como DEPOSITADA: a urna contou um voto que não valia."
    cifrou = confere_abertura(mural["contexto"], num(mural["chave"]), tuple(mural["manifesto"]["opcoes"]), reg)
    if cifrou is None:
        return False, f"os segredos de {reg['id']} não reproduzem a cédula: a urna mentiu no desafio."
    return True, f"a urna tinha cifrado: {cifrou}. Foi isso que estava na tela? Se não foi, reclama." + aviso


def recibos_repetidos(recibos: list[str]) -> list[str]:
    """Coleta pública de recibos: o mesmo código na mão de dois eleitores é prova de clash."""
    contagem = Counter(so_digitos(r)[:32] for r in recibos if so_digitos(r))
    return sorted(r for r, n in contagem.items() if n > 1)


# ---------------------------------------------------------------- linha de comando
def _sem_chave_repetida(pares: list[tuple[str, object]]) -> dict:
    obj: dict = {}
    for k, v in pares:
        if k in obj:
            raise ValueError(f"chave repetida no JSON: {limpo(k, 40)!r}")
        obj[k] = v
    return obj


def le_json(texto_json: str) -> object:
    """JSON do mural ou da ata. Chave repetida é recusada: com ela, quem lê o arquivo de olho veria um
    resultado e o programa conferiria outro (o Python fica com a última)."""
    return json.loads(texto_json, object_pairs_hook=_sem_chave_repetida)


def carrega(caminho: str, oque: str) -> dict:
    try:
        dados = le_json(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as e:
        raise SystemExit(pinta(f"✗ não consegui ler {oque} ({limpo(caminho)}): {limpo(e)}", "31;1")) from e
    if not isinstance(dados, dict):
        raise SystemExit(pinta(f"✗ {oque} ({limpo(caminho)}) não é um objeto JSON", "31;1"))
    return dados


def main() -> int:
    ap = argparse.ArgumentParser(description="Confere sozinho o mural da Urna do Garoto.")
    ap.add_argument("mural", help="arquivo JSON do mural")
    ap.add_argument("--ata", help="arquivo JSON com o que estava colado nas portas (elo final e contas da mesa)")
    ap.add_argument("--ata-parcial", action="store_true", help="a ata traz só as seções que VOCÊ fotografou")
    ap.add_argument("--contexto", help="o contexto da eleição publicado ANTES da votação (amarra o mural)")
    ap.add_argument("--paranoico", action="store_true", help="refaz o grupo a partir da semente (~20-30 s)")
    ap.add_argument("--recibo", help="o código do seu recibo (32 dígitos, ou o QR code inteiro)")
    ap.add_argument("--ficha", help="com --recibo: a ficha que você sorteou na mesa (16 dígitos)")
    ap.add_argument("--desafiei", action="store_true", help="com --recibo: eu desafiei essa cédula")
    ap.add_argument("--recibos", help="arquivo com um recibo por linha (coleta pública): acha recibo repetido")
    args = ap.parse_args()
    mural = carrega(args.mural, "o mural")
    ata = carrega(args.ata, "a ata") if args.ata else None
    if args.contexto and mural.get("contexto") != so_digitos(args.contexto):
        print(
            pinta("✗ o contexto do mural não é o que foi publicado antes da eleição. NÃO confie neste mural.", "31;1")
        )
        return 1
    v = Verificador(mural, ata=ata, paranoico=args.paranoico, ata_parcial=args.ata_parcial)
    if args.recibo or args.recibos:
        # recibo só vale contra um mural que confere: senão, um mural forjado "acharia" qualquer recibo
        print("conferindo o mural inteiro antes de procurar o recibo…")
        v.saida = lambda _: None
        problemas = v.roda()
        if problemas:
            print(pinta(f"✗ o mural não confere ({limpo(problemas[0])}). Não adianta procurar recibo nele.", "31;1"))
            return 1
        saida = 0
        if args.recibos:
            try:
                lista = [linha.strip() for linha in Path(args.recibos).read_text(encoding="utf-8").splitlines()]
            except (OSError, ValueError) as e:
                raise SystemExit(pinta(f"✗ não consegui ler os recibos: {limpo(e)}", "31;1")) from e
            lista = [r for r in lista if r]
            repetidos = recibos_repetidos(lista)
            fora = [r for r in lista if not procura_recibo(mural, r)]
            for r in repetidos:
                print(
                    pinta(
                        f"✗ o recibo {limpo(r)} está na mão de mais de um eleitor: clash, a urna trocou um voto", "31;1"
                    )
                )
            for r in fora[:10]:
                print(pinta(f"✗ o recibo {limpo(r, 80)} não está no mural", "31;1"))
            if not repetidos and not fora:
                print(pinta(f"✓ {qtd(len(lista), 'recibo')}: todos no mural, nenhum repetido", "32"))
            saida = 1 if repetidos or fora else 0
        if args.recibo:
            ok, mensagem = confere_recibo(mural, args.recibo, args.desafiei, args.ficha)
            print(pinta(("✓ " if ok else "✗ ") + limpo(mensagem, 600), "32" if ok else "31;1"))
            saida = saida or (0 if ok else 1)
        if ata is None and saida == 0:
            print(pinta("⚠ conferi o mural sem a ata das portas: a tua cédula está lá, mas o comparecimento", "33"))
            print(pinta("  e o elo final não foram amarrados. Roda de novo com --ata ata.json.", "33"))
        return saida
    print(pinta("Verificador da Urna do Garoto;  ·  não confia: confere", "1"))
    man = mural.get("manifesto")
    nome = limpo(man.get("eleicao", "?"), 120) if isinstance(man, dict) else "?"
    print(f"mural: {limpo(args.mural, 120)} · {nome}")
    problemas = v.roda()
    if problemas:
        print(pinta(f"\n✗ {qtd(len(problemas), 'problema')}. NÃO confie neste resultado.", "31;1"))
        return 1
    if ata is None:
        print(pinta("\n⚠ a matemática confere, mas SEM a ata das portas: cédula enfiada com o comparecimento", "33;1"))
        print(pinta("  reescrito dentro do mural passaria. Roda de novo com --ata ata.json.", "33;1"))
        return 2
    if v.sem_porta:
        faltam = qtd(len(v.sem_porta), "seção", "seções")
        print(
            pinta(f"\n⚠ a matemática confere e bate com as portas que você trouxe; falta a foto de {faltam}.", "33;1")
        )
        return 2
    print(pinta("\n✓ a matemática confere e bate com a ata que você passou.", "32;1"))
    print("  A ata só vale como prova se veio das fotos das portas, e não do mesmo lugar que o mural.")
    if not args.contexto:
        print("  Pra amarrar a eleição inteira, passa também --contexto com o valor publicado antes da votação.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
