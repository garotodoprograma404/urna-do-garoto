#!/usr/bin/env python3
"""
Ataques à Urna do Garoto;  —  o vilão tenta todos os golpes. Duvida? Roda.
por Garoto do Programa;  (github.com/garotodoprograma404/urna-do-garoto)

Cada ataque mexe numa cópia da eleição (ou entra com uma peça malandra: urna, guardião) e alguém
tem que pegar: o verificador, a ata colada na porta, os guardiões, o celular de quem desafia ou o
eleitor conferindo o recibo (com a ficha) em casa.
Os ataques mais fortes são de quem está DENTRO: a própria urna trapaceando, refazendo a corrente
inteira, reescrevendo o comparecimento do mural e chamando guardiões cúmplices pra abrir a soma.
Os golpes 01 a 17 são os do vídeo. Os 18 a 22 vieram da auditoria antes de publicar (README).

    python3 ataques.py          # todos os golpes (~2-3 min)

Achou um golpe que passa? Abre uma issue no GitHub. É exatamente pra isso que o código é aberto.
"""

from __future__ import annotations

import copy
import json
import random
import sys
from dataclasses import dataclass, field

import cripto as C
import guardioes as GU
import urna as U
import verificador as V
from eleicao import GUARDIOES, OPCOES, PESOS, QUORUM
from grupo import GRUPO
from verificador import pinta

P, Q, G = GRUPO.p, GRUPO.q, GRUPO.g
URNAS = ("secao-001", "secao-002")
ESCOLHAS = {
    "secao-001": ("Pastel", "Esfiha", "Pão de queijo", "Pastel", "BRANCO", "Esfiha",
                  "Pastel", "Pão de queijo", "Pastel", "Esfiha", "Pão de queijo", "Pastel"),
    "secao-002": ("Esfiha", "Pastel", "Pão de queijo"),
}  # fmt: skip
DESAFIAM = {2: "Esfiha", 7: "Pastel"}  # o 3º e o 8º eleitor da seção 1 desafiam (com uma opção qualquer)


@dataclass
class Cenario:
    mural: dict
    ata: dict
    guardioes: list[GU.Guardiao]
    manifesto: U.Manifesto
    chave: int
    recibos: list[tuple[str, str, str]] = field(default_factory=list)  # (código, o que confirmou, ficha)


def vota(urna: U.Urna, escolhas: tuple[str, ...], desafiam: dict[int, str]) -> list[tuple[str, str, str]]:
    """Uma seção: cada eleitor sorteia uma ficha, alguns desafiam uma vez, e todos confirmam."""
    recibos = []
    for i, escolha in enumerate(escolhas):
        ficha = U.nova_ficha()
        urna.libera(ficha)
        if i in desafiam:
            urna.prepara(desafiam[i])
            urna.desafia()
        urna.prepara(escolha)
        recibos.append((urna.confirma(), escolha, ficha))
    return recibos


def eleicao(classe_urna: type[U.Urna] = U.Urna, apura: bool = True) -> Cenario:
    """Duas seções pequenas, do começo à apuração. `classe_urna` deixa trocar a urna por uma malandra."""
    manifesto = U.Manifesto("Ataques à Urna do Garoto", OPCOES, GUARDIOES, QUORUM, URNAS)
    guardioes, chave = GU.cerimonia_das_chaves(list(GUARDIOES), QUORUM, U.pre_contexto(manifesto))
    mural = U.novo_mural(manifesto, [g.compromissos for g in guardioes], chave)
    ata = {"versao": U.VERSAO, "contexto": mural["contexto"], "urnas": {}}
    recibos = []
    for ident in URNAS:
        urna = classe_urna(ident, manifesto, mural["contexto"], chave)
        recibos += vota(urna, ESCOLHAS[ident], DESAFIAM if ident == URNAS[0] else {})
        fecho = urna.fecha()
        U.publica_urna(mural, ident, urna.registros, fecho, comparecimento=len(ESCOLHAS[ident]))
        ata["urnas"][ident] = U.ata_da_secao(fecho, len(ESCOLHAS[ident]))
    for g in guardioes:
        g.recebe_ata(ata)  # a ata dos fiscais de cada guardião
    if apura:
        U.apura(mural, guardioes[:QUORUM])
        mural["lacre"] = U.lacre(mural)
    return Cenario(mural, ata, guardioes, manifesto, chave, recibos)


class Cumplice:
    """Guardião comprado: abre o que o vilão mandar, sem conferir nada e quantas vezes ele quiser."""

    def __init__(self, guardiao: GU.Guardiao) -> None:
        self.guardiao, self.numero, self.nome = guardiao, guardiao.numero, guardiao.nome

    def abre_apuracao(self, mural: dict) -> list[GU.FatiaDecifrada]:
        return [self.guardiao._decifra(mural["contexto"], i, t) for i, t in enumerate(V.totais(mural))]


def cumplices(c: Cenario) -> list[Cumplice]:
    return [Cumplice(g) for g in c.guardioes[:QUORUM]]


