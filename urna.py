"""
A Urna do Garoto;  —  a máquina de votar e o mural público.
por Garoto do Programa;  (github.com/garotodoprograma404/urna-do-garoto)

O eleitor na cabine:
  0. na mesa, sorteia às cegas uma FICHA de um saco embaralhado (um número aleatório; a mesa não anota
     quem pegou qual) e digita/escaneia a ficha na urna: é isso que libera a cabine;
  1. escolhe na tela;
  2. a urna cifra a cédula (1 na opção escolhida, 0 nas outras), gera as provas e IMPRIME o código
     de confirmação ANTES de saber o que o eleitor vai fazer. O código amarra a ficha dele;
  3. o eleitor decide:
       CONFIRMA → a cédula cifrada vai pro mural, os segredos são apagados e ele leva o código pra casa;
       DESAFIA  → a urna é obrigada a entregar os segredos, e o celular dele (ou do fiscal) confere que a
                  cédula aberta é a do código impresso e cifrou o que estava na tela. Essa cédula vai pro
                  mural como DESAFIADA (não conta) e ele vota de novo, na mesma sessão.
  Como a urna se compromete antes de saber, cada desafio é uma chance de pegar uma urna trapaceira
  (desafio de Benaloh, 2006).
  Se a sessão acaba sem voto (o eleitor desistiu, ou era o teste de um fiscal), o mesário aperta ENCERRAR:
  a urna grava SEM_VOTO na corrente e a mesa anota a ficha como devolvida.

O mural é público: qualquer um baixa, confere todas as provas e refaz a apuração (verificador.py).
O código de confirmação não revela o voto: é um hash da cédula CIFRADA (e da ficha).
"""

from __future__ import annotations

import json
import math
import re
import secrets
from dataclasses import dataclass
from pathlib import Path

import cripto as C
import guardioes as GU
import verificador as V  # a urna usa o verificador; o verificador NÃO importa a urna
from grupo import GRUPO

P, Q, G = GRUPO.p, GRUPO.q, GRUPO.g
VERSAO = "urna-do-garoto/v2"
DEPOSITADA, DESAFIADA, SEM_VOTO = "DEPOSITADA", "DESAFIADA", "SEM_VOTO"
FICHA = re.compile(r"[0-9a-f]{16}")


class ErroUrna(Exception):
    pass


@dataclass(frozen=True)
class Manifesto:
    """Publicado ANTES da eleição: o que se vota, quem guarda a chave e a lista fechada de urnas."""

    eleicao: str
    opcoes: tuple[str, ...]
    guardioes: tuple[str, ...]
    quorum: int
    urnas: tuple[str, ...]


# ---------------------------------------------------------------- as receitas de hash (iguais às do PROTOCOLO.md)
def pre_contexto(m: Manifesto) -> str:
    return C.hash_hex("pre-contexto", GRUPO.p, GRUPO.q, GRUPO.g, m.eleicao, m.opcoes, m.guardioes, m.quorum, m.urnas)


def contexto(pre: str, compromissos: list[GU.Compromissos]) -> str:
    return C.hash_hex("contexto", pre, [(c.numero, c.nome, c.coeficientes) for c in compromissos])


def codigo_inicial(ctx: str, urna: str) -> str:
    return C.hash_hex("inicio", ctx, urna)


def codigo_da_cedula(ctx: str, anterior: str, ficha: str, ced: Cedula) -> str:
    return C.hash_hex(
        "codigo",
        ctx,
        anterior,
        ced.id,
        ficha,
        [(cf.alfa, cf.beta) for cf in ced.cifras],
        [(p.c0, p.c1, p.v0, p.v1) for p in ced.provas],
        (ced.prova_soma.c, ced.prova_soma.v),
    )


def codigo_sem_voto(ctx: str, anterior: str, ident: str, ficha: str) -> str:
    return C.hash_hex("sem-voto", ctx, anterior, ident, ficha)


