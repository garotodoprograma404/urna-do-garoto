"""
A criptografia da Urna do Garoto;  —  cifrar, somar sem abrir e provar sem revelar.
por Garoto do Programa;  (github.com/garotodoprograma404/urna-do-garoto)

Nada aqui foi inventado por mim. São as peças clássicas, publicadas e atacadas há décadas:
  - ElGamal (1985), na versão exponencial de Cramer, Gennaro e Schoenmakers (1997): cifra o voto e
    deixa SOMAR votos cifrados sem abrir nenhum;
  - Chaum-Pedersen (1992): prova que dois números têm o mesmo expoente secreto, sem mostrar qual;
  - prova disjuntiva de Cramer-Damgård-Schoenmakers (1994): "aqui dentro tem 0 OU 1", sem dizer qual;
  - Schnorr (1989): "eu sei o segredo desta chave", sem mostrar o segredo;
  - Fiat-Shamir FORTE: o desafio de cada prova é o hash de TUDO (contexto, enunciado e compromissos).
    A versão fraca, que deixa coisa de fora do hash, já derrubou provas do Helios em 2012
    (Bernhard, Pereira e Warinschi, "How not to prove yourself").

Regra de ouro: todo número que chega de fora passa por pertence() antes de qualquer conta.
"""

from __future__ import annotations

import functools
import hashlib
from dataclasses import dataclass

from grupo import GRUPO

P, Q, G = GRUPO.p, GRUPO.q, GRUPO.g
G_INVERSO = pow(G, -1, P)
DOMINIO = "urna-do-garoto/v2"


@functools.lru_cache(maxsize=4096)
def _pertence(x: int) -> bool:
    return GRUPO.pertence(x)


def pertence(x: object) -> bool:
    """GRUPO.pertence com memória: a chave da eleição é conferida uma vez, não mil."""
    return isinstance(x, int) and not isinstance(x, bool) and _pertence(x)