def frescos(c: Cenario, quantos: int = QUORUM) -> list[GU.Guardiao]:
    """Os guardiões honestos de novo, como se ainda não tivessem aberto a apuração desta eleição
    (cada um continua com a ata que os fiscais dele trouxeram)."""
    copias = [copy.copy(g) for g in c.guardioes[:quantos]]
    for g in copias:
        g._abriu = None
    return copias


def refaz(c: Cenario, mural: dict, reescreve_comparecimento: bool = False) -> dict:
    """O ataque de quem está DENTRO: refaz códigos, elos e fechamento de cada urna, reescreve (se quiser)
    o comparecimento do mural, chama guardiões cúmplices pra abrir a soma do jeito que ficou e lacra de novo.
    O que ele NÃO alcança: a ata (elo final colado na porta + contas assinadas pela mesa)."""
    ctx = mural["contexto"]
    for urna, fecho in mural["urnas"].items():
        elo, depositadas, sem_voto = U.codigo_inicial(ctx, urna), 0, 0
        for reg in (r for r in mural["cedulas"] if r["urna"] == urna):
            reg["anterior"] = elo
            if reg["estado"] == U.SEM_VOTO:
                reg["codigo"] = U.codigo_sem_voto(ctx, elo, reg["id"], reg["ficha"])
            else:
                reg["codigo"] = U.codigo_da_cedula(ctx, elo, reg["ficha"], U.cedula_do_registro(reg))
            elo = U.elo(ctx, reg["codigo"], reg["estado"])
            depositadas += reg["estado"] == U.DEPOSITADA
            sem_voto += reg["estado"] == U.SEM_VOTO
        fecho.update(
            depositadas=depositadas,
            sem_voto=sem_voto,
            elo_final=elo,
            fechamento=U.fechamento(ctx, urna, elo, depositadas, sem_voto),
        )
        fecho.setdefault("devolvidas", 0)
        if reescreve_comparecimento:
            fecho.update(comparecimento=depositadas + sem_voto, devolvidas=sem_voto)
    U.apura(mural, cumplices(c))
    mural["lacre"] = U.lacre(mural)
    return mural


def depositada(mural: dict, n: int, urna: str = URNAS[0]) -> dict:
    """A n-ésima cédula depositada de uma urna."""
    return [r for r in mural["cedulas"] if r["urna"] == urna and r["estado"] == U.DEPOSITADA][n]


def cedula_nova(c: Cenario, mural: dict, urna: str, escolha: str) -> dict:
    """Uma cédula perfeita (com prova válida), feita por quem conhece o protocolo."""
    seq = sum(r["urna"] == urna for r in mural["cedulas"]) + 1
    ced, _ = U.monta_cedula(mural["contexto"], c.chave, len(OPCOES), OPCOES.index(escolha), f"{urna}/{seq:06d}")
    return U.registro(ced, urna, "", U.nova_ficha(), "", U.DEPOSITADA, None)


def desafio_na_cabine(urna: U.Urna, ficha: str, na_tela: str) -> str | None:
    """O celular de quem desafia: a cédula aberta tem que ser a do código impresso e ter o que estava na tela."""
    impresso = urna.prepara(na_tela)
    urna.desafia()
    return V.confere_desafio_na_cabine(urna.ctx, urna.chave, OPCOES, urna.registros[-1], impresso, na_tela, ficha)


# ---------------------------------------------------------------- mexendo no mural, de fora
def troca_voto(c: Cenario):
    m = copy.deepcopy(c.mural)
    reg = depositada(m, 4)
    alfa, beta = (int(x, 16) for x in reg["cifras"][0])
    reg["cifras"][0][1] = U.hx(beta * G % P)  # beta·g: +1 voto pro Pastel, sem saber a chave
    m["apuracao"]["totais"][0][1] = U.hx(int(m["apuracao"]["totais"][0][1], 16) * G % P)
    m["apuracao"]["resultado"]["Pastel"] += 1
    m["lacre"] = U.lacre(m)
    return f"somei +1 voto pro Pastel na cédula {reg['id']} e ajustei soma, resultado e lacre", m


def apaga(c: Cenario):
    m = copy.deepcopy(c.mural)
    reg = depositada(m, 5)
    m["cedulas"].remove(reg)
    m["lacre"] = U.lacre(m)
    return f"apaguei a cédula {reg['id']} do mural", m


# ---------------------------------------------------------------- a urna malandra, de dentro
def turbinada(c: Cenario):
    m = copy.deepcopy(c.mural)
    reg = depositada(m, 3)
    novo = C.cifra(c.chave, 5, GRUPO.aleatorio())
    reg["cifras"][2] = [U.hx(novo.alfa), U.hx(novo.beta)]  # 5 votos pra Esfiha numa cédula só
    return f"sou a urna: pus 5 votos pra Esfiha na cédula {reg['id']} e refiz a corrente inteira", refaz(c, m)