def elo(ctx: str, codigo: str, estado: str) -> str:
    """Amarra a decisão (depositada/desafiada/sem voto) na corrente: virar uma desafiada em depositada quebra tudo."""
    return C.hash_hex("elo", ctx, codigo, estado)


def fechamento(ctx: str, urna: str, ultimo_elo: str, depositadas: int, sem_voto: int) -> str:
    return C.hash_hex("fechamento", ctx, urna, ultimo_elo, depositadas, sem_voto)


def codigo_curto(codigo: str) -> str:
    """O que vai impresso no recibo: 32 dígitos (128 bits), em 8 grupos. O QR code leva o código inteiro.
    Com 128 bits, achar duas cédulas com o mesmo começo custa ~2^64 (a urna escolhe os dois lados)."""
    return "-".join(codigo[i : i + 4] for i in range(0, 32, 4)).upper()


def nova_ficha() -> str:
    """Uma ficha do saco da mesa: 64 bits aleatórios. Na vida real, impressa num cartão e sorteada às cegas."""
    return secrets.token_hex(8)


def ficha_impressa(ficha: str) -> str:
    return "-".join(ficha[i : i + 4] for i in range(0, 16, 4)).upper()


# ---------------------------------------------------------------- a cédula cifrada
@dataclass(frozen=True)
class Cedula:
    id: str
    cifras: tuple[C.Cifra, ...]
    provas: tuple[C.ProvaZeroOuUm, ...]
    prova_soma: C.ProvaIgualdade


def monta_cedula(ctx: str, chave: int, n_opcoes: int, escolha: int, ident: str) -> tuple[Cedula, list[int]]:
    """Cifra 1 na opção escolhida e 0 nas outras, com as duas provas:
    - cada cifra esconde 0 ou 1 (ninguém enfia 50 votos numa cédula);
    - a soma da cédula esconde exatamente 1 (ninguém vota em dois)."""
    segredos = [GRUPO.aleatorio() for _ in range(n_opcoes)]
    votos = [int(i == escolha) for i in range(n_opcoes)]
    cifras = tuple(C.cifra(chave, m, r) for m, r in zip(votos, segredos, strict=True))
    provas = tuple(
        C.prova_zero_ou_um((ctx, ident, i), chave, cf, m, r)
        for i, (cf, m, r) in enumerate(zip(cifras, votos, segredos, strict=True))
    )
    total = math.prod(cifras, start=C.CIFRA_ZERO)
    prova_soma = C.prova_soma((ctx, ident), chave, total, 1, sum(segredos) % Q)
    return Cedula(ident, cifras, provas, prova_soma), segredos


def registro(
    ced: Cedula, urna: str, anterior: str, ficha: str, codigo: str, estado: str, abertura: dict | None
) -> dict:
    """A cédula do jeito que aparece no mural (JSON, números em hexadecimal)."""
    return {
        "id": ced.id,
        "urna": urna,
        "anterior": anterior,
        "ficha": ficha,
        "codigo": codigo,
        "cifras": [[hx(cf.alfa), hx(cf.beta)] for cf in ced.cifras],
        "provas": [[hx(p.c0), hx(p.c1), hx(p.v0), hx(p.v1)] for p in ced.provas],
        "prova_soma": [hx(ced.prova_soma.c), hx(ced.prova_soma.v)],
        "estado": estado,
        "abertura": abertura,
    }


def registro_sem_voto(ident: str, urna: str, anterior: str, ficha: str, codigo: str) -> dict:
    """Uma sessão que acabou sem voto: entra na corrente, sem cifra nenhuma."""
    return {"id": ident, "urna": urna, "anterior": anterior, "ficha": ficha, "codigo": codigo, "estado": SEM_VOTO}


def hx(x: int) -> str:
    return format(x, "x")


