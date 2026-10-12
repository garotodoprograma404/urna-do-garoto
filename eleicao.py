#!/usr/bin/env python3
"""
Eleição completa na Urna do Garoto;  —  eleição de mentira, matemática de verdade.
por Garoto do Programa;  (github.com/garotodoprograma404/urna-do-garoto)

Roda do começo ao fim:
  1. o grupo (da semente pública);
  2. a cerimônia: 5 guardiões, a chave nasce dividida, abre com 3;
  3. a votação: várias seções ao mesmo tempo. Cada eleitor sorteia uma ficha na mesa; alguns DESAFIAM a
     urna (uma vez, com uma opção qualquer) e o celular confere a cédula aberta contra o código impresso;
     de vez em quando um FISCAL pega uma ficha como qualquer um e desafia 2 ou 3 vezes seguidas (a urna
     não sabe quem é, e não sabe qual cédula vai ser a de verdade);
  4. o fechamento: cada urna imprime o elo final (vai colado na porta) e a mesa assina as fichas
     liberadas e as devolvidas sem voto: isso vira a ATA, que mora FORA do mural;
  5. a apuração: cada guardião confere o mural contra a ata dos fiscais DELE e abre só a soma
     (o Garoto perdeu a chave dele, mas não faz falta);
  6. o verificador confere o mural inteiro.

Uso:
  python3 eleicao.py                               # 3 seções × 100 eleitores (~1-3 min)
  python3 eleicao.py --secoes 4 --eleitores 300    # uma seção do tamanho das do Brasil (~300)
  python3 verificador.py mural.json --ata ata.json # confere de novo, quando quiser
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import guardioes as GU
import urna as U
import verificador as V
from grupo import GRUPO, SEMENTE
from verificador import pinta

ELEICAO = "Eleição da Firma 2026: o lanche oficial da reunião de sexta"
OPCOES = ("Pastel", "Pão de queijo", "Esfiha", "BRANCO")
PESOS = (0.38, 0.34, 0.22, 0.06)  # como os eleitores de mentira votam (só a simulação sabe)
GUARDIOES = ("Universidade", "Imprensa", "Fiscal do Partido A", "Fiscal do Partido B", "Garoto do Programa;")
QUORUM = 3


def vota_secao(args: tuple) -> dict:
    """Uma seção inteira, num processo só dela (como na vida real: cada urna vota sozinha)."""
    ident, manifesto, ctx, chave, eleitores, chance_desafio, chance_fiscal, semente = args
    sorteio = random.Random(semente)
    urna = U.Urna(ident, manifesto, ctx, chave)
    verdade, desafios, recibos = Counter(), [], []
    fichas = devolvidas = 0

    def desafia(ficha: str) -> None:
        # desafio com uma opção QUALQUER (não precisa ser a do eleitor: assim a cédula desafiada, que fica
        # pública, não entrega o voto de ninguém). O celular confere a cédula aberta contra o código impresso.
        na_tela = sorteio.choice(OPCOES)
        impresso = urna.prepara(na_tela)
        urna.desafia()
        motivo = V.confere_desafio_na_cabine(ctx, chave, manifesto.opcoes, urna.registros[-1], impresso, na_tela, ficha)
        desafios.append((urna.registros[-1]["id"], na_tela, motivo))

    for _ in range(eleitores):  # a mesa identifica o eleitor (em OUTRO aparelho) e ele sorteia uma ficha
        if sorteio.random() < chance_fiscal:
            # o fiscal pega ficha como qualquer um (a urna não sabe quem é), desafia 2 ou 3 vezes SEGUIDAS e
            # encerra sem votar: a urna que trapaceia só na cédula depois de um desafio é pega aqui
            ficha = U.nova_ficha()
            urna.libera(ficha)
            for _ in range(sorteio.choice((2, 3))):
                desafia(ficha)
            urna.encerra_sem_voto()
            fichas, devolvidas = fichas + 1, devolvidas + 1
        escolha = sorteio.choices(OPCOES, PESOS)[0]
        ficha = U.nova_ficha()
        urna.libera(ficha)
        fichas += 1
        if sorteio.random() < chance_desafio:  # o eleitor desconfiado desafia uma vez e vota de novo
            desafia(ficha)
        urna.prepara(escolha)
        recibos.append((urna.confirma(), ficha))
        verdade[escolha] += 1
    return {
        "urna": ident,
        "registros": urna.registros,
        "fecho": urna.fecha(),
        "comparecimento": fichas,  # contado pela mesa, não pela urna
        "devolvidas": devolvidas,
        "verdade": verdade,
        "desafios": desafios,
        "recibo": recibos[sorteio.randrange(len(recibos))],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Roda uma eleição inteira na Urna do Garoto.")
    ap.add_argument("--secoes", type=int, default=3)
    ap.add_argument("--eleitores", type=int, default=100, help="eleitores por seção")
    ap.add_argument("--desafio", type=float, default=0.10, help="chance de um eleitor desafiar a urna")
    ap.add_argument("--fiscal", type=float, default=0.03, help="chance de um fiscal testar a urna antes de um eleitor")
    ap.add_argument("--mural", default="mural.json")
    ap.add_argument("--ata", default="ata.json")
    ap.add_argument("--semente", type=int, default=None, help="pra repetir as mesmas escolhas e desafios")
    args = ap.parse_args()
    ok = 1 <= args.secoes <= 200 and 1 <= args.eleitores <= 5000 and 0 <= args.desafio < 0.9 and 0 <= args.fiscal < 0.5
    if not ok:
        ap.error("valores fora do razoável")
    inicio = time.perf_counter()
    print(pinta("Urna do Garoto;  por Garoto do Programa · eleição de mentira, matemática de verdade", "1"))
    print(f"{ELEICAO}\nopções: {' · '.join(OPCOES)}")

    print(pinta("\n[1/6] o grupo matemático", "1"))
    print(f'   p {GRUPO.p.bit_length()} bits · q {GRUPO.q.bit_length()} bits · tirados da semente "{SEMENTE}"')
    print(f"   impressão digital {GRUPO.impressao_digital()[:32]}… (python3 grupo.py refaz e confere)")

    print(pinta(f"\n[2/6] cerimônia das chaves: {len(GUARDIOES)} guardiões, abre com {QUORUM}", "1"))
    urnas = tuple(f"secao-{i:03d}" for i in range(1, args.secoes + 1))
    manifesto = U.Manifesto(ELEICAO, OPCOES, GUARDIOES, QUORUM, urnas)
    guardioes, chave = GU.cerimonia_das_chaves(list(GUARDIOES), QUORUM, U.pre_contexto(manifesto))
    for g in guardioes:
        print(f"   ✓ {g.nome:22} publicou {QUORUM} compromissos com prova e conferiu as {len(GUARDIOES)} fatias")
    print(f"   chave da eleição: {U.hx(chave)[:24]}…  (ninguém tem ela inteira. Nem eu.)")
    mural = U.novo_mural(manifesto, [g.compromissos for g in guardioes], chave)

    total = args.secoes * args.eleitores
    print(pinta(f"\n[3/6] votação: {args.secoes} seções × {args.eleitores} eleitores = {total} votos", "1"))
    print(f"   cada eleitor sorteia uma ficha e tem {args.desafio:.0%} de chance de DESAFIAR (uma vez, opção qualquer)")
    print(
        f"   antes de cada eleitor, {args.fiscal:.0%} de chance de um fiscal testar a urna (2 ou 3 desafios seguidos)"
    )
    sorteio = random.Random(args.semente)
    tarefas = [
        (urna, manifesto, mural["contexto"], chave, args.eleitores, args.desafio, args.fiscal, sorteio.random())
        for urna in urnas
    ]
    t = time.perf_counter()
    with ProcessPoolExecutor(max_workers=min(args.secoes, os.cpu_count() or 1)) as pool:
        secoes = list(pool.map(vota_secao, tarefas))
    verdade = Counter()
    desafios = []
    ata = {"versao": U.VERSAO, "contexto": mural["contexto"], "urnas": {}}
    for s in secoes:
        U.publica_urna(mural, s["urna"], s["registros"], s["fecho"], s["comparecimento"], s["devolvidas"])
        ata["urnas"][s["urna"]] = U.ata_da_secao(s["fecho"], s["comparecimento"], s["devolvidas"])
        verdade.update(s["verdade"])
        desafios.extend(s["desafios"])
    pegos = [d for d in desafios if d[2] is not None]
    testes = sum(s["devolvidas"] for s in secoes)
    print(f"   {total} cédulas cifradas e provadas em {time.perf_counter() - t:.0f} s")
    print(f"   {len(desafios)} desafios ({testes} testes de fiscal): a urna abriu a cédula do código impresso,")
    print("   e o celular conferiu que ela cifrou o que estava na tela")
    for ident, na_tela, motivo in desafios[:3]:
        conferiu = "a cédula do código impresso tinha isso  ✓" if motivo is None else motivo
        print(f"      {ident}: na tela {na_tela!r} → {conferiu}")
    if pegos:
        print(pinta(f"   ✗ {len(pegos)} desafios pegaram a urna mentindo!", "31"))
    exemplo, ficha_exemplo = secoes[0]["recibo"]
    recibo, ficha = U.codigo_curto(exemplo), U.ficha_impressa(ficha_exemplo)
    print(f"   recibo de um eleitor: {pinta(recibo, '33')}  ficha {ficha}  (não diz em quem ele votou)")

    print(pinta("\n[4/6] fechamento: a ata (elo final na porta + fichas da mesa), fora do mural", "1"))
    for s in secoes[:4]:
        f = s["fecho"]
        elo_final = f["elo_final"][:16]
        print(
            f"   {s['urna']}: {f['depositadas']} cédulas · {f['sem_voto']} sem voto · "
            f"{s['comparecimento']} fichas da mesa ({V.qtd(s['devolvidas'], 'devolvida')}) · elo final {elo_final}"
        )
    if len(secoes) > 4:
        print(f"   … e mais {len(secoes) - 4} seções")

    print(pinta("\n[5/6] apuração: os guardiões abrem SÓ a soma", "1"))
    garoto = guardioes[-1]
    print(f"   {garoto.nome} perdeu a chave dele. (Ele não tem mão.) Sem problema: precisa de {QUORUM}.")
    presentes = guardioes[:QUORUM]
    t = time.perf_counter()
    for g in guardioes:
        g.recebe_ata(ata)  # cada um pega a ata com os fiscais DELE, nunca com quem pede a apuração
    resultado = U.apura(mural, presentes)  # antes de abrir, cada um confere o mural (passos 1 a 5) com a ata dele
    print(f"   {', '.join(g.nome for g in presentes)} abriram a soma em {time.perf_counter() - t:.1f} s")
    for opcao in OPCOES:
        barra = "█" * round(40 * resultado[opcao] / total)
        print(f"   {opcao:14} {resultado[opcao]:6}  {barra}")
    bate = all(resultado[o] == verdade[o] for o in OPCOES)
    print(f"   o que os eleitores escolheram de verdade (só a simulação sabe): {'bate ✓' if bate else 'NÃO BATE ✗'}")
    U.salva(mural, args.mural)
    Path(args.ata).write_text(json.dumps(ata, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"   mural público salvo em {args.mural} · lacre {mural['lacre'][:16]} · ata em {args.ata}")

    print(pinta("\n[6/6] verificador (não importa urna.py; dá pra escrever o seu pelo PROTOCOLO.md)", "1"))
    problemas = V.verifica(mural, saida=lambda s: print("   " + s.lstrip("\n")), ata=ata)
    ok, mensagem = V.confere_recibo(mural, recibo, ficha=ficha)
    print(f"   {'✓' if ok else '✗'} eleitor em casa, recibo {recibo}, ficha {ficha}: {mensagem}")
    print(
        pinta(
            f"\n{'✓ eleição verificada' if not problemas else '✗ PROBLEMA'} em {time.perf_counter() - inicio:.0f} s",
            "1",
        )
    )
    print(f"Confere você: python3 verificador.py {args.mural} --ata {args.ata}")
    print(f"Procura o recibo: python3 verificador.py {args.mural} --ata {args.ata} --recibo {recibo} --ficha {ficha}")
    return 1 if problemas or pegos or not bate or not ok else 0


if __name__ == "__main__":
    sys.exit(main())