def voto_duplo(c: Cenario):
    m = copy.deepcopy(c.mural)
    reg = depositada(m, 6)
    ctx, rid = m["contexto"], reg["id"]
    votos = [1, 1, 0, 0]  # Pastel E Pão de queijo na mesma cédula
    rs = [GRUPO.aleatorio() for _ in votos]
    cifras = [C.cifra(c.chave, v, r) for v, r in zip(votos, rs, strict=True)]
    provas = [
        C.prova_zero_ou_um((ctx, rid, i), c.chave, cf, v, r)
        for i, (cf, v, r) in enumerate(zip(cifras, votos, rs, strict=True))
    ]
    total = cifras[0] * cifras[1] * cifras[2] * cifras[3]
    soma = C.prova_soma((ctx, rid), c.chave, total, 2, sum(rs) % Q)  # prova honesta… de que a soma é 2
    reg["cifras"] = [[U.hx(cf.alfa), U.hx(cf.beta)] for cf in cifras]
    reg["provas"] = [[U.hx(p.c0), U.hx(p.c1), U.hx(p.v0), U.hx(p.v1)] for p in provas]
    reg["prova_soma"] = [U.hx(soma.c), U.hx(soma.v)]
    return f"sou a urna: votei em Pastel E Pão de queijo na cédula {rid}, com provas 0-ou-1 válidas", refaz(c, m)


def repeticao(c: Cenario):
    m = copy.deepcopy(c.mural)
    alvo, copia = depositada(m, 1), depositada(m, 8)
    for campo in ("cifras", "provas", "prova_soma"):
        copia[campo] = copy.deepcopy(alvo[campo])
    feito = f"copiei a cédula cifrada {alvo['id']} por cima da {copia['id']} (pra descobrir o voto pela diferença)"
    return feito, refaz(c, m)


def enche_urna(c: Cenario):
    m = copy.deepcopy(c.mural)
    for _ in range(5):
        m["cedulas"].insert(m["cedulas"].index(depositada(m, -1)) + 1, cedula_nova(c, m, URNAS[0], "Esfiha"))
    feito = "sou a urna: enfiei 5 cédulas perfeitas pra Esfiha, refiz a corrente E reescrevi o comparecimento"
    return feito, refaz(c, m, reescreve_comparecimento=True)


def vira_desafiada(c: Cenario):
    m = copy.deepcopy(c.mural)
    reg = next(r for r in m["cedulas"] if r["estado"] == U.DESAFIADA)
    reg["estado"], reg["abertura"] = U.DEPOSITADA, None
    feito = f"transformei a cédula desafiada {reg['id']} em voto e reescrevi o comparecimento pra bater"
    return feito, refaz(c, m, reescreve_comparecimento=True)


class UrnaTrocaDepois(U.Urna):
    """Imprime o código da cédula honesta. No CONFIRMA, marca essa como DESAFIADA e deposita outra."""

    def confirma(self) -> str:
        _, codigo, escolha, _ = self._pendente
        if escolha != "Pastel":
            return super().confirma()
        self.desafia()  # a honesta vai pro mural como "desafiada"…
        self.prepara("Esfiha")
        super().confirma()  # …e a trocada é a que conta
        return codigo  # o eleitor sai com o código da honesta na mão


def troca_depois_do_botao(c: Cenario):
    falsa = eleicao(UrnaTrocaDepois)
    limpo = not V.verifica(falsa.mural, saida=lambda _: None, paralelo=False, ata=falsa.ata)
    pegos = []
    for i, (codigo, _, ficha) in enumerate(falsa.recibos):
        if i % 3 == 0:  # 1 em cada 3 eleitores confere o recibo em casa
            ok, mensagem = V.confere_recibo(falsa.mural, U.codigo_curto(codigo), ficha=U.ficha_impressa(ficha))
            if not ok:
                pegos.append(f"recibo {U.codigo_curto(codigo)[:24]}…: {mensagem}")
    feito = "sou a urna: no CONFIRMA, marco a cédula do eleitor como desafiada e deposito outra, trocada"
    if limpo:
        feito += " (o mural fica perfeito: o verificador diz OK)"
    return feito, pegos


class UrnaTrapaceira(U.Urna):
    """Troca voto de Pastel por Esfiha ANTES de cifrar, em silêncio. Por padrão troca TODOS: é o que vira a
    eleição. Mas não sabe quem vai desafiar, nem quem é fiscal."""

    def __init__(self, *args, chance: float = 1.0, sorteio: random.Random | None = None) -> None:
        super().__init__(*args)
        self.chance, self.sorteio = chance, sorteio or random.Random()
        self.contou, self._trocada = 0, False

    def prepara(self, escolha: str) -> str:
        self._trocada = escolha == "Pastel" and self.sorteio.random() < self.chance
        return super().prepara("Esfiha" if self._trocada else escolha)

    def confirma(self) -> str:
        self.contou += self._trocada
        return super().confirma()