def cedula_do_registro(reg: dict) -> Cedula:
    return Cedula(
        reg["id"],
        tuple(C.Cifra(int(a, 16), int(b, 16)) for a, b in reg["cifras"]),
        tuple(C.ProvaZeroOuUm(*(int(x, 16) for x in pr)) for pr in reg["provas"]),
        C.ProvaIgualdade(*(int(x, 16) for x in reg["prova_soma"])),
    )


# ---------------------------------------------------------------- a urna
class Urna:
    def __init__(self, ident: str, manifesto: Manifesto, ctx: str, chave: int) -> None:
        if not C.pertence(chave) or chave == 1:
            raise ErroUrna("chave da eleição inválida")
        if ident not in manifesto.urnas:
            raise ErroUrna(f"{ident!r} não está na lista de urnas do manifesto")
        C.fixa(chave)
        self.ident, self.manifesto, self.ctx, self.chave = ident, manifesto, ctx, chave
        self.registros: list[dict] = []
        self.depositadas = 0
        self.sem_voto = 0
        self._elo = codigo_inicial(ctx, ident)
        self._seq = 0
        self._ficha: str | None = None  # a sessão aberta (a ficha que liberou a cabine)
        self._usadas: set[str] = set()
        self._pendente: tuple[Cedula, str, str, list[int]] | None = None
        self._fechada = False

    def libera(self, ficha: str) -> None:
        """A mesa liberou a cabine: o eleitor (ou o fiscal, que a urna não distingue) digita a ficha que sorteou."""
        if self._fechada:
            raise ErroUrna("urna fechada")
        if self._ficha is not None:
            raise ErroUrna("tem uma sessão aberta: CONFIRMA ou ENCERRA antes")
        if not isinstance(ficha, str) or not FICHA.fullmatch(ficha):
            raise ErroUrna("ficha inválida")
        if ficha in self._usadas:
            raise ErroUrna("essa ficha já foi usada nesta urna")
        self._ficha = ficha

    def prepara(self, escolha: str) -> str:
        """Cifra a escolha e devolve o código de confirmação (impresso antes do eleitor decidir)."""
        if self._fechada:
            raise ErroUrna("urna fechada")
        if self._ficha is None:
            raise ErroUrna("a mesa não liberou a cabine (sem ficha)")
        if self._pendente:
            raise ErroUrna("tem uma cédula esperando CONFIRMA ou DESAFIA")
        if escolha not in self.manifesto.opcoes:
            raise ErroUrna(f"opção inexistente: {escolha!r}")
        self._seq += 1
        ced, segredos = monta_cedula(
            self.ctx,
            self.chave,
            len(self.manifesto.opcoes),
            self.manifesto.opcoes.index(escolha),
            f"{self.ident}/{self._seq:06d}",
        )
        codigo = codigo_da_cedula(self.ctx, self._elo, self._ficha, ced)
        self._pendente = (ced, codigo, escolha, segredos)
        return codigo

    def confirma(self) -> str:
        """Deposita a cédula e encerra a sessão. O eleitor leva o código e, em casa, confere que ela está no
        mural como DEPOSITADA e com a ficha dele (se a urna marcar como desafiada, o verificador grita)."""
        ced, codigo, _, segredos = self._tira_pendente()
        segredos.clear()  # apagados (em Python isso não zera a memória; na urna de verdade, o chip zera)
        self._registra(ced, codigo, DEPOSITADA, None)
        self.depositadas += 1
        self._encerra_sessao()
        return codigo

    def desafia(self) -> dict:
        """A urna entrega os segredos. Essa cédula não conta: o eleitor vota de novo, na mesma sessão."""
        ced, codigo, escolha, segredos = self._tira_pendente()
        abertura = {"escolha": escolha, "segredos": [hx(r) for r in segredos]}
        self._registra(ced, codigo, DESAFIADA, abertura)
        return abertura

    def encerra_sem_voto(self) -> str:
        """O mesário aperta ENCERRAR: o eleitor desistiu (ou era o teste do fiscal). Cédula que ninguém
        confirmou nunca conta: se tiver uma esperando, ela é aberta como desafiada. A sessão vira SEM_VOTO."""
        if self._ficha is None:
            raise ErroUrna("nenhuma sessão aberta")
        if self._pendente:
            self.desafia()
        self._seq += 1
        ident = f"{self.ident}/{self._seq:06d}"
        codigo = codigo_sem_voto(self.ctx, self._elo, ident, self._ficha)
        self.registros.append(registro_sem_voto(ident, self.ident, self._elo, self._ficha, codigo))
        self._elo = elo(self.ctx, codigo, SEM_VOTO)
        self.sem_voto += 1
        self._encerra_sessao()
        return codigo

    def fecha(self) -> dict:
        """Fim do dia: o que sai impresso e vai colado na porta da seção (como o boletim de urna)."""
        if self._pendente or self._ficha is not None:
            raise ErroUrna("tem sessão aberta ou cédula pendente")
        self._fechada = True
        return {
            "depositadas": self.depositadas,
            "sem_voto": self.sem_voto,
            "elo_final": self._elo,
            "fechamento": fechamento(self.ctx, self.ident, self._elo, self.depositadas, self.sem_voto),
        }

    def _tira_pendente(self) -> tuple[Cedula, str, str, list[int]]:
        if not self._pendente:
            raise ErroUrna("nenhuma cédula preparada")
        pendente, self._pendente = self._pendente, None
        return pendente

    def _registra(self, ced: Cedula, codigo: str, estado: str, abertura: dict | None) -> None:
        self.registros.append(registro(ced, self.ident, self._elo, self._ficha, codigo, estado, abertura))
        self._elo = elo(self.ctx, codigo, estado)

    def _encerra_sessao(self) -> None:
        self._usadas.add(self._ficha)
        self._ficha = None


