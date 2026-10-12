"""
Os guardiões da chave da Urna do Garoto;  —  ninguém sozinho abre um voto. Nem eu.
por Garoto do Programa;  (github.com/garotodoprograma404/urna-do-garoto)

A chave que abre a soma dos votos nunca existe inteira em lugar nenhum. Ela nasce dividida entre
n guardiões (universidade, imprensa, fiscais dos partidos…) e só funciona com k deles juntos.
k - 1 guardiões mancomunados não conseguem nada. E se um guardião sumir (ou perder o pen drive),
os outros k ainda abrem a apuração.

A cerimônia (DKG de Pedersen 1991, com o segredo dividido e verificável de Feldman 1987):
  1. cada guardião i sorteia um polinômio secreto f_i de grau k-1 e publica g elevado a cada coeficiente
     (os "compromissos"), com uma prova de Schnorr de que conhece cada coeficiente. É o ataque da
     "chave pirata" (rogue key): escolher a parte DEPOIS de ver a dos outros, em função delas. As fatias
     conferidas no passo 3 já barram isso dentro da cerimônia; a prova deixa QUALQUER UM conferir de fora,
     só com o mural. Sobra um viés pequeno (Gennaro, Jarecki, Krawczyk e Rabin, 1999): quem publica por
     último ainda pode testar várias partes até a chave final ter uma propriedade que ele quer;
  2. pra cada colega j, o guardião i entrega a fatia f_i(j) (na vida real, cifrada: só o j abre);
  3. o j confere a fatia contra os compromissos públicos: g^f_i(j) = Π C_it^(j^t). Fatia falsa é pega na hora;
  4. o segredo do guardião j é s_j = Σ_i f_i(j). A chave da eleição é K = Π C_i0 = g^(Σ_i f_i(0)).

Na apuração, cada guardião presente entrega alfa^s_j + uma prova de Chaum-Pedersen de que usou o
segredo certo. Com k fatias, a interpolação de Lagrange no expoente reconstrói alfa^s sem reconstruir s.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass

import cripto as C
from grupo import GRUPO

P, Q, G = GRUPO.p, GRUPO.q, GRUPO.g


class ErroCerimonia(Exception):
    pass


@dataclass(frozen=True)
class Compromissos:
    """O que o guardião publica no mural: g^(cada coeficiente) + prova de que conhece cada um."""

    numero: int
    nome: str
    coeficientes: tuple[int, ...]
    provas: tuple[C.ProvaConhecimento, ...]


def contexto_do_coeficiente(pre_contexto: str, numero: int, t: int) -> tuple:
    return (pre_contexto, "coeficiente", numero, t)


def confere_compromissos(c: Compromissos, pre_contexto: str, quorum: int) -> bool:
    if len(c.coeficientes) != quorum or len(c.provas) != quorum:
        return False
    return all(
        C.confere_conhecimento(prova, contexto_do_coeficiente(pre_contexto, c.numero, t), coef)
        for t, (coef, prova) in enumerate(zip(c.coeficientes, c.provas, strict=True))
    )


def no_expoente(coeficientes: tuple[int, ...], x: int) -> int:
    """g^f(x) calculado só com os compromissos públicos: Π C_t^(x^t)."""
    return math.prod(pow(coef, pow(x, t, Q), P) for t, coef in enumerate(coeficientes)) % P


def chave_de_verificacao(todos: list[Compromissos], numero: int) -> int:
    """g^s_j do guardião j. Qualquer um calcula, só com o que está no mural."""
    return math.prod(no_expoente(c.coeficientes, numero) for c in todos) % P


def chave_da_eleicao(todos: list[Compromissos]) -> int:
    return math.prod(c.coeficientes[0] for c in todos) % P


def lagrange(numero: int, presentes: list[int]) -> int:
    """Peso do guardião `numero` pra reconstruir f(0) a partir dos presentes (mod q)."""
    w = 1
    for j in presentes:
        if j != numero:
            w = w * j * pow(j - numero, -1, Q) % Q
    return w


@dataclass(frozen=True)
class FatiaDecifrada:
    numero: int
    m: int  # alfa^s_j
    prova: C.ProvaIgualdade


def contexto_da_fatia(contexto: str, opcao: int) -> tuple:
    return (contexto, "apuracao", opcao)


def confere_fatia(fatia: FatiaDecifrada, contexto: str, opcao: int, verificacao: int, total: C.Cifra) -> bool:
    return C.confere_igualdade(
        fatia.prova, "decifra", contexto_da_fatia(contexto, opcao), G, verificacao, total.alfa, fatia.m
    )


def combina(fatias: list[FatiaDecifrada]) -> int:
    """Junta k fatias conferidas: Π (alfa^s_j)^(peso_j) = alfa^s."""
    presentes = [f.numero for f in fatias]
    if len(set(presentes)) != len(presentes):
        raise ValueError("guardião repetido")
    return math.prod(pow(f.m, lagrange(f.numero, presentes), P) for f in fatias) % P


class Guardiao:
    def __init__(self, numero: int, nome: str, quorum: int, pre_contexto: str) -> None:
        if numero < 1:
            raise ValueError("guardião começa no 1 (f(0) é o segredo, ninguém pode ser o 0)")
        self.numero, self.nome = numero, nome
        self._coeficientes = [GRUPO.aleatorio() for _ in range(quorum)]
        publicos = tuple(C.potencia(G, a) for a in self._coeficientes)
        provas = tuple(
            C.prova_conhecimento(contexto_do_coeficiente(pre_contexto, numero, t), publicos[t], a)
            for t, a in enumerate(self._coeficientes)
        )
        self.compromissos = Compromissos(numero, nome, publicos, provas)
        self._fatias: dict[int, int] = {}
        self._segredo: int | None = None
        self._ata: dict | None = None  # a ata que OS FISCAIS DELE trouxeram, nunca a de quem pede a apuração
        self._abriu: tuple[str, list[FatiaDecifrada]] | None = None  # a ÚNICA soma que ele abre na vida

    def recebe_ata(self, ata: dict) -> None:
        """A ata das portas que os fiscais DESTE guardião fotografaram e entregaram a ele, antes de qualquer
        pedido. Na vida real cada guardião monta (ou confere, seção por seção) a dele com as fotos."""
        self._ata = copy.deepcopy(ata)

    def fatia_para(self, numero: int) -> int:
        """f(numero) pelo método de Horner, mod q."""
        resultado = 0
        for a in reversed(self._coeficientes):
            resultado = (resultado * numero + a) % Q
        return resultado

    def recebe_fatia(self, de: Compromissos, fatia: int) -> bool:
        """Confere a fatia contra os compromissos públicos de quem mandou. Falsa → recusa."""
        if len(de.coeficientes) != len(self._coeficientes) or not all(C.pertence(x) for x in de.coeficientes):
            return False  # a cerimônia já conferiu os compromissos; aqui é defesa em profundidade
        if not GRUPO.expoente(fatia) or C.potencia(G, fatia) != no_expoente(de.coeficientes, self.numero):
            return False
        self._fatias[de.numero] = fatia
        return True

    def fecha(self, n: int) -> None:
        if sorted(self._fatias) != list(range(1, n + 1)):
            raise ErroCerimonia(f"{self.nome} não recebeu as {n} fatias")
        self._segredo = sum(self._fatias.values()) % Q
        self._fatias.clear()  # em Python isso não zera a memória; na urna de verdade, o chip zera

    def abre_apuracao(self, mural: dict) -> list[FatiaDecifrada]:
        """A apuração, do lado do guardião. Ele não confia em quem pediu:
        1. confere o mural sozinho (passos 1 a 5 do verificador) contra a ata que OS FISCAIS DELE trouxeram.
           A ata não vem junto com o pedido: quem monta um mural sob medida monta uma ata que bate com ele;
        2. confere que a cerimônia do mural é a dele (os compromissos dele estão lá, iguaizinhos);
        3. calcula a soma ele mesmo, multiplicando as cédulas depositadas;
        4. abre a parte dele de UMA soma na vida. Pedir a MESMA soma de novo devolve as mesmas fatias (não
           vaza nada novo, e uma apuração que falhou por culpa de outro guardião pode ser refeita). Qualquer
           OUTRA soma (sem uma urna, só com uma cédula…) é tentativa de descobrir voto por diferença: recusa."""
        import verificador as V  # aqui dentro porque o verificador importa este arquivo

        if self._ata is None:
            raise ErroCerimonia(f"{self.nome}: não recebi a ata das portas dos meus fiscais, não abro")
        problemas = V.confere_para_apuracao(mural, self._ata)
        if problemas:
            raise ErroCerimonia(f"{self.nome}: o mural não confere com a ata dos meus fiscais ({problemas[0]})")
        minha = [c for c in mural["cerimonia"] if c["numero"] == self.numero]
        if len(minha) != 1 or tuple(V.num(x) for x in minha[0]["coeficientes"]) != self.compromissos.coeficientes:
            raise ErroCerimonia(f"{self.nome}: esse mural não é da minha cerimônia")
        somas = V.totais(mural)
        digital = C.hash_hex("soma-aberta", mural["contexto"], [(t.alfa, t.beta) for t in somas])
        if self._abriu is not None:
            if self._abriu[0] != digital:
                raise ErroCerimonia(f"{self.nome} já abriu OUTRA soma desta eleição e não abre mais nenhuma")
            return list(self._abriu[1])
        fatias = [self._decifra(mural["contexto"], i, total) for i, total in enumerate(somas)]
        self._abriu = (digital, fatias)
        return list(fatias)

    def _decifra(self, contexto: str, opcao: int, total: C.Cifra) -> FatiaDecifrada:
        """A conta crua: alfa^s + prova de que usou o segredo certo. Sem regra nenhuma: só a apuração chama."""
        if self._segredo is None:
            raise ErroCerimonia("a cerimônia não terminou")
        if not total.valida():  # fora do grupo, a resposta vazaria pedaços do segredo
            raise ErroCerimonia(f"{self.nome}: número fora do grupo, não abro")
        verificacao = C.potencia(G, self._segredo)
        m = pow(total.alfa, self._segredo, P)
        prova = C.prova_igualdade(
            "decifra", contexto_da_fatia(contexto, opcao), G, verificacao, total.alfa, m, self._segredo
        )
        return FatiaDecifrada(self.numero, m, prova)


def cerimonia_das_chaves(nomes: list[str], quorum: int, pre_contexto: str) -> tuple[list[Guardiao], int]:
    """Roda a cerimônia inteira. Devolve os guardiões (cada um com sua parte secreta) e a chave pública."""
    if not 2 <= quorum <= len(nomes):
        raise ValueError("o quórum tem que ser de 2 até o número de guardiões (quórum 1 = cada um abre tudo)")
    guardioes = [Guardiao(i + 1, nome, quorum, pre_contexto) for i, nome in enumerate(nomes)]
    return guardioes, cerimonia(guardioes, quorum, pre_contexto)


def cerimonia(guardioes: list[Guardiao], quorum: int, pre_contexto: str) -> int:
    """A cerimônia com guardiões já criados (é por aqui que os ataques entram com um guardião malandro)."""
    n = len(guardioes)
    if not 2 <= quorum <= n:
        raise ValueError("o quórum tem que ser de 2 até o número de guardiões (quórum 1 = cada um abre tudo)")
    if [g.numero for g in guardioes] != list(range(1, n + 1)):
        raise ErroCerimonia("os guardiões têm que ser numerados de 1 a n")
    publicados = [g.compromissos for g in guardioes]
    for c in publicados:  # 1. todo mundo confere a prova de todo mundo (é público)
        if not confere_compromissos(c, pre_contexto, quorum):
            raise ErroCerimonia(f"{c.nome}: prova de conhecimento inválida (chave pirata?)")
    for de in guardioes:  # 2. cada um entrega uma fatia pra cada um, e quem recebe confere
        for para in guardioes:
            if not para.recebe_fatia(de.compromissos, de.fatia_para(para.numero)):
                raise ErroCerimonia(f"{para.nome} recebeu fatia falsa de {de.nome}")
    for g in guardioes:
        g.fecha(n)
    chave = chave_da_eleicao(publicados)
    if not C.pertence(chave) or chave == 1:
        raise ErroCerimonia("chave da eleição inválida")
    return chave