def urna_trapaceira(
    c: Cenario,
    eleitores: int = 120,
    chance_desafio: float = 0.15,
    semente: int = 7,
    chance_troca: float = 1.0,
    fiscal_a_cada: int = 20,
):
    """Eleitores desafiam no máximo uma vez, com uma opção qualquer. A cada `fiscal_a_cada` eleitores, um
    fiscal (de cada partido, um de cada vez) pega ficha como qualquer um e desafia com o candidato DELE."""
    sorteio = random.Random(semente)
    urna = UrnaTrapaceira(
        URNAS[0], c.manifesto, c.mural["contexto"], c.chave, chance=chance_troca, sorteio=random.Random(semente + 1)
    )
    pegas, fiscais = [], 0
    for n in range(eleitores):
        if fiscal_a_cada and n % fiscal_a_cada == fiscal_a_cada // 2:
            ficha, partido = U.nova_ficha(), OPCOES[fiscais % len(OPCOES)]
            urna.libera(ficha)
            fiscais += 1
            motivo = desafio_na_cabine(urna, ficha, partido)
            if motivo:
                pegas.append(f"{urna.registros[-1]['id']} (fiscal do {partido}): {motivo}")
            urna.encerra_sem_voto()
        escolha = sorteio.choices(OPCOES, PESOS)[0]
        ficha = U.nova_ficha()
        urna.libera(ficha)
        if sorteio.random() < chance_desafio:  # desafio com uma opção qualquer, uma vez
            na_tela = sorteio.choice(OPCOES)
            motivo = desafio_na_cabine(urna, ficha, na_tela)
            if motivo:
                pegas.append(f"{urna.registros[-1]['id']} (eleitor): {motivo}")
        urna.prepara(escolha)
        urna.confirma()
    trocados = V.qtd(urna.contou, "voto trocado", "votos trocados")
    feito = (
        f"sou a urna: troquei Pastel por Esfiha antes de cifrar ({trocados} na contagem), "
        f"{eleitores} eleitores, {chance_desafio:.0%} desafiam uma vez"
    )
    if fiscais:
        feito += f", e {fiscais} fiscais testaram a urna, cada um com o candidato dele"
    return feito, pegas


# ---------------------------------------------------------------- mexendo nas urnas inteiras
def urna_fantasma(c: Cenario):
    m = copy.deepcopy(c.mural)
    fantasma = "secao-999"
    m["urnas"][fantasma] = {"comparecimento": 6}
    for _ in range(6):
        m["cedulas"].append(cedula_nova(c, m, fantasma, "Pão de queijo"))
    return f"inventei a {fantasma}: 6 cédulas perfeitas pro Pão de queijo, com corrente e comparecimento", refaz(c, m)


def some_secao(c: Cenario):
    m = copy.deepcopy(c.mural)
    m["cedulas"] = [r for r in m["cedulas"] if r["urna"] != URNAS[1]]
    del m["urnas"][URNAS[1]]
    return f"sumi com a {URNAS[1]} inteira (ela não votou do jeito que eu queria)", refaz(c, m)


# ---------------------------------------------------------------- a apuração
def resultado_falso(c: Cenario):
    m = copy.deepcopy(c.mural)
    res = m["apuracao"]["resultado"]
    res["Pastel"], res["Esfiha"] = res["Pastel"] - 2, res["Esfiha"] + 2
    m["lacre"] = U.lacre(m)
    return "anunciei Pastel −2 e Esfiha +2 (a soma total continua igual, pra ninguém estranhar)", m


def volta_no_relogio(c: Cenario):
    """g^q = 1: somar q votos dá o mesmo g^votos. A conta "dá a volta" e a soma total continua igual."""
    m = copy.deepcopy(c.mural)
    res = m["apuracao"]["resultado"]
    res["Pastel"], res["Esfiha"] = res["Pastel"] + Q, res["Esfiha"] - Q
    m["lacre"] = U.lacre(m)
    feito = f"anunciei Pastel com {len(str(res['Pastel']))} dígitos de votos e Esfiha negativa"
    return feito + " (a conta no expoente dá a volta e fecha)", m


class Vendido:
    """Embrulha um guardião de verdade e adultera a fatia que ele entrega na apuração."""

    def __init__(self, guardiao: GU.Guardiao) -> None:
        self.guardiao, self.numero, self.nome = guardiao, guardiao.numero, guardiao.nome

    def abre_apuracao(self, mural: dict) -> list[GU.FatiaDecifrada]:
        honestas = self.guardiao.abre_apuracao(mural)
        return [GU.FatiaDecifrada(f.numero, f.m * G % P, f.prova) for f in honestas]  # empurra o resultado


def fatia_forjada_pelo_totalizador(c: Cenario) -> dict:
    """O totalizador anuncia Pastel +1 / Esfiha −1 e forja a fatia PUBLICADA de um guardião pra conta fechar."""
    m = copy.deepcopy(c.mural)
    ap = m["apuracao"]
    presentes = [f["guardiao"] for f in ap["fatias"]]
    w = GU.lagrange(presentes[0], presentes)
    for i, delta in ((0, 1), (2, -1)):
        fator = pow(G, (-delta * pow(w, -1, Q)) % Q, P)
        ap["fatias"][0]["por_opcao"][i][0] = U.hx(int(ap["fatias"][0]["por_opcao"][i][0], 16) * fator % P)
    ap["resultado"]["Pastel"] += 1
    ap["resultado"]["Esfiha"] -= 1
    m["lacre"] = U.lacre(m)
    return m