# ---------------------------------------------------------------- o mural público
def novo_mural(m: Manifesto, compromissos: list[GU.Compromissos], chave: int) -> dict:
    pre = pre_contexto(m)
    return {
        "versao": VERSAO,
        "grupo": {"p": hx(GRUPO.p), "q": hx(GRUPO.q), "g": hx(GRUPO.g)},
        "manifesto": {
            "eleicao": m.eleicao,
            "opcoes": list(m.opcoes),
            "guardioes": list(m.guardioes),
            "quorum": m.quorum,
            "urnas": list(m.urnas),
        },
        "cerimonia": [
            {
                "numero": c.numero,
                "nome": c.nome,
                "coeficientes": [hx(x) for x in c.coeficientes],
                "provas": [[hx(p.c), hx(p.v)] for p in c.provas],
            }
            for c in compromissos
        ],
        "chave": hx(chave),
        "contexto": contexto(pre, compromissos),
        "urnas": {},
        "cedulas": [],
        "apuracao": None,
        "lacre": None,
    }


def publica_urna(
    mural: dict, urna: str, registros: list[dict], fecho: dict, comparecimento: int, devolvidas: int = 0
) -> None:
    """Junta no mural o que uma urna gravou + o que a MESA (outro aparelho) contou: fichas liberadas
    (comparecimento) e fichas que voltaram sem voto (devolvidas: desistência ou teste do fiscal)."""
    mural["cedulas"].extend(registros)
    mural["urnas"][urna] = {"comparecimento": comparecimento, "devolvidas": devolvidas, **fecho}


def ata_da_secao(fecho: dict, comparecimento: int, devolvidas: int = 0) -> dict:
    """O que fica FORA do mural: o que a urna imprimiu e foi colado na porta (elo final, depositadas,
    sem voto) e o que a mesa assinou (fichas liberadas e devolvidas), fotografados pelos fiscais.
    É a âncora que quem monta o mural não consegue reescrever, SE vier das fotos (e não de quem montou)."""
    return {
        "comparecimento": comparecimento,
        "devolvidas": devolvidas,
        "depositadas": fecho["depositadas"],
        "sem_voto": fecho["sem_voto"],
        "elo_final": fecho["elo_final"],
    }