# ---------------------------------------------------------------- potência rápida pra base fixa
class BaseFixa:
    """Tabela pré-calculada pra uma base que se repete (g e a chave da eleição).
    base^e vira no máximo 32 multiplicações em vez de ~300. Mesmo resultado, ~10x mais rápido.
    Tabela indexada pelos bits do expoente vaza por cache (Percival 2005): é o "Python vaza tempo" do README."""

    def __init__(self, base: int) -> None:
        self.tabela: list[list[int]] = []
        atual = base
        for _ in range((Q.bit_length() + 7) // 8):
            linha = [1] * 256
            for j in range(1, 256):
                linha[j] = linha[j - 1] * atual % P
            self.tabela.append(linha)
            atual = linha[255] * atual % P  # atual^256: próxima janela de 8 bits
        self.base = base

    def potencia(self, e: int) -> int:
        e %= Q  # vale porque a base tem ordem q
        resultado, janela = 1, 0
        while e:
            if e & 255:
                resultado = resultado * self.tabela[janela][e & 255] % P
            e, janela = e >> 8, janela + 1
        return resultado


_FIXAS: dict[int, BaseFixa] = {}


def fixa(base: int) -> None:
    """Avisa que essa base vai se repetir muito. A tabela reduz o expoente mod q: só vale pra base do grupo."""
    if not pertence(base):
        raise ValueError("fixa() só aceita número do grupo (a tabela reduz o expoente mod q)")
    if base not in _FIXAS:
        _FIXAS[base] = BaseFixa(base)


def potencia(base: int, e: int) -> int:
    tabela = _FIXAS.get(base)
    return tabela.potencia(e) if tabela else pow(base, e, P)


# ---------------------------------------------------------------- hash
def codifica(x: object) -> bytes:
    """Codificação canônica: cada valor vira bytes de um jeito só, e duas listas diferentes nunca
    viram os mesmos bytes (tipo + tamanho na frente de tudo). Sem isso, "ab"+"c" e "a"+"bc" colidem."""
    if isinstance(x, bool):
        raise TypeError("bool não entra no hash (True == 1 em Python, ia dar ambiguidade)")
    if isinstance(x, int):
        if x < 0:
            raise ValueError("só inteiros não negativos")
        corpo, tipo = x.to_bytes(max(1, (x.bit_length() + 7) // 8), "big"), b"I"
    elif isinstance(x, str):
        corpo, tipo = x.encode(), b"S"
    elif isinstance(x, bytes):
        corpo, tipo = x, b"B"
    elif isinstance(x, (list, tuple)):
        return b"L" + len(x).to_bytes(4, "big") + b"".join(codifica(item) for item in x)
    else:
        raise TypeError(f"não sei codificar {type(x).__name__}")
    return tipo + len(corpo).to_bytes(4, "big") + corpo


def hash_hex(rotulo: str, *partes: object) -> str:
    """SHA-256 com separação de domínio: o rótulo diz PRA QUE serve o hash."""
    return hashlib.sha256(codifica((DOMINIO, rotulo, partes))).hexdigest()


def hash_q(rotulo: str, *partes: object) -> int:
    """Hash que vira número entre 0 e q-1 (SHA-512 reduzido mod q: 512 bits → viés desprezível)."""
    return int.from_bytes(hashlib.sha512(codifica((DOMINIO, rotulo, partes))).digest(), "big") % Q


# ---------------------------------------------------------------- ElGamal exponencial
@dataclass(frozen=True)
class Cifra:
    """Um número cifrado: alfa = g^r, beta = g^m · K^r (m = o voto, r = segredo de uso único)."""

    alfa: int
    beta: int

    def __mul__(self, outra: Cifra) -> Cifra:
        # A mágica: multiplicar cifras SOMA os votos. g^m1·g^m2 = g^(m1+m2). Ninguém abre nada.
        return Cifra(self.alfa * outra.alfa % P, self.beta * outra.beta % P)

    def valida(self) -> bool:
        return pertence(self.alfa) and pertence(self.beta)


CIFRA_ZERO = Cifra(1, 1)  # o "zero" da soma de cifras


def cifra(chave: int, m: int, r: int) -> Cifra:
    return Cifra(potencia(G, r), potencia(G, m) * potencia(chave, r) % P)


def log_pequeno(g_m: int, maximo: int) -> int | None:
    """Descobre m a partir de g^m, testando 0, 1, 2… até `maximo` (o voto é contagem, então é pequeno)."""
    atual = 1
    for m in range(maximo + 1):
        if atual == g_m:
            return m
        atual = atual * G % P
    return None


fixa(G)


# ---------------------------------------------------------------- Schnorr: "eu sei o segredo"
@dataclass(frozen=True)
class ProvaConhecimento:
    c: int
    v: int


def prova_conhecimento(contexto: object, publico: int, segredo: int) -> ProvaConhecimento:
    u = GRUPO.aleatorio()
    c = hash_q("conhecimento", contexto, publico, potencia(G, u))
    return ProvaConhecimento(c, (u + c * segredo) % Q)


def confere_conhecimento(prova: ProvaConhecimento, contexto: object, publico: int) -> bool:
    if not (pertence(publico) and GRUPO.expoente(prova.c) and GRUPO.expoente(prova.v)):
        return False
    a = potencia(G, prova.v) * pow(publico, Q - prova.c, P) % P  # g^v · publico^(-c)
    return prova.c == hash_q("conhecimento", contexto, publico, a)


# ---------------------------------------------------------------- Chaum-Pedersen: "mesmo segredo nos dois"
@dataclass(frozen=True)
class ProvaIgualdade:
    """Prova que log_g1(h1) = log_g2(h2) sem mostrar o log."""

    c: int
    v: int


def prova_igualdade(rotulo: str, contexto: object, g1: int, h1: int, g2: int, h2: int, x: int) -> ProvaIgualdade:
    u = GRUPO.aleatorio()
    c = hash_q(rotulo, contexto, g1, h1, g2, h2, potencia(g1, u), potencia(g2, u))
    return ProvaIgualdade(c, (u + c * x) % Q)


def confere_igualdade(prova: ProvaIgualdade, rotulo: str, contexto: object, g1: int, h1: int, g2: int, h2: int) -> bool:
    if not all(pertence(x) for x in (g1, h1, g2, h2)):
        return False
    if not (GRUPO.expoente(prova.c) and GRUPO.expoente(prova.v)):
        return False
    a = potencia(g1, prova.v) * pow(h1, Q - prova.c, P) % P
    b = potencia(g2, prova.v) * pow(h2, Q - prova.c, P) % P
    return prova.c == hash_q(rotulo, contexto, g1, h1, g2, h2, a, b)


# ---------------------------------------------------------------- disjuntiva: "aqui tem 0 OU 1"
@dataclass(frozen=True)
class ProvaZeroOuUm:
    """Prova que a cifra esconde 0 ou 1, sem dizer qual. O ramo verdadeiro é provado de verdade;
    o outro é simulado. Como c0 + c1 tem que dar o hash, só dá pra simular UM ramo: o outro é real."""

    c0: int
    c1: int
    v0: int
    v1: int


def _alvos(cf: Cifra) -> tuple[int, int]:
    return cf.beta, cf.beta * G_INVERSO % P  # beta/g^0 e beta/g^1: um deles é K^r


def prova_zero_ou_um(contexto: object, chave: int, cf: Cifra, m: int, r: int) -> ProvaZeroOuUm:
    if m not in (0, 1):
        raise ValueError("essa prova só existe pra 0 ou 1. É esse o ponto.")
    alvos, falso = _alvos(cf), 1 - m
    c_falso, v_falso = GRUPO.aleatorio(), GRUPO.aleatorio()
    a, b = [0, 0], [0, 0]
    a[falso] = potencia(G, v_falso) * pow(cf.alfa, Q - c_falso, P) % P
    b[falso] = potencia(chave, v_falso) * pow(alvos[falso], Q - c_falso, P) % P
    u = GRUPO.aleatorio()
    a[m], b[m] = potencia(G, u), potencia(chave, u)
    c = hash_q("zero-ou-um", contexto, chave, cf.alfa, cf.beta, a[0], b[0], a[1], b[1])
    c_real = (c - c_falso) % Q
    v_real = (u + c_real * r) % Q
    cs, vs = [0, 0], [0, 0]
    cs[m], vs[m], cs[falso], vs[falso] = c_real, v_real, c_falso, v_falso
    return ProvaZeroOuUm(cs[0], cs[1], vs[0], vs[1])


def confere_zero_ou_um(prova: ProvaZeroOuUm, contexto: object, chave: int, cf: Cifra) -> bool:
    if not (pertence(chave) and cf.valida()) or cf.alfa == 1:  # alfa = 1 é r = 0: o voto ia aparecer em claro
        return False
    if not all(GRUPO.expoente(x) for x in (prova.c0, prova.c1, prova.v0, prova.v1)):
        return False
    a, b = [], []
    for alvo, c, v in zip(_alvos(cf), (prova.c0, prova.c1), (prova.v0, prova.v1), strict=True):
        a.append(potencia(G, v) * pow(cf.alfa, Q - c, P) % P)
        b.append(potencia(chave, v) * pow(alvo, Q - c, P) % P)
    c = hash_q("zero-ou-um", contexto, chave, cf.alfa, cf.beta, a[0], b[0], a[1], b[1])
    return (prova.c0 + prova.c1) % Q == c


# ---------------------------------------------------------------- constante: "a soma dá exatamente L"
def prova_soma(contexto: object, chave: int, total: Cifra, valor: int, r_total: int) -> ProvaIgualdade:
    """Prova que a soma das cifras de uma cédula esconde exatamente `valor` (na urna: 1 voto por cédula)."""
    resto = total.beta * pow(G_INVERSO, valor, P) % P  # beta / g^valor = K^r_total
    return prova_igualdade("soma", contexto, G, total.alfa, chave, resto, r_total)


def confere_soma(prova: ProvaIgualdade, contexto: object, chave: int, total: Cifra, valor: int) -> bool:
    if not total.valida():
        return False
    resto = total.beta * pow(G_INVERSO, valor, P) % P
    return confere_igualdade(prova, "soma", contexto, G, total.alfa, chave, resto)