def fatia_falsa(c: Cenario):
    m = copy.deepcopy(c.mural)
    m["apuracao"] = None
    honestos, (vendido,) = frescos(c), [Vendido(g) for g in frescos(c, 4)[3:]]  # o Fiscal do Partido B se vende
    U.apura(m, [*honestos, vendido])  # 4 presentes: 3 honestos + o vendido
    m["lacre"] = U.lacre(m)
    feito = f"o {vendido.nome} entregou fatia adulterada na apuração"
    if vendido.nome not in m["apuracao"]["recusados"]:
        return feito, []
    if V.verifica(m, saida=lambda _: None, paralelo=False, ata=c.ata):
        return feito, []
    pegos = [
        "a fatia dele não tem prova válida: recusada na hora, com o nome dele no mural",
        f"os outros {QUORUM} abriram a soma sem ele, e o resultado confere",
    ]
    # e se quem publica for cúmplice e puser no mural uma fatia forjada pra conta fechar? o verificador pega
    forjado = V.verifica(fatia_forjada_pelo_totalizador(c), saida=lambda _: None, paralelo=False, ata=c.ata)
    if not any("não tem prova válida" in p for p in forjado):
        return feito, []
    return feito, [*pegos, f"totalizador que publica fatia forjada: {forjado[0]}"]


def mural_de_um_voto(c: Cenario) -> tuple[dict, dict]:
    """O mural sob medida pra abrir UM voto: só a 1ª cédula da seção 1 (a corrente fecha, porque o
    `anterior` dela é o código inicial), a seção 2 vazia, e uma ata forjada que bate com isso."""
    m = copy.deepcopy(c.mural)
    alvo = depositada(m, 0)
    m["cedulas"], m["apuracao"], m["lacre"] = [alvo], None, None
    ctx = m["contexto"]
    forjada = {"versao": U.VERSAO, "contexto": ctx, "urnas": {}}
    for urna in URNAS:
        elo, dep = U.codigo_inicial(ctx, urna), 0
        for reg in (r for r in m["cedulas"] if r["urna"] == urna):
            elo, dep = U.elo(ctx, reg["codigo"], reg["estado"]), dep + (reg["estado"] == U.DEPOSITADA)
        fecho = {
            "depositadas": dep,
            "sem_voto": 0,
            "elo_final": elo,
            "fechamento": U.fechamento(ctx, urna, elo, dep, 0),
        }
        m["urnas"][urna] = {"comparecimento": dep, "devolvidas": 0, **fecho}
        forjada["urnas"][urna] = U.ata_da_secao(fecho, dep)
    return m, forjada


def abre_uma_cedula(c: Cenario):
    """Pede pros guardiões abrirem um mural com uma cédula só (pra descobrir aquele voto), coerente com uma
    ata forjada. Só conta como pego se NENHUM guardião honesto abrir."""
    m, forjada = mural_de_um_voto(c)
    coerente = not V.verifica(m, saida=lambda _: None, paralelo=False, ata=forjada, ate=5)
    feito = f"pedi pros guardiões abrirem um mural só com a cédula {m['cedulas'][0]['id']}"
    if coerente:
        feito += ", com uma ata forjada que bate com ele"
    motivos = []
    todos = [*frescos(c, len(GUARDIOES)), c.guardioes[0]]  # os 5 sem abrir nada, e um que já abriu a de verdade
    for guardiao in todos:
        try:
            guardiao.abre_apuracao(m)
        except GU.ErroCerimonia as e:
            motivos.append(f"recusou: {e}")
    if not coerente or len(motivos) < len(todos):  # se UM honesto abriu, o golpe passou
        return feito, []
    return feito, motivos


def conluio(c: Cenario):
    """Dois guardiões se juntam, usando o segredo de cada um direto, pra abrir UMA cédula. Quórum é 3."""
    reg = depositada(c.mural, 0)
    cf = C.Cifra(*(int(x, 16) for x in reg["cifras"][0]))
    dupla = c.guardioes[2:4]
    fatias = [GU.FatiaDecifrada(g.numero, pow(cf.alfa, g._segredo, P), None) for g in dupla]
    aberto = C.log_pequeno(cf.beta * pow(GU.combina(fatias), -1, P) % P, 1)
    nomes = " + ".join(g.nome for g in dupla)
    if aberto is None:
        feito = f"{nomes} juntaram os segredos pra abrir a cédula {reg['id']}"
        return feito, ["deu lixo: nem 0 nem 1 (dois guardiões não abrem nada)"]
    return f"{nomes} abriram a cédula {reg['id']}", []


class GuardiaoPirata(GU.Guardiao):
    """Espera os outros publicarem e escolhe a parte dele pra chave final ser g^x, com x só dele."""

    def pirateia(self, outros: list[GU.Compromissos]) -> int:
        x = GRUPO.aleatorio()
        dos_outros = GU.chave_da_eleicao(outros)
        c0 = C.potencia(G, x) * pow(dos_outros, -1, P) % P
        c = self.compromissos
        self.compromissos = GU.Compromissos(c.numero, c.nome, (c0, *c.coeficientes[1:]), c.provas)
        return C.potencia(G, x)