def compromissos_do_mural(mural: dict) -> list[GU.Compromissos]:
    return [
        GU.Compromissos(
            c["numero"],
            c["nome"],
            tuple(int(x, 16) for x in c["coeficientes"]),
            tuple(C.ProvaConhecimento(int(a, 16), int(b, 16)) for a, b in c["provas"]),
        )
        for c in mural["cerimonia"]
    ]


def apura(mural: dict, presentes: list[GU.Guardiao]) -> dict:
    """Pede a cada guardião presente que abra a parte dele da SOMA (nunca de uma cédula) e publica o resultado.
    Quem decide abrir é cada guardião, conferindo o mural contra a ata dos fiscais DELE
    (ver Guardiao.abre_apuracao). Quem pede não entrega ata nenhuma."""
    quorum = mural["manifesto"]["quorum"]
    numeros = [g.numero for g in presentes]
    if len(set(numeros)) != len(numeros):
        raise ErroUrna("guardião repetido na apuração")
    if len(numeros) < quorum:
        raise ErroUrna(f"precisa de {quorum} guardiões diferentes pra abrir a apuração")
    compromissos = compromissos_do_mural(mural)
    ctx, somas = mural["contexto"], V.totais(mural)
    depositadas = sum(1 for reg in mural["cedulas"] if reg["estado"] == DEPOSITADA)
    aceitas: list[list[GU.FatiaDecifrada]] = []
    recusados: list[str] = []
    motivos: list[str] = []
    for g in presentes:
        try:
            fs = g.abre_apuracao(mural)
        except GU.ErroCerimonia as e:
            motivos.append(str(e))
            continue
        verificacao = GU.chave_de_verificacao(compromissos, g.numero)
        # cada fatia é conferida ANTES de entrar na conta: guardião que mente fica de fora (e com o nome no mural)
        honesta = len(fs) == len(somas) and all(
            f.numero == g.numero and GU.confere_fatia(f, ctx, i, verificacao, t)
            for i, (f, t) in enumerate(zip(fs, somas, strict=True))
        )
        if honesta:
            aceitas.append(fs)
        else:
            recusados.append(g.nome)
    if len(aceitas) < quorum:
        explica = f" ({motivos[0]})" if motivos else ""
        raise ErroUrna(f"só {len(aceitas)} fatias válidas; precisa de {quorum}{explica}")
    resultado = {}
    for i, (opcao, total) in enumerate(zip(mural["manifesto"]["opcoes"], somas, strict=True)):
        alfa_s = GU.combina([fs[i] for fs in aceitas])
        votos = C.log_pequeno(total.beta * pow(alfa_s, -1, P) % P, depositadas)
        if votos is None:
            raise ErroUrna("a soma não abriu")
        resultado[opcao] = votos
    mural["apuracao"] = {
        "totais": [[hx(t.alfa), hx(t.beta)] for t in somas],
        "fatias": [
            {"guardiao": fs[0].numero, "por_opcao": [[hx(f.m), hx(f.prova.c), hx(f.prova.v)] for f in fs]}
            for fs in aceitas
        ],
        "recusados": recusados,
        "resultado": resultado,
    }
    return resultado


def lacre(mural: dict) -> str:
    """Hash de tudo. Mudou uma vírgula no mural, o lacre muda."""
    corpo = {k: v for k, v in mural.items() if k != "lacre"}
    return C.hash_hex("lacre", json.dumps(corpo, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def salva(mural: dict, caminho: str | Path) -> None:
    mural["lacre"] = lacre(mural)
    Path(caminho).write_text(json.dumps(mural, ensure_ascii=False, indent=1), encoding="utf-8")