def chave_pirata(c: Cenario):
    pre = U.pre_contexto(c.manifesto)
    honestos = [GU.Guardiao(i + 1, nome, QUORUM, pre) for i, nome in enumerate(GUARDIOES[:-1])]
    pirata = GuardiaoPirata(len(GUARDIOES), GUARDIOES[-1], QUORUM, pre)
    chave_dele = pirata.pirateia([g.compromissos for g in honestos])
    todos = [*honestos, pirata]
    controla = GU.chave_da_eleicao([g.compromissos for g in todos]) == chave_dele
    try:
        GU.cerimonia(todos, QUORUM, pre)
    except GU.ErroCerimonia as e:
        feito = "guardião escolheu a parte dele DEPOIS de ver a dos outros"
        if controla:
            feito += " (se ninguém conferisse, a chave inteira seria só dele)"
        return feito, [f"a cerimônia parou: {e}"]
    return "chave pirata", []


# ---------------------------------------------------------------- golpes 18 a 22: os da auditoria
class UrnaTrocaNoDesafio(U.Urna):
    """Cifra Esfiha pra quem escolheu Pastel e imprime o código dela. Se o eleitor DESAFIA, joga fora a
    trocada, monta na hora uma cédula honesta e abre ESSA: os segredos batem com a tela."""

    def prepara(self, escolha: str) -> str:
        self._na_tela = escolha
        return super().prepara("Esfiha" if escolha == "Pastel" else escolha)

    def desafia(self) -> dict:
        if self._na_tela == "Pastel":
            self._pendente, self._seq = None, self._seq - 1
            super().prepara("Pastel")
        return super().desafia()


def troca_no_desafio(c: Cenario):
    urna = UrnaTrocaNoDesafio(URNAS[0], c.manifesto, c.mural["contexto"], c.chave)
    ficha = U.nova_ficha()
    urna.libera(ficha)
    motivo = desafio_na_cabine(urna, ficha, "Pastel")
    so_segredos = V.confere_abertura(urna.ctx, c.chave, OPCOES, urna.registros[-1]) == "Pastel"
    feito = "sou a urna: no DESAFIA, jogo fora a cédula trocada, monto uma honesta e abro essa"
    if so_segredos:
        feito += " (os segredos abrem Pastel direitinho)"
    return feito, [f"o celular confere o código impresso: {motivo}"] if motivo else []


class UrnaClash(U.Urna):
    """Guarda os segredos de uma cédula de Pastel já depositada. Pro próximo eleitor de Pastel, imprime o
    código DAQUELA cédula e, no CONFIRMA, deposita Esfiha no lugar dele (código que ninguém recebe)."""

    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.guardada: str | None = None
        self.reuso: str | None = None
        self.roubados = 0

    def prepara(self, escolha: str) -> str:
        codigo = super().prepara(escolha)
        self.reuso = None
        if escolha == "Pastel" and self.guardada is not None:
            self.reuso, self.guardada = self.guardada, None
            return self.reuso
        return codigo

    def confirma(self) -> str:
        if self.reuso is None:
            _, codigo, escolha, _ = self._pendente
            super().confirma()
            if escolha == "Pastel":
                self.guardada = codigo
            return codigo
        impresso, self.reuso = self.reuso, None
        self._pendente, self._seq = None, self._seq - 1
        super().prepara("Esfiha")
        super().confirma()
        self.roubados += 1
        return impresso  # o eleitor sai com o código de OUTRO eleitor na mão


def clash(c: Cenario):
    mural = U.novo_mural(c.manifesto, [g.compromissos for g in c.guardioes], c.chave)
    ata = {"versao": U.VERSAO, "contexto": mural["contexto"], "urnas": {}}
    recibos, roubados = [], 0
    for ident in URNAS:
        urna = UrnaClash(ident, c.manifesto, mural["contexto"], c.chave)
        recibos += vota(urna, ESCOLHAS[ident], {})
        roubados += urna.roubados
        fecho = urna.fecha()
        U.publica_urna(mural, ident, urna.registros, fecho, comparecimento=len(ESCOLHAS[ident]))
        ata["urnas"][ident] = U.ata_da_secao(fecho, len(ESCOLHAS[ident]))
    perfeito = not V.verifica(mural, saida=lambda _: None, paralelo=False, ata=ata, ate=5)
    sem_ficha = all(V.confere_recibo(mural, U.codigo_curto(cod))[0] for cod, _, _ in recibos)
    feito = f"sou a urna: dei pra {roubados} eleitores de Pastel o recibo de OUTRO que votou igual e contei Esfiha"
    if perfeito and sem_ficha:
        feito += " (o mural fica perfeito, e sem a ficha todo recibo confere em casa)"
    pegos = []
    for cod, _, ficha in recibos:
        ok, mensagem = V.confere_recibo(mural, U.codigo_curto(cod), ficha=U.ficha_impressa(ficha))
        if not ok:
            pegos.append(f"recibo + ficha em casa: {mensagem}")
    repetidos = V.recibos_repetidos([U.codigo_curto(cod) for cod, _, _ in recibos])
    if repetidos:
        pegos.append(
            f"a coleta pública de recibos acha {V.qtd(len(repetidos), 'recibo repetido', 'recibos repetidos')}"
        )
    return feito, pegos if roubados else []


class UrnaJogaFora(U.Urna):
    """No CONFIRMA de um eleitor de Pastel, imprime o código mas grava a sessão como SEM_VOTO (como se ele
    tivesse desistido). As contas da urna fecham: depositadas + sem voto = fichas."""

    jogou = False

    def confirma(self) -> str:
        _, codigo, escolha, _ = self._pendente
        if escolha != "Pastel" or self.jogou:
            return super().confirma()
        self._pendente, self._seq = None, self._seq - 1
        self.encerra_sem_voto()
        self.jogou = True
        return codigo


def joga_fora(c: Cenario):
    mural = U.novo_mural(c.manifesto, [g.compromissos for g in c.guardioes], c.chave)
    ata = {"versao": U.VERSAO, "contexto": mural["contexto"], "urnas": {}}
    recibos = []
    for ident in URNAS:
        urna = UrnaJogaFora(ident, c.manifesto, mural["contexto"], c.chave)
        recibos += vota(urna, ESCOLHAS[ident], {})
        fecho = urna.fecha()
        U.publica_urna(mural, ident, urna.registros, fecho, comparecimento=len(ESCOLHAS[ident]))  # a mesa: 0 devolvidas
        ata["urnas"][ident] = U.ata_da_secao(fecho, len(ESCOLHAS[ident]))
    feito = "sou a urna: joguei fora um voto de Pastel como se o eleitor tivesse desistido (SEM_VOTO)"
    pegos = [p for p in V.verifica(mural, saida=lambda _: None, paralelo=False, ata=ata, ate=5) if "devolvida" in p][:1]
    # e se o mesário for cúmplice e anotar uma ficha devolvida que não voltou? sobra o recibo do eleitor
    cumplice, ata_cumplice = copy.deepcopy(mural), copy.deepcopy(ata)
    for urnas in (cumplice["urnas"], ata_cumplice["urnas"]):
        for ident in URNAS:
            urnas[ident]["devolvidas"] = mural["urnas"][ident]["sem_voto"]
    if not V.verifica(cumplice, saida=lambda _: None, paralelo=False, ata=ata_cumplice, ate=5):
        cod, _, ficha = next(r for r in recibos if r[1] == "Pastel")
        ok, mensagem = V.confere_recibo(cumplice, U.codigo_curto(cod), ficha=U.ficha_impressa(ficha))
        if not ok:
            pegos.append(f"com o mesário cúmplice, o eleitor em casa: {mensagem}")
    return feito, pegos


class UrnaPosDesafio(U.Urna):
    """Trapaceia SÓ na cédula logo depois de um desafio, na mesma sessão: quase sempre é o voto de verdade de
    quem acabou de desafiar (quase ninguém desafia duas vezes seguidas)."""

    _acabou_de_desafiar = False

    def prepara(self, escolha: str) -> str:
        self.trocou = self._acabou_de_desafiar and escolha != "Esfiha"
        return super().prepara("Esfiha" if self.trocou else escolha)

    def desafia(self) -> dict:
        self._acabou_de_desafiar = True
        return super().desafia()

    def confirma(self) -> str:
        self._acabou_de_desafiar = False
        return super().confirma()

    def encerra_sem_voto(self) -> str:
        self._acabou_de_desafiar = False
        return super().encerra_sem_voto()


def pos_desafio(c: Cenario, eleitores: int = 30, chance_desafio: float = 0.3, semente: int = 5):
    sorteio = random.Random(semente)
    urna = UrnaPosDesafio(URNAS[0], c.manifesto, c.mural["contexto"], c.chave)
    trocados = pegos_por_eleitor = 0
    pegos = []
    for n in range(eleitores):
        if n == eleitores // 2:  # um fiscal: dois desafios SEGUIDOS na mesma sessão, o 2º com o candidato dele
            ficha = U.nova_ficha()
            urna.libera(ficha)
            for na_tela in (sorteio.choice(OPCOES), "Pastel"):
                motivo = desafio_na_cabine(urna, ficha, na_tela)
                if motivo:
                    pegos.append(f"o fiscal, no desafio seguido: {motivo}")
            urna.encerra_sem_voto()
        ficha = U.nova_ficha()
        urna.libera(ficha)
        if sorteio.random() < chance_desafio:
            pegos_por_eleitor += desafio_na_cabine(urna, ficha, sorteio.choice(OPCOES)) is not None
        urna.prepara(sorteio.choices(OPCOES, PESOS)[0])
        trocados += urna.trocou
        urna.confirma()
    feito = (
        f"sou a urna: troquei {V.qtd(trocados, 'voto', 'votos')}, só na cédula logo depois de um desafio "
        f"(os eleitores, que desafiam uma vez só, pegaram {pegos_por_eleitor})"
    )
    return feito, pegos


def resultado_escondido(c: Cenario):
    """Um JSON com DUAS chaves "resultado": quem abre o arquivo de olho lê a primeira (falsa), o Python fica
    com a última (a verdadeira), e o lacre é o mesmo do mural honesto."""
    m = copy.deepcopy(c.mural)
    falso = {o: (len(c.mural["cedulas"]) if o == "Esfiha" else 0) for o in OPCOES}
    m["apuracao"] = "@@APURACAO@@"
    texto = json.dumps(m, ensure_ascii=False, indent=1)
    ap = json.dumps(c.mural["apuracao"], ensure_ascii=False)
    texto = texto.replace('"@@APURACAO@@"', '{"resultado": ' + json.dumps(falso, ensure_ascii=False) + ", " + ap[1:])
    mesmo_lacre = json.loads(texto)["lacre"] == U.lacre(json.loads(texto))
    feito = "escondi no mural um resultado falso (Esfiha ganhando) ANTES do verdadeiro, com a mesma chave"
    if mesmo_lacre:
        feito += " (o lacre continua batendo)"
    try:
        V.le_json(texto)
    except ValueError as e:
        return feito, [f"o verificador recusa o arquivo: {e}"]
    return feito, []


ATAQUES = [
    ("Troco um voto já depositado", troca_voto),
    ("Apago uma cédula", apaga),
    ("Cédula turbinada: 5 votos de uma vez", turbinada),
    ("Voto em dois na mesma cédula", voto_duplo),
    ("Copio a cédula de alguém (repetição)", repeticao),
    ("Encho a urna e reescrevo o comparecimento", enche_urna),
    ("Viro uma cédula desafiada em voto", vira_desafiada),
    ("A urna troca o voto ANTES de cifrar", urna_trapaceira),
    ("A urna troca o voto DEPOIS do CONFIRMA", troca_depois_do_botao),
    ("Invento uma seção inteira", urna_fantasma),
    ("Sumo com uma seção inteira", some_secao),
    ("Anuncio um resultado falso", resultado_falso),
    ("Resultado que dá a volta no relógio", volta_no_relogio),
    ("Guardião vendido na apuração", fatia_falsa),
    ("Peço pros guardiões abrirem uma cédula só", abre_uma_cedula),
    ("Dois guardiões juntam os segredos", conluio),
    ("Chave pirata na cerimônia", chave_pirata),
    ("A urna troca a cédula na hora do DESAFIO", troca_no_desafio),
    ("Dois eleitores, um recibo só (clash)", clash),
    ("Jogo um voto fora como se fosse desistência", joga_fora),
    ("A urna trapaceia logo depois de um desafio", pos_desafio),
    ("Escondo um resultado falso no arquivo", resultado_escondido),
]


def ataca(c: Cenario, funcao) -> tuple[str, list[str]]:
    """Roda um golpe. Se ele devolver um mural, o verificador independente julga (com a ata das portas)."""
    feito, resultado = funcao(c)
    if isinstance(resultado, dict):
        return feito, V.verifica(resultado, saida=lambda _: None, paralelo=False, ata=c.ata)
    return feito, resultado


def main() -> int:
    print(pinta(f"Ataques à Urna do Garoto;  ·  {len(ATAQUES)} golpes. Duvida? Roda.", "1"))
    c = eleicao()
    problemas = V.verifica(c.mural, saida=lambda _: None, paralelo=False, ata=c.ata)
    situacao = "OK ✓" if not problemas else "FALHOU"
    print(f"eleição honesta de base: {len(URNAS)} seções, {len(c.mural['cedulas'])} cédulas, verificador {situacao}\n")
    passaram = 0
    for numero, (titulo, funcao) in enumerate(ATAQUES, start=1):
        feito, pegos = ataca(c, funcao)
        if numero == 18:
            print(pinta("· · · golpes 18 a 22: achados na auditoria antes de publicar · · ·\n", "1"))
        print(pinta(f"Golpe {numero:02} · {titulo}", "1"))
        print(f"   o que eu fiz: {feito}")
        if pegos:
            print(pinta(f"   PEGO ✓  {pegos[0]}", "32"))
            for extra in pegos[1:3]:
                print(pinta(f"           {extra}", "32"))
        else:
            passaram += 1
            print(pinta("   PASSOU ✗  (abre uma issue: achamos um furo)", "31"))
    print(pinta(f"\n{len(ATAQUES) - passaram} de {len(ATAQUES)} golpes pegos.", "1"))
    print("\nO que a matemática NÃO pega (está no README, sem esconder):")
    print("  · a urna ver o voto na hora em que você digita (isso é com o hardware: HARDWARE.md);")
    print("  · ninguém desafiar a urna nem conferir o recibo com a ficha (por isso o fiscal desafia o dia inteiro);")
    print(f"  · {QUORUM} guardiões de lados rivais se juntarem pra abrir um voto (por isso são rivais);")
    print("  · uma ata que não veio das fotos das portas (ela não tem assinatura digital);")
    print("  · alguém do seu lado na cabine mandando você votar.")
    return 1 if passaram or problemas else 0


if __name__ == "__main__":
    sys.exit(main())
